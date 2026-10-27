#!/usr/bin/env python3
"""Plot results/results.csv -> results/fig_exp{1,2,3,4}.png (light theme, for slides)."""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")

CORES = ["P", "E", "LP-E"]
CORE_LABEL = {"P": "P-core (Lion Cove)", "E": "E-core (Skymont)", "LP-E": "LP E-core (Crestmont?)"}
CORE_COLOR = {"P": "#2a78d6", "E": "#eb6834", "LP-E": "#1baf7a"}  # categorical slots 1-3
REF_ARCH = {"P": "ARL-P", "E": "ARL-E", "LP-E": "MTL-E"}
LEA_COLOR, LOAD_COLOR = "#6250d6", "#eda100"  # slots 7, 4: not core identities
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": INK, "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "legend.frameon": False,
})

rows = list(csv.DictReader(open(os.path.join(RES, "results.csv"))))
ref = {(r["form"], r["arch"]): r for r in csv.DictReader(open(os.path.join(RES, "uops_info_reference.csv")))}


def get(kernel, core):
    for r in rows:
        if r["kernel"] == kernel and r["core"] == core:
            return float(r["cycles_median"]), float(r["cycles_min"]), float(r["cycles_max"])
    raise KeyError(kernel)


def grouped(ax, kernels, labels, ref_forms=None, ref_metric="latency"):
    x = np.arange(len(kernels))
    w = 0.26
    for i, c in enumerate(CORES):
        vals = [get(k, c) for k in kernels]
        med = [v[0] for v in vals]
        err = [[v[0] - v[1] for v in vals], [v[2] - v[0] for v in vals]]
        ax.bar(x + (i - 1) * w, med, w, color=CORE_COLOR[c], edgecolor=SURFACE, linewidth=2,
               label=CORE_LABEL[c], yerr=err, error_kw=dict(ecolor=INK2, elinewidth=0.8, capsize=0))
        if ref_forms:
            for j, f in enumerate(ref_forms):
                rr = ref.get((f, REF_ARCH[c]))
                if rr:
                    ax.plot([x[j] + (i - 1.5) * w + 0.03, x[j] + (i - 0.5) * w - 0.03],
                            [float(rr[ref_metric])] * 2, color=INK, linewidth=2, solid_capstyle="butt")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")


def ref_handle():
    return plt.Line2D([], [], color=INK, linewidth=2, label="uops.info (ARL-P / ARL-E / MTL-E)")


def finish(fig, ax, name, title, ylabel, extra=()):
    ax.set_ylabel(ylabel)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    h, l = ax.get_legend_handles_labels()
    for e in extra:
        h.append(e)
        l.append(e.get_label())
    fig.legend(h, l, loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=len(h), fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(os.path.join(RES, name), dpi=160)
    plt.close(fig)


# --- Exp 1: LEA latency sweep, base path and index path panels ---
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw=dict(width_ratios=[8, 8]), sharey=True)
base = [("b", "base"), ("bd8", "base+disp8"), ("bd32", "base+disp32"), ("bi", "base+index"),
        ("bi4", "base+index*4"), ("bi8", "base+index*8"), ("bid", "base+index+disp"),
        ("bi4d", "base+index*4+disp"), ("bid32bit", "base+index+disp (32-bit)")]
idx = [("bi", "base+index"), ("bi4", "base+index*4"), ("i4d", "index*4+disp"), ("bid", "base+index+disp"),
       ("bi4d", "base+index*4+disp"), ("rbp_i", "rbp+index"), ("r13_i", "r13+index")]
grouped(axes[0], [f"e1_{n}_base" for n, _ in base], [f for _, f in base], [f for _, f in base])
grouped(axes[1], [f"e1_{n}_index" for n, _ in idx], [f for _, f in idx], [f for _, f in idx])
axes[0].set_title("chain through base register", loc="left", color=INK2, fontsize=10)
axes[1].set_title("chain through index register", loc="left", color=INK2, fontsize=10)
axes[0].set_yticks([0, 1, 2, 3])
finish(fig, axes[0], "fig_exp1_lea_latency.png", "Exp 1 - LEA latency by addressing form",
       "latency (cycles)", [ref_handle()])

