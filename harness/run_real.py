#!/usr/bin/env python3
"""Exp 5: build and run the real-code benchmark, write results/realcode.csv.

Usage: python run_real.py [cpu:label ...]        (default: 0:P 2:E 14:LP-E)

Also dumps the gcc -O2 output of real_kernels.c to results/codegen/real_kernels.s,
which is the point of the experiment: it shows which addressing forms the compiler
actually emits.
"""
import csv
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results")
COLS = ["workload", "what", "cycles_median", "cycles_min", "cycles_max", "core", "cpu"]

# What each workload measures, and the addressing form gcc emitted for it.
WHAT = {
    "w1_naive_chain":    "lea 8[x+y*4] on the loop-carried chain",
    "w1_split_chain":    "same, split so only `add` is on the chain",
    "w1_naive_s1_chain": "x+y+8: gcc emits add+add imm, no lea",
    "w1_split_s1_chain": "same, split so only `add` is on the chain",
    "w2_disp_L1":        "base+index*8+disp8 as a load addressing mode, L1-resident",
    "w2_nodisp_L1":      "base+index*8 as a load addressing mode, L1-resident",
    "w2_disp_mem":       "base+index*8+disp8, random gather over 32 MB",
    "w2_nodisp_mem":     "base+index*8, random gather over 32 MB",
    "w3_stride_L1":      "a[i*3+1] traversal: gcc strength-reduces to a pointer walk",
}


def build():
    subprocess.run(["gcc", "-O2", "-masm=intel", "-S", "-o", "realk.s", "real_kernels.c"],
                   cwd=HERE, check=True)
    subprocess.run(["gcc", "-O2", "-o", "realcode.exe", "realcode.c", "real_kernels.c"],
                   cwd=HERE, check=True)
    os.makedirs(os.path.join(OUT, "codegen"), exist_ok=True)
    with open(os.path.join(HERE, "realk.s")) as f:
        src = f.read()
    with open(os.path.join(OUT, "codegen", "real_kernels.s"), "w") as f:
        f.write(src)


def main(targets):
    build()
    os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
    rows = []
    for cpu, label in targets:
        print(f"running cpu {cpu} ({label}) ...", flush=True)
        out = subprocess.run([os.path.join(HERE, "realcode.exe"), str(cpu)],
                             capture_output=True, text=True, check=True).stdout
        with open(os.path.join(OUT, "raw", f"cpu{cpu}_{label}_real.csv"), "w") as f:
            f.write(out)
        for r in csv.DictReader(io.StringIO(out)):
            rows.append(dict(workload=r["workload"], what=WHAT.get(r["workload"], ""),
                             cycles_median=r["cycles_median"], cycles_min=r["cycles_min"],
                             cycles_max=r["cycles_max"], core=label, cpu=cpu))
    with open(os.path.join(OUT, "realcode.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to results/realcode.csv")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or ["0:P", "2:E", "14:LP-E"]
    main([(int(a.split(":")[0]), a.split(":")[1]) for a in args])
