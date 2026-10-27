#!/usr/bin/env python3
"""Build bench.exe, run every kernel on one CPU of each core type, write results.csv.

Usage: python run_all.py [--only=PREFIX] [--out=NAME.csv] [cpu:label ...]   (default: 0:P 2:E 14:LP-E)
cycles in results.csv are per *operation* (per instruction, x per_op for split sequences).
"""
import csv
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "results")
COLS = ["experiment", "kernel", "form", "path", "metric",
        "cycles_median", "cycles_min", "cycles_max", "core", "cpu"]


def build():
    subprocess.run([sys.executable, "gen.py", ".", "win"], cwd=HERE, check=True)
    subprocess.run(["gcc", "-O2", "-o", "bench.exe", "bench.c", "kernels.S"], cwd=HERE, check=True)


def main(targets, only="", out_name="results.csv"):
    build()
    meta = {k["name"]: k for k in json.load(open(os.path.join(HERE, "kernels.json")))}
    os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
    rows = []
    for cpu, label in targets:
        print(f"running cpu {cpu} ({label}) ...", flush=True)
        out = subprocess.run([os.path.join(HERE, "bench.exe"), str(cpu), "200000", only],
                             capture_output=True, text=True, check=True).stdout
        tag = f"_{only.rstrip('_')}" if only else ""
        open(os.path.join(OUT, "raw", f"cpu{cpu}_{label}{tag}.csv"), "w").write(out)
        for r in csv.DictReader(io.StringIO(out)):
            m = meta[r["kernel"]]
            per = m["per_op"]
            rows.append(dict(experiment=m["exp"], kernel=r["kernel"], form=m["form"], path=m["path"],
                             metric=m["metric"],
                             cycles_median=round(float(r["cycles_median"]) * per, 3),
                             cycles_min=round(float(r["cycles_min"]) * per, 3),
                             cycles_max=round(float(r["cycles_max"]) * per, 3),
                             core=label, cpu=cpu))
    with open(os.path.join(OUT, out_name), "w", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to results/{out_name}")


if __name__ == "__main__":
    opts = {a[2:].split("=")[0]: a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or ["0:P", "2:E", "14:LP-E"]
    main([(int(a.split(":")[0]), a.split(":")[1]) for a in args],
         opts.get("only", ""), opts.get("out", "results.csv"))