# --- Exp 3: equivalent encodings ---
e3 = [("e3A_rax_rax", "A: [rax+rax] 4B"), ("e3A_rax_x2", "A: [rax*2+0] 8B"),
      ("e3B_nodisp", "B: [rax+rcx]"), ("e3B_disp8", "B: +disp8=0"), ("e3B_disp32", "B: +disp32=0"),
      ("e3C_rbx", "C: [rbx+rax]"), ("e3C_rsp", "C: [rsp+rax]"), ("e3C_r12", "C: [r12+rax]"),
      ("e3C_rbp", "C: [rbp+rax+0]"), ("e3C_r13", "C: [r13+rax+0]"),
      ("e3D_lea_x4", "D: lea [rax*4+0]"), ("e3D_shl", "D: shl rax,2"),
      ("e3D_lea_bi", "D: lea [rax+rcx]"), ("e3D_add", "D: add rax,rcx"),
      ("e3E_lea3", "E: lea [rax+rcx+8]"), ("e3E_lea_add", "E: lea+add imm"), ("e3E_add_add", "E: add+add imm"),
      ("e3E_lea3s", "E: lea [rax+rcx*4+8]"), ("e3E_leas_add", "E: lea*4 + add imm"),
      ("e3E_hoist", "E: hoisted lea + add")]
fig, ax = plt.subplots(figsize=(14, 4.8))
grouped(ax, [k for k, _ in e3], [l for _, l in e3])
ax.set_yticks([0, 1, 2])
finish(fig, ax, "fig_exp3_equivalent.png",
       "Exp 3 - equivalent encodings (same result, cycles per operation on the dependency chain)",
       "latency (cycles / op)")

# --- Exp 4 vs Exp 1: LEA latency vs load-use latency per form, one panel per core ---
pairs = [("base", "e1_b_base", "e4_b"), ("base+index", "e1_bi_base", "e4_bi"),
         ("base+index*8", "e1_bi8_base", "e4_bi8"), ("base+disp8", "e1_bd8_base", "e4_bd8"),
         ("base+disp32", "e1_bd32_base", "e4_bd32"), ("base+index+disp", "e1_bid_base", "e4_bid")]
fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), sharey=True)
x = np.arange(len(pairs))
for ax, c in zip(axes, CORES):
    lea = [get(l, c)[0] for _, l, _ in pairs]
    ld = [get(m, c)[0] for _, _, m in pairs]
    ax.bar(x - 0.19, lea, 0.38, color=LEA_COLOR, edgecolor=SURFACE, linewidth=2, label="LEA (ALU)")
    ax.bar(x + 0.19, ld, 0.38, color=LOAD_COLOR, edgecolor=SURFACE, linewidth=2, label="load-use (AGU + L1)")
    ax.set_xticks(x)
    ax.set_xticklabels([p for p, _, _ in pairs], rotation=30, ha="right")
    ax.set_title(CORE_LABEL[c], loc="left", color=INK2, fontsize=10)
axes[0].set_yticks([0, 1, 2, 3, 4, 5])
finish(fig, axes[0], "fig_exp4_lea_vs_load.png", "Exp 4 - same addressing form: LEA latency vs load-use latency",
       "latency (cycles)")

# --- Exp 2: throughput ---
tp = [("e2_b", "base"), ("e2_bd8", "base+disp8"), ("e2_bi", "base+index"), ("e2_bi4", "base+index*4"),
      ("e2_i4d", "index*4+disp"), ("e2_bid", "base+index+disp"), ("e2_bi4d", "base+index*4+disp"),
      ("e2_rbp_i", "rbp+index"), ("e2_r13_i", "r13+index"), ("e2_rip", "rip-relative")]
fig, ax = plt.subplots(figsize=(13, 4.6))
grouped(ax, [k for k, _ in tp], [l for _, l in tp], [l for _, l in tp], ref_metric="throughput")
finish(fig, ax, "fig_exp2_lea_throughput.png",
       "Exp 2 - LEA reciprocal throughput (8 independent chains; lower = more LEAs per cycle)",
       "cycles / instruction", [ref_handle()])

