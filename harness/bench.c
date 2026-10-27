// rdtsc-calibrated microbenchmark driver (Windows native or Linux/WSL).
// For each kernel: TSC ticks per instruction, then cycles = ticks / ticks(add_rr_chain)
// measured right next to it (`add rax,rcx` chain is 1 cycle/instr; `add rax,1` is not
// usable on Golden Cove+ because the renamer folds immediate adds).
//
// Usage: bench list          -> logical processors with efficiency class (Windows)
//        bench <cpu> [iters] [prefix] -> run kernels (optionally only names starting with prefix) on <cpu>
#ifdef _WIN32
#define _WIN32_WINNT 0x0A00  // Windows 10+: GetSystemCpuSetInformation
#include <windows.h>
#else
#define _GNU_SOURCE
#include <sched.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <x86intrin.h>
#include "kernels.h"

#define REPS 7
#define NK (sizeof(KERNELS) / sizeof(KERNELS[0]))

static long long iters = 200000;

// Experiment 4 pointer-chasing target: p, p+8 and p+4096 each hold p, so every
// load form [rax], [rax+8], [rax+rcx*8], [rax+4096]... (rcx = 0) chains back to p.
static char mem[8192] __attribute__((aligned(4096)));

static void init_mem(void) {
    *(void **)(mem) = mem;
    *(void **)(mem + 8) = mem;
    *(void **)(mem + 4096) = mem;
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
// EfficiencyClass: higher = more performant core (P-core > E-core).
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

static double ticks_per_instr(void (*fn)(long long, void *)) {
    unsigned aux;
    unsigned long long t0 = __rdtscp(&aux);
    fn(iters, mem);
    unsigned long long t1 = __rdtscp(&aux);
    return (double)(t1 - t0) / ((double)iters * UNROLL);
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static void (*find(const char *name))(long long, void *) {
    for (unsigned i = 0; i < NK; i++)
        if (!strcmp(KERNELS[i].name, name)) return KERNELS[i].fn;
    return NULL;
}

int main(int argc, char **argv) {
    init_mem();
    if (argc > 1 && !strcmp(argv[1], "list")) {
        // efficiency class + TSC ticks per add_rr cycle (higher core clock -> fewer ticks)
        void (*add)(long long, void *) = find("add_rr_chain");
        printf("cpu,efficiency_class,add_ticks\n");
        for (int c = 0; c < 64; c++) {
            if (efficiency_class(c) < 0) break;
            pin(c);
            for (int w = 0; w < 20; w++) add(iters, mem);
            printf("%d,%d,%.4f\n", c, efficiency_class(c), ticks_per_instr(add));
        }
        return 0;
    }
    int cpu = argc > 1 ? atoi(argv[1]) : 0;
    if (argc > 2) iters = atoll(argv[2]);
    const char *only = argc > 3 ? argv[3] : "";  // run only kernels whose name starts with this
    pin(cpu);
    void (*add)(long long, void *) = find("add_rr_chain");
    for (int w = 0; w < 50; w++) add(iters, mem);  // warm up / ramp frequency

    printf("kernel,cycles_median,cycles_min,cycles_max,add_ticks_median,cpu,eff_class\n");
    for (unsigned k = 0; k < NK; k++) {
        if (strncmp(KERNELS[k].name, only, strlen(only))) continue;
        double c[REPS], a[REPS];
        for (int r = 0; r < REPS; r++) {
            double a0 = ticks_per_instr(add);
            double t = ticks_per_instr(KERNELS[k].fn);
            double a1 = ticks_per_instr(add);
            a[r] = (a0 + a1) / 2;
            c[r] = t / a[r];
        }
        qsort(c, REPS, sizeof(double), cmp);
        qsort(a, REPS, sizeof(double), cmp);
        printf("%s,%.3f,%.3f,%.3f,%.4f,%d,%d\n", KERNELS[k].name, c[REPS / 2], c[0], c[REPS - 1], a[REPS / 2],
               cpu, efficiency_class(cpu));
    }
    return 0;
}
