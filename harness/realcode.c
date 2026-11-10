// Exp 5 driver: runs the real_kernels.c workloads on one pinned logical CPU and
// reports cycles per inner-loop iteration, calibrated the same way as bench.c
// (rdtsc ticks divided by the ticks of an `add rax,rcx` chain measured right next
// to each kernel, so frequency changes cancel).
//
// Usage: realcode.exe <cpu>
#ifdef _WIN32
#define _WIN32_WINNT 0x0A00  // Windows 10+: GetSystemCpuSetInformation
#include <windows.h>
#else
#define _GNU_SOURCE
#include <sched.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <x86intrin.h>

#define REPS 7
#define CAL 20000  // calibration-chain iterations (x100 adds)

long long w1_naive(const long long *tab, long long n, long long x);
long long w1_split(const long long *tab, long long n, long long x);
long long w1_naive_s1(const long long *tab, long long n, long long x);
long long w1_split_s1(const long long *tab, long long n, long long x);
long long w2_disp(const long long *a, const int *idx, long long n);
long long w2_nodisp(const long long *a, const int *idx, long long n);
long long w3_stride(const long long *a, long long n);

// ---- working sets
#define NTAB 64
#define NL1 1024          // 8 KB of long long: L1-resident on every core type
#define NBIG (4u << 20)   // 32 MB: larger than the 24 MB L3
#define NIDXBIG (2u << 20)

static long long tab[NTAB];
static long long a_l1[NL1];
static int idx_l1[NL1];
static long long *a_big;
static int *idx_big;
static volatile long long sink;

static void init_data(void) {
    for (int i = 0; i < NTAB; i++) tab[i] = i & 7;
    for (int i = 0; i < NL1; i++) a_l1[i] = i;
    for (int i = 0; i < NL1; i++) idx_l1[i] = (i * 37) & (NL1 - 2);
    a_big = malloc((size_t)NBIG * sizeof *a_big);
    idx_big = malloc((size_t)NIDXBIG * sizeof *idx_big);
    if (!a_big || !idx_big) { fprintf(stderr, "alloc failed\n"); exit(1); }
    for (unsigned i = 0; i < NBIG; i++) a_big[i] = i;
    unsigned s = 12345;
    for (unsigned i = 0; i < NIDXBIG; i++) {  // random gather: memory-latency bound
        s = s * 1664525u + 1013904223u;
        idx_big[i] = (int)(s % (NBIG - 2));
    }
}

static void pin(int cpu) {
#ifdef _WIN32
    SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
    SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << cpu);
#else
    cpu_set_t s;
    CPU_ZERO(&s);
    CPU_SET(cpu, &s);
    sched_setaffinity(0, sizeof s, &s);
#endif
}

#ifdef _WIN32
static int efficiency_class(int cpu) {
    static char buf[1 << 16];
    ULONG len = 0;
    if (!GetSystemCpuSetInformation((PSYSTEM_CPU_SET_INFORMATION)buf, sizeof buf, &len, GetCurrentProcess(), 0))
        return -1;
    for (ULONG off = 0; off < len;) {
        PSYSTEM_CPU_SET_INFORMATION p = (PSYSTEM_CPU_SET_INFORMATION)(buf + off);
        if (p->Type == CpuSetInformation && p->CpuSet.Group == 0 && p->CpuSet.LogicalProcessorIndex == cpu)
            return p->CpuSet.EfficiencyClass;
        off += p->Size;
    }
    return -1;
}
#else
static int efficiency_class(int cpu) { (void)cpu; return -1; }
#endif

// TSC ticks per cycle, from a dependency chain of `add rax,rcx` (1 cycle/instr).
static double ticks_per_cycle(void) {
    long long c = CAL;
    unsigned aux;
    unsigned long long t0 = __rdtscp(&aux);
    __asm__ volatile("xorl %%eax, %%eax\n\t"
                     "movl $1, %%ecx\n\t"
                     "1:\n\t"
                     ".rept 100\n\t"
                     "addq %%rcx, %%rax\n\t"
                     ".endr\n\t"
                     "decq %0\n\t"
                     "jnz 1b\n\t"
                     : "+r"(c)
                     :
                     : "rax", "rcx", "cc");
    unsigned long long t1 = __rdtscp(&aux);
    return (double)(t1 - t0) / ((double)CAL * 100.0);
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static int g_cpu;

// Time `expr` (which performs `total` inner iterations) and print cycles/iteration.
#define MEASURE(label, total, expr)                                                      \
    do {                                                                                 \
        double cy[REPS];                                                                 \
        sink += (expr); /* warm up */                                                     \
        for (int r = 0; r < REPS; r++) {                                                 \
            double a0 = ticks_per_cycle();                                               \
            unsigned aux;                                                                \
            unsigned long long t0 = __rdtscp(&aux);                                      \
            sink += (expr);                                                              \
            unsigned long long t1 = __rdtscp(&aux);                                      \
            double a1 = ticks_per_cycle();                                               \
            cy[r] = (double)(t1 - t0) / ((a0 + a1) / 2) / (double)(total);                \
        }                                                                                \
        qsort(cy, REPS, sizeof(double), cmp);                                            \
        printf("%s,%.4f,%.4f,%.4f,%d,%d\n", label, cy[REPS / 2], cy[0], cy[REPS - 1],     \
               g_cpu, efficiency_class(g_cpu));                                          \
        fflush(stdout);                                                                  \
    } while (0)

int main(int argc, char **argv) {
    g_cpu = argc > 1 ? atoi(argv[1]) : 0;
    pin(g_cpu);
    init_data();
    for (int w = 0; w < 20; w++) sink += w1_naive(tab, 100000, 1);  // ramp frequency

    printf("workload,cycles_median,cycles_min,cycles_max,cpu,eff_class\n");

    // W1: the LEA sits on the loop-carried dependency chain.
    const long long N1 = 20000000;
    MEASURE("w1_naive_chain", N1, w1_naive(tab, N1, 1));
    MEASURE("w1_split_chain", N1, w1_split(tab, N1, 1));
    MEASURE("w1_naive_s1_chain", N1, w1_naive_s1(tab, N1, 1));
    MEASURE("w1_split_s1_chain", N1, w1_split_s1(tab, N1, 1));

    // W2: the same base+index*8+disp form, but as a load addressing mode (AGU).
    const long long R2 = 20000, T2 = R2 * NL1;
    {
        long long acc = 0;
        MEASURE("w2_disp_L1", T2, ({ for (long long r = 0; r < R2; r++) acc += w2_disp(a_l1, idx_l1, NL1); acc; }));
        MEASURE("w2_nodisp_L1", T2, ({ for (long long r = 0; r < R2; r++) acc += w2_nodisp(a_l1, idx_l1, NL1); acc; }));
    }

    // W2 again, memory-latency bound (random gather over 32 MB).
    MEASURE("w2_disp_mem", (long long)NIDXBIG, w2_disp(a_big, idx_big, NIDXBIG));
    MEASURE("w2_nodisp_mem", (long long)NIDXBIG, w2_nodisp(a_big, idx_big, NIDXBIG));

    // W3: plain strided traversal, L1-resident; what gcc emits on its own.
    const long long R3 = 60000, N3 = 340, T3 = R3 * N3;
    {
        long long acc = 0;
        MEASURE("w3_stride_L1", T3, ({ for (long long r = 0; r < R3; r++) acc += w3_stride(a_l1, N3); acc; }));
    }
    return 0;
}
