// Run ONE kernel, pinned to one CPU, for hardware-counter measurements (VTune counting mode).
// Unlike bench.c there is no add_rr_chain calibration and no warm-up, so the counters see only
// this kernel (plus process start-up, which the `empty` kernel measures and lets you subtract).
//
// Usage: uopcount <cpu> <kernel> [iters] [reps]   e.g. uopcount 12 e3B_disp8 200000 25
// Instructions in the kernel body = UNROLL * iters * reps (UNROLL = 200).
#define _WIN32_WINNT 0x0A00
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "kernels.h"

static char mem[8192] __attribute__((aligned(4096)));

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: uopcount <cpu> <kernel> [iters] [reps]\n");
        return 2;
    }
    int cpu = atoi(argv[1]);
    long long iters = argc > 3 ? atoll(argv[3]) : 200000;
    int reps = argc > 4 ? atoi(argv[4]) : 25;
    void (*fn)(long long, void *) = NULL;
    for (unsigned i = 0; i < sizeof(KERNELS) / sizeof(KERNELS[0]); i++)
        if (!strcmp(KERNELS[i].name, argv[2])) fn = KERNELS[i].fn;
    if (!fn) {
        fprintf(stderr, "unknown kernel %s\n", argv[2]);
        return 2;
    }
    *(void **)(mem) = mem;  // same self-pointers as bench.c (used by the load kernels)
    *(void **)(mem + 8) = mem;
    *(void **)(mem + 4096) = mem;
    SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_HIGHEST);
    SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << cpu);
    for (int r = 0; r < reps; r++) fn(iters, mem);
    printf("%s cpu=%d iters=%lld reps=%d loop_passes=%lld (a 200-instruction body runs %lld instructions; empty runs 0)\n",
           argv[2], cpu, iters, reps, iters * reps, (long long)UNROLL * iters * reps);
    return 0;
}
