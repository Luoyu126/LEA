// Experiment 3E extension: does gcc emit one complex LEA or split it, per -march?
// (long long: Windows `long` is 32-bit)
long long f_bi4d(long long a, long long b) { return a + b * 4 + 8; }
long long f_bid(long long a, long long b) { return a + b + 8; }
long long f_x2(long long a) { return a * 2; }
