#!/usr/bin/env python3
"""Slide versions of the results_mine figures, sized for the deck in slides/ (1920x1080 canvas):
no built-in title (the slide has one), text >= 24 px at display size, the deck's colors.
Same data as plot_mine.py (mean of the two CPUs of each core type).
Usage: python plot_slides.py   -> results_mine/slides/fig_slide_*.png"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import plot_mine as pm  # loads the CSVs (also re-renders the document figures, unchanged)

OUT = os.path.join(pm.MINE, "slides")
os.makedirs(OUT, exist_ok=True)
DPI = 200  # figures are shown at half their pixel size on the slide
BG, INK, INK2, GRID, AXIS = "#F3F5F7", "#13171D", "#4A5361", "#D9DEE4", "#9AA3AE"
COLOR = {"P": "#2563C4", "E": "#D9581F"}  # the deck's P / E colors
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2, "xtick.color": INK, "ytick.color": INK2, "text.color": INK,
    "grid.color": GRID, "font.size": 18, "hatch.color": BG, "hatch.linewidth": 2.0,
})


def labels(ax, bars, vals, size=16):
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.04, f"{v:.2f}".rstrip("0").rstrip("."),
                ha="center", va="bottom", fontsize=size, color=INK2)


# ---- replication: 960 x 560 on the slide ----
forms = [("ez_bi_base", "[rax+rcx]"), ("ez_bi_d8_0_base", "[rax+rcx+0]"),
         ("ez_bi_d8_8_base", "[rax+rcx+8]"), ("ezi_i1_d32_0_index", "[rax*1+0]\nno base")]
fig, ax = plt.subplots(figsize=(9.6, 5.6))
x, w = np.arange(len(forms)), 0.36
for i, c in enumerate("PE"):
    vals = [pm.val(pm.Z, k, c) for k, _ in forms]
    labels(ax, ax.bar(x + (i - 0.5) * w, vals, w, color=COLOR[c], edgecolor=BG, linewidth=3,
                      label={"P": "P-core · Raptor Cove", "E": "E-core · Gracemont"}[c]), vals)
    for j, (k, _) in enumerate(forms):
        t = pm.val(pm.TZ, k, c)
        ax.plot([x[j] + (i - 1) * w + 0.04, x[j] + i * w - 0.04], [t, t], color=INK, lw=3, solid_capstyle="butt")
ax.plot([], [], color=INK, lw=3, label="285H (Lion Cove / Skymont)")
ax.set_xticks(x)
ax.set_xticklabels([f for _, f in forms])
ax.set_ylabel("latency (cycles)")
ax.set_ylim(0, 2.9)
ax.set_yticks([0, 1, 2])
ax.grid(axis="y")
ax.set_axisbelow(True)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
h, l = ax.get_legend_handles_labels()
h, l = h[1:] + h[:1], l[1:] + l[:1]  # P, E, then the 285H tick
ax.legend(h, l, loc="upper left", ncol=2, fontsize=16, frameon=False, handlelength=1.2, columnspacing=1.2)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_slide_replication.png"), dpi=DPI)
plt.close(fig)

# ---- Part 2 backup: 1664 x 600 on the slide ----
pairs = [("64-bit addr\nlatency", "x2r_bi", "x2r_bi_d8"),
         ("0x67 prefix\nlatency", "x2a_bi", "x2a_bi_d8"),
         ("32-bit dest\nlatency", "x2b_d_bi", "x2b_d_bi_d8"),
         ("16-bit dest\nlatency", "x2b_w_bi", "x2b_w_bi_d8"),
         ("RIP-rel.*\nthroughput", "x2c_rip_0", "x2c_rip_64")]
fig, axes = plt.subplots(1, 2, figsize=(16.64, 6.0), sharey=True)
for ax, c in zip(axes, "PE"):
    x, w = np.arange(len(pairs)), 0.38
    a = [pm.val(pm.X, p[1], c) for p in pairs]
    b = [pm.val(pm.X, p[2], c) for p in pairs]
    labels(ax, ax.bar(x - w / 2, a, w, color=COLOR[c], edgecolor=BG, linewidth=3, label="no displacement"), a)
    labels(ax, ax.bar(x + w / 2, b, w, color=COLOR[c], edgecolor=BG, linewidth=3, hatch="//", alpha=0.7,
                      label="+0 displacement*"), b)
    ax.set_xticks(x)
    ax.set_xticklabels([p[0] for p in pairs], fontsize=16)
    ax.set_title({"P": "P-core · Raptor Cove", "E": "E-core · Gracemont"}[c], loc="left", fontsize=18, color=INK)
    ax.set_ylim(0, 4.3)
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="upper left", fontsize=16, frameon=False)
axes[0].set_ylabel("cycles")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig_slide_part2.png"), dpi=DPI)
plt.close(fig)
print("slide figures written to results_mine/slides/")
