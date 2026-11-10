// Exp 5: does the index+displacement LEA penalty show up in compiler-generated code?
//
// Three workloads, compiled as their own translation unit (-O2) so the generated
// addressing forms can be checked with objdump -> results/codegen/real_kernels.s.
//
//   W1  the same arithmetic ON the loop-carried dependency chain, as an explicit LEA
//   W2  the same arithmetic folded into a LOAD's addressing mode (computed by the AGU)
//   W3  a plain strided traversal, to see what gcc does when left alone
//
// Every function is noinline so the driver cannot specialize it, and each returns a
// value the driver consumes, so nothing is optimized away.

#define NOINLINE __attribute__((noinline))

// ---------------------------------------------------------------- W1: on the chain
//
// Both loops compute exactly the same x. The only difference is whether the
// index*scale + displacement work sits on the loop-carried chain through x.
//
// naive: x = x + y*4 + 8   -> one 3-component LEA; its latency IS the chain cost.
// split: y*4 + 8 computed into d first, leaving a plain `add x, d` on the chain.
//
// The empty asm block in w1_split is an optimization barrier: without it gcc sees the
// same dataflow as w1_naive and re-fuses the two steps back into one LEA. It forces d
// to be materialized in a register and costs no instruction of its own.

long long NOINLINE w1_naive(const long long *tab, long long n, long long x) {
    for (long long k = 0; k < n; k++) {
        long long y = tab[k & 63];
        x = x + y * 4 + 8;
    }
    return x;
}

long long NOINLINE w1_split(const long long *tab, long long n, long long x) {
    for (long long k = 0; k < n; k++) {
        long long y = tab[k & 63];
        long long d = y * 4 + 8;
        __asm__("" : "+r"(d));  // keep d off the x chain
        x += d;
    }
    return x;
}

// Scale-1 versions. gcc picks scale 4 above, and a scale factor costs the P-core a
// cycle on its own (Exp 1), which hides the index+disp effect behind a second cause.
// With `x + y + 8` the LEA is base + index*1 + disp -- the exact headline form, which
// Exp 1 puts at 1 cycle on P and 2 on E/LP-E.

long long NOINLINE w1_naive_s1(const long long *tab, long long n, long long x) {
    for (long long k = 0; k < n; k++) {
        long long y = tab[k & 63];
        x = x + y + 8;
    }
    return x;
}

long long NOINLINE w1_split_s1(const long long *tab, long long n, long long x) {
    for (long long k = 0; k < n; k++) {
        long long y = tab[k & 63];
        long long d = y + 8;
        __asm__("" : "+r"(d));  // keep d off the x chain
        x += d;
    }
    return x;
}

// ------------------------------------------------- W2: the same form inside a load
//
// a[idx[k] + 1] is base + index*8 + disp8 -- the exact form that costs an extra
// cycle as a LEA. Here the AGU computes it as part of the load.
// w2_nodisp drops the displacement (base + index*8) for comparison.

long long NOINLINE w2_disp(const long long *a, const int *idx, long long n) {
    long long s = 0;
    for (long long k = 0; k < n; k++) s += a[idx[k] + 1];
    return s;
}

long long NOINLINE w2_nodisp(const long long *a, const int *idx, long long n) {
    long long s = 0;
    for (long long k = 0; k < n; k++) s += a[idx[k]];
    return s;
}

// --------------------------------------------------- W3: plain strided traversal
//
// The realistic case: a[i*3 + 1] looks like base + index*scale + disp in the source.
// What gcc actually emits is the interesting part (see the dumped asm).

long long NOINLINE w3_stride(const long long *a, long long n) {
    long long s = 0;
    for (long long i = 0; i < n; i++) s += a[i * 3 + 1];
    return s;
}
