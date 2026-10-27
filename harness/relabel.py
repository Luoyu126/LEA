#!/usr/bin/env python3
"""Refresh the `form` column of a results CSV from kernels.json (labels only; data untouched).

Usage: python relabel.py ../results/zero_disp.csv
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
forms = {k["name"]: k["form"] for k in json.load(open(os.path.join(HERE, "kernels.json")))}
path = sys.argv[1]
rows = list(csv.DictReader(open(path)))
for r in rows:
    r["form"] = forms.get(r["kernel"], r["form"])
with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, rows[0].keys())
    w.writeheader()
    w.writerows(rows)
print(f"relabeled {len(rows)} rows in {path}")
