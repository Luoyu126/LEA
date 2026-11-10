#!/usr/bin/env python3
"""Figures for results_mine/ (i7-13700H). Values = mean of the two CPUs of each core type.
Usage: python plot_mine.py   -> results_mine/fig_mine_*.png"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MINE = os.path.join(HERE, "..")
THEIRS = os.path.join(HERE, "..", "..", "results")
COLOR = {"P": "#2a78d6", "E": "#eb6834"}  # same slots as the students' figures (validated)
LABEL = {"P": "P-core (Raptor Cove)", "E": "E-core (Gracemont)"}
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": MUTED,
    "text.color": INK, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "legend.frameon": False, "hatch.color": SURFACE,
    "hatch.linewidth": 1.2,
})


def load(path):
    d = {}
    for r in csv.DictReader(open(path)):
        d.setdefault((r["kernel"], r["path"]), {}).setdefault(r["core"], []).append(float(r["cycles_median"]))
    return {k: {c: sum(v) / len(v) for c, v in cv.items()} for k, cv in d.items()}


Z, TZ = load(os.path.join(MINE, "zero_disp.csv")), load(os.path.join(THEIRS, "zero_disp.csv"))
X = load(os.path.join(MINE, "extension.csv"))


def val(tbl, kernel, core):
    for (k, p), cv in tbl.items():
        if k == kernel and core in cv:
            return cv[core]
    raise KeyError(kernel)


def label_bars(ax, bars, vals):
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.05, f"{v:.2f}".rstrip("0").rstrip("."),
                ha="center", va="bottom", fontsize=8, color=INK2)


# ---- 1. replication of the zero-displacement study ----
forms = [("ez_bi_base", "[rax+rcx]"), ("ez_bi_d8_0_base", "[rax+rcx+0]\ndisp8"),
         ("ez_bi_d32_0_base", "[rax+rcx+0]\ndisp32"), ("ez_bi_d8_8_base", "[rax+rcx+8]"),
         ("ez0_bi_d8_0_base", "[rax+rcx+0]\nrcx=0"), ("ez_b_d8_0_base", "[rax+0]\n(no index)"),
         ("ezi_i1_d32_0_index", "[rax*1+0]\n(no base)"), ("ez_rbp_d8_0_index", "[rbp+rax+0]")]
fig, ax = plt.subplots(figsize=(11, 4.4))
x, w = np.arange(len(forms)), 0.36
for i, c in enumerate("PE"):
    vals = [val(Z, k, c) for k, _ in forms]
    bars = ax.bar(x + (i - 0.5) * w, vals, w, color=COLOR[c], edgecolor=SURFACE, linewidth=2, label=LABEL[c] + ", mine")
    label_bars(ax, bars, vals)
    for j, (k, _) in enumerate(forms):
        t = val(TZ, k, c)
        ax.plot([x[j] + (i - 1) * w + 0.03, x[j] + i * w - 0.03], [t, t], color=INK, lw=2, solid_capstyle="butt")
ax.plot([], [], color=INK, lw=2, label="students' 285H (Lion Cove / Skymont)")
ax.set_xticks(x)
ax.set_xticklabels([f for _, f in forms])
ax.set_ylabel("latency (cycles)")
ax.set_ylim(0, 2.5)
fig.suptitle("Replication: lea latency on i7-13700H. E-cores pay 1 extra cycle whenever index + displacement are both encoded",
             x=0.01, ha="left", fontsize=11, fontweight="bold")
fig.legend(loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=3, fontsize=9)
fig.tight_layout(rect=(0, 0, 1, 0.86))
fig.savefig(os.path.join(MINE, "fig_mine_replication.png"), dpi=160)
plt.close(fig)


# ---- 2 & 3: with vs without a zero displacement, one panel per core ----
def pair_fig(name, title, pairs, ylabel, note=""):
    fig, axes = plt.subplots(2, 1, figsize=(13, 8.2), sharey=True, sharex=True)
    for ax, c in zip(axes, "PE"):
        x, w = np.arange(len(pairs)), 0.38
        a = [val(X, p[1], c) for p in pairs]
        b = [val(X, p[2], c) for p in pairs]
        b1 = ax.bar(x - w / 2, a, w, color=COLOR[c], edgecolor=SURFACE, linewidth=2, label="without displacement")
        b2 = ax.bar(x + w / 2, b, w, color=COLOR[c], edgecolor=SURFACE, linewidth=2, hatch="///", alpha=0.75,
                    label="with +0 displacement")
        label_bars(ax, b1, a)
        label_bars(ax, b2, b)
        ax.set_xticks(x)
        ax.set_xticklabels([p[0] for p in pairs], fontsize=9)
        ax.tick_params(axis="x", labelbottom=True)
        ax.set_ylabel(ylabel)
        ax.set_title(LABEL[c], loc="left", fontsize=10, color=INK2)
        ax.legend(loc="upper left", fontsize=8.5)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, fontweight="bold")
    if note:
        fig.text(0.01, 0.01, note, fontsize=8.5, color=INK2, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04 if note else 0, 1, 0.95))
    fig.savefig(os.path.join(MINE, name), dpi=160)
    plt.close(fig)


pair_fig("fig_mine_part2_lea_modes.png",
         "Part 2: new lea address modes. Only the index + displacement combination is slowed on Gracemont",
         [("64-bit addr\n[rax+rcx]\nlatency", "x2r_bi", "x2r_bi_d8"),
          ("0x67 prefix\n[eax+ecx]\nlatency", "x2a_bi", "x2a_bi_d8"),
          ("0x67 prefix\n[eax] (base only)\nlatency", "x2a_b", "x2a_b_d8"),
          ("32-bit dest\nlea eax,[rax+rcx]\nlatency", "x2b_d_bi", "x2b_d_bi_d8"),
          ("16-bit dest\nlea ax,[rax+rcx]\nlatency", "x2b_w_bi", "x2b_w_bi_d8"),
          ("index only*\n[rax] vs [rax*1+0]\nlatency", "x2d_b", "x2d_i1_0"),
          ("0x67\n[r14d+r15d]\nthroughput", "x2a_tp_bi", "x2a_tp_bi_d8"),
          ("RIP-relative**\n[rip+0] vs [rip+64]\nthroughput", "x2c_rip_0", "x2c_rip_64")],
         "cycles",
         note="* index-only cannot be encoded without a disp32, so the no-displacement bar is the same-value base form [rax].   "
              "** RIP-relative always has a disp32 and no register input: compares disp 0 vs 64, throughput only.")

pair_fig("fig_mine_part3_other_instrs.png",
         "Part 3: stores, loads and add-with-memory. A zero displacement costs nothing on either core",
         [("lea [b+i]\n(reference)\nlatency", "x2r_bi", "x2r_bi_d8"),
          ("mov [b+i],rax\nstore\nthroughput", "x3s_bi", "x3s_bi_d8"),
          ("mov rax,[b+i]\nload\nthroughput", "x3lt_bi", "x3lt_bi_d8"),
          ("mov rax,[rax+i]\nload-use\nlatency", "x3l_bi", "x3l_bi_d8"),
          ("add rax,[rax+i]\naddress on chain\nlatency", "x3a_bi", "x3a_bi_d8"),
          ("add rax,[b+i]\nregister on chain\nlatency", "x3r_bi", "x3r_bi_d8"),
          ("add r,[b+i]\nthroughput", "x3t_bi", "x3t_bi_d8"),
          ("store→load\n[b+i] pair\nlatency", "x3f_bi", "x3f_bi_d8")],
         "cycles", note="b = base register, i = index register (value 0). Throughput bars are cycles per instruction (lower = faster).")
print("figures written to results_mine/")
