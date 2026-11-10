#!/usr/bin/env python3
"""Compare my i7-13700H results (results_mine/) with the students' 285H results (results/).
Writes results_mine/compare_<file>.csv and prints a markdown table.
Usage: python compare.py results.csv|zero_disp.csv"""
import csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
MINE, THEIRS = os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "results")
name = sys.argv[1]
theirs, mine = {}, {}
for r in csv.DictReader(open(os.path.join(THEIRS, name))):
    if r["core"] in ("P", "E"):
        theirs.setdefault((r["kernel"], r["path"]), {}).setdefault(r["core"], []).append(float(r["cycles_median"]))
order, forms = [], {}
for r in csv.DictReader(open(os.path.join(MINE, name))):
    key = (r["kernel"], r["path"])
    if key not in mine: order.append(key); forms[key] = (r["experiment"], r["form"], r["metric"])
    mine.setdefault(key, {})[r["cpu"]] = float(r["cycles_median"])
cpus = sorted({c for v in mine.values() for c in v}, key=int)
out = []
for key in order:
    exp, form, metric = forms[key]
    t = theirs.get(key, {})
    tp = round(sum(t["P"]) / len(t["P"]), 2) if "P" in t else ""
    te = round(sum(t["E"]) / len(t["E"]), 2) if "E" in t else ""
    out.append(dict(experiment=exp, kernel=key[0], path=key[1], form=form, metric=metric,
                    **{f"mine_cpu{c}": mine[key].get(c, "") for c in cpus},
                    theirs_P_LionCove=tp, theirs_E_Skymont=te))
with open(os.path.join(MINE, "compare_" + name), "w", newline="") as f:
    w = csv.DictWriter(f, out[0].keys()); w.writeheader(); w.writerows(out)
print("| exp | form | path | metric | " + " | ".join(f"cpu{c}" for c in cpus) + " | theirs P | theirs E |")
print("|---" * (6 + len(cpus)) + "|")
for o in out:
    print(f"| {o['experiment']} | `{o['form']}` | {o['path']} | {o['metric'][:3]} | "
          + " | ".join(f"{o['mine_cpu'+c]:.2f}" for c in cpus) + f" | {o['theirs_P_LionCove']} | {o['theirs_E_Skymont']} |")
