#!/usr/bin/env python3
"""Assemble kernels.S and print, for every extension kernel (name starts with 'x'), the first
instructions of its loop body as objdump decodes them, next to the label we gave it.
Usage (from harness/): python ../results_mine/scripts/check_encodings.py > ../results_mine/encodings.txt"""
import json, re, subprocess
subprocess.run(["gcc", "-c", "kernels.S", "-o", "kernels_check.o"], check=True)
dis = subprocess.run(["objdump", "-d", "-M", "intel", "--no-show-raw-insn", "kernels_check.o"],
                     capture_output=True, text=True, check=True).stdout
raw = subprocess.run(["objdump", "-d", "-w", "-M", "intel", "kernels_check.o"], capture_output=True, text=True, check=True).stdout
meta = {k["name"]: k for k in json.load(open("kernels.json"))}
blocks = re.split(r"\n(?=[0-9a-f]+ <k_)", raw)
for b in blocks:
    m = re.match(r"[0-9a-f]+ <k_(x\w+)>:", b)
    if not m: continue
    name = m.group(1); kd = meta[name]
    lines = [l for l in b.splitlines()[1:] if "\t" in l]
    # loop body starts after the padding following the last setup instruction: find first body insn
    n = len(kd["body"])
    body = [l for l in lines if not re.search(r"\b(push|pop|nop|xchg|ret|dec|jne|data16|cs nop)\b", l)]
    # skip prologue (mov/xor/lea setup) = the first 15 + setup instructions
    skip = 15 + (kd["setup"].count("\n") + 1 if kd["setup"] else 0)
    for l in body[skip:skip + n]:
        parts = l.split("\t")
        print(f"{name:18s} | {parts[1].strip():36s} | {parts[2].strip():40s} | {kd['form']}")