# --- Focus: zero displacement (results/zero_disp.csv, CPUs 0 / 2 / 14) ---
zpath = os.path.join(RES, "zero_disp.csv")
if os.path.exists(zpath):
    zrows = list(csv.DictReader(open(zpath)))
    ZCPU = {"P": "0", "E": "2", "LP-E": "14"}

    def zget(kernel, core):
        r = next(r for r in zrows if r["kernel"] == kernel and r["cpu"] == ZCPU[core])
        return float(r["cycles_median"])

    def zbars(ax, items, fmt):
        x = np.arange(len(items))
        w = 0.26
        for i, c in enumerate(CORES):
            vals = [zget(k, c) for k, _ in items]
            bars = ax.bar(x + (i - 1) * w, vals, w, color=CORE_COLOR[c], edgecolor=SURFACE, linewidth=2,
                          label=CORE_LABEL[c])
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v, fmt.format(v), ha="center", va="bottom",
                        fontsize=8, color=INK2)
        ax.set_xticks(x)
        ax.set_xticklabels([l for _, l in items])

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), gridspec_kw=dict(width_ratios=[7, 3]))
    zbars(axes[0], [("ez_bi_base", "[rax+rcx*1]"),
                    ("ez_bi_d8_0_base", "[rax+rcx*1+0]\ndisp8"),
                    ("ez_bi_d32_0_base", "[rax+rcx*1+0]\ndisp32"),
                    ("ez_bi_d8_8_base", "[rax+rcx*1+8]"),
                    ("ez_b_d8_0_base", "[rax+0]\n(no index)"),
                    ("ez_rbx_index", "[rbx+rax*1]"),
                    ("ez_rbp_d8_0_index", "[rbp+rax*1]\n(disp8 forced)")], "{:.0f}")
    axes[0].set_yticks([0, 1, 2])
    axes[0].set_ylabel("latency (cycles)")
    axes[0].set_title("latency - dependency chain", loc="left", color=INK2, fontsize=10)
    zbars(axes[1], [("ez_tp_bi", "[r14+r15*1]"), ("ez_tp_bi_d8_0", "[r14+r15*1+0]\ndisp8")], "{:.2f}")
    axes[1].set_ylabel("cycles / instruction")
    axes[1].set_title("reciprocal throughput", loc="left", color=INK2, fontsize=10)
    finish(fig, axes[0], "fig_zero_disp.png",
           "Same instruction, plus a zero byte: lea rax,[rax+rcx*1] vs lea rax,[rax+rcx*1+0]",
           "latency (cycles)")

    # Minimal slide version: cores on x; every measurable base/index/disp combination (scale 1),
    # all computing exactly rax (rcx = 0, disp = 0).
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = np.arange(len(CORES))
    w = 0.2
    for off, (k, label, color) in zip((-1.5 * w, -0.5 * w, 0.5 * w, 1.5 * w), [
            ("ez_b_d8_0_base", "lea rax,[rax+0]   (base + disp)", MUTED),
            ("ez0_bi_base", "lea rax,[rax+rcx*1]   (base + index)", AXIS),
            ("ezi_i1_d32_0_index", "lea rax,[rax*1+0]   (index + disp)", "#ec835a"),
            ("ez0_bi_d8_0_base", "lea rax,[rax+rcx*1+0]   (base + index + disp)", "#eb6834")]):
        vals = [zget(k, c) for c in CORES]
        bars = ax.bar(x + off, vals, w, color=color, edgecolor=SURFACE, linewidth=2, label=label)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.0f}", ha="center", va="bottom",
                    fontsize=12, fontweight="bold", color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(["P-core", "E-core", "LP E-core"], fontsize=11)
    ax.set_yticks([0, 1, 2])
    ax.set_ylim(0, 2.4)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper left", bbox_to_anchor=(0.005, 0.93),
               ncol=1, fontsize=9)
    ax.set_ylabel("latency (cycles)")
    fig.suptitle("Four ways to compute rax: slow on E-cores whenever index and disp are both present",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.72))
    fig.savefig(os.path.join(RES, "fig_zero_disp_simple.png"), dpi=160)
    plt.close(fig)

print("figures written to results/")
