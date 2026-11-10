# 5-minute talk: adding zero to an LEA

Script for the 12-slide deck: **8 slides presented** (1–8) and **4 backup slides** (9–12) that are
only reached if someone asks. Data: `zero_disp.csv`, `results_mine/compare_zero_disp.csv`,
`results_mine/vtune/uops.csv`, `realcode.csv`.

| # | slide | time |
|---|---|---|
| 1 | cover — the question | 0:20 |
| 2 | what we measure, and on what | 0:40 |
| 3 | how we measured | 0:35 |
| 4 | hypothesis: two kinds of adder | 0:45 |
| 5 | every combination, every core | 1:00 |
| 6 | our proposed pipelines | 0:40 |
| 7 | the slow form is one micro-op | 0:40 |
| 8 | AI use | 0:20 |
| | **total** | **5:00** |

> **There is no takeaway slide.** The deck ends on the micro-op result and the AI-use slide, so the
> closing line has to be spoken. Say it over slide 7, before moving on:
> *"So: a displacement of zero is not free. On two generations of Intel E-cores, any LEA with both
> an index and a displacement takes 2 cycles instead of 1, whatever the values. The P-cores don't
> care. Same chip, same instruction, different answer."*

---

## The numbers, for reference

Latency in cycles, median of 7, two CPUs per core type. 285H = Lion Cove (P), Skymont (E),
Crestmont (LP E). 13700H = Raptor Cove (P), Gracemont (E).

| parts | instruction | Lion Cove | Raptor Cove | Skymont | Gracemont | Crestmont |
|---|---|---|---|---|---|---|
| base | `[rax]` | 1 | **0.17** | 1 | 1 | 1 |
| base + disp | `[rax+0]` | 1 | **0.17** | 1 | 1 | 1 |
| base + index | `[rax+rcx*1]` | 1 | 1 | 1 | 1 | 1 |
| **index + disp** | `[rax*1+0]` | 1 | 1 | **2** | **2** | **2** |
| **base + index + disp** | `[rax+rcx*1+0]` | 1 | 1 | **2** | **2** | **2** |

Every input besides `rax` is zero, so all five produce the same value. Index alone cannot be
encoded (with no base, x86 always adds a disp32); a displacement alone has no register to chain.

Throughput, cycles per instruction: `[r14+r15]` → `[r14+r15+0]` is 0.17 → 0.17 on Lion Cove,
0.20 → 0.20 on Raptor Cove, **0.13 → 0.30** on Skymont, **0.25 → 1.00** on Gracemont and Crestmont.

---

## 1 · Cover (0:20)

Read the question off the slide: can two x86 instructions that compute the same value take
different time, only because the address is encoded differently? Our answer: yes, on some cores —
adding a displacement of zero can double the latency.

## 2 · What we measure, and on what (0:40)

- **Left:** one computation, five encodings. Every legal combination of base, index and
  displacement. `rcx` = 0 and every displacement = 0, so **all five put exactly `rax` in `rax`** and
  differ only in their bytes — three bytes for the shortest, eight for the longest.
- We write the bytes by hand because **an assembler silently drops a `+0`**.
- LEA is the right probe: it does the address arithmetic and never touches memory, so no cache
  effect can creep in.
- **Right:** five cores in three classes, two laptops. Say the class names, not the codenames —
  the colours (blue P, orange E, green LP E) carry through every later slide.

## 3 · How we measured (0:35)

Four steps, in the order the arrows show:

1. **Dependency chain** — each LEA feeds the next, so time ÷ count = latency. 200 unrolled,
   200k loops, median of 7.
2. **Exact bytes** — checked with objdump.
3. **One core at a time** — pinned with `SetThreadAffinityMask`, two CPUs per class.
4. **Calibrated cycles** — rdtsc ÷ an `add rax,rcx` chain timed right before and after, so
   frequency changes cancel.

Worth saying out loud, not on the slide: native Windows rather than WSL (WSL can't pin to a core
type, ±20% noise against ±2%), and everything repeated on a second laptop.

## 4 · Hypothesis: two kinds of adder (0:45)

This is the prediction, stated **before** the results.

- **E-core — a 2-input adder.** Input A takes the base; the index and the displacement **share**
  input B. Any two parts fit in one cycle, but an index together with a displacement needs a
  second pass.
- **P-core — a 3-input adder.** A 3-to-2 compressor feeds one adder, so base + index + displacement
  finish in one cycle; missing parts are fed in as 0.
- **So the prediction is falsifiable:** on E-cores, 2 cycles whenever an index and a displacement
  occur together, 1 otherwise, **whatever the values**. On P-cores, no difference for unscaled forms.

Say "unscaled": a ×4 or ×8 scale costs both P-cores a cycle on its own, and that is a separate
effect.

## 5 · Every combination, every core (1:00)

The main result. Let the block pattern do the work: **the three E-core columns go to 2 on the last
two rows; neither P-core ever does.**

- **Our first guess was wrong.** We expected "three parts are slow". But `[rax*1+0]` has only
  **two** parts and is still slow. The rule is **index and displacement together**.
- The displacement's **value** does not matter: 0, ±8, 127, 4096 all cost the same. Nor does its
  **length**: disp8 and disp32 are identical. The core decides from the encoded form alone and
  never notices that the displacement is zero.
- This also explains the textbook rule "LEA with RBP as the base is slow": x86 cannot encode
  `[rbp+rax*1]` without a displacement byte, so it is always secretly `[rbp+rax*1+0]`. `rsp`/`r12`,
  which need a SIB byte instead, are fast.
- If asked about the two `0.17` cells: Raptor Cove resolves a small constant at rename, before
  execution — Lion Cove does not do that for LEA. Backup slide 12.

## 6 · Our proposed pipelines (0:40)

Walk the two rows. P-core: all three parts enter together, 3-to-2 compress, add, done in cycle 1.
E-core: base + index in cycle 1, then the displacement in cycle 2 — and because the decoder routes
by encoding, **a zero displacement still takes that second cycle**.

## 7 · The slow form is one micro-op (0:40)

The question timing could not answer: is the slow form **split into two micro-ops**, or is it
**one micro-op that takes two cycles**? Both predict exactly 2 cycles on a chain.

We counted with Intel VTune on Gracemont: **1.0 micro-op, 2 cycles** — the same micro-op count as
the fast form. So the second cycle happens *inside* one micro-op; the instruction is not split.

Two controls bracket it, which is why the number is trustworthy:

- `add rax,rcx`, known to be one micro-op → measured 1.0 ✓
- 16-bit `lea ax,[rax+rcx]`, which really is cracked → measured ≈3, about 2 of them microcode ✓

So the method can detect "cracked into several", and on the `+0` form it does not.

**Do not overclaim.** This rules out the two-micro-op reading; it does **not** prove the adder is
built the way slide 6 draws it. Say: "the second cycle happens inside one micro-op, which fits our
sketch — but counters can't show how the adder is built."

**Then deliver the closing line** (see the box at the top) before moving to slide 8.

## 8 · AI use (0:20)

- **What we used Claude for:** drafting the plan, writing the harness, adding the compiler-output
  experiment and the VTune runs, drafting the write-ups and these slides.
- **Where we went further:** rejected "three address parts are slow" and tested index + disp alone;
  caught the `add rax,1` calibration error (0.17 cycles, not 1 — every result was 5–6× too high);
  caught "7 or 8 per cycle" for a 0.25-cycle throughput, which is 4; checked every number against
  the raw data.

---

## Backup slides (9–12)

| # | slide | reach for it when asked… |
|---|---|---|
| 9 | Does it replicate? A second chip. | "could this just be your one chip?" |
| 10 | Only LEA pays. | "do real loads and stores pay it too?" |
| 11 | Prefixes and sizes keep the rule. | "what about 32-bit addressing, or smaller destinations?" |
| 12 | A small constant is almost free. | "why is there a 0.17 on slide 5?" |

- **9 · Second chip.** Gracemont is one E-core generation *older* than Skymont and shows the same
  rule, so the quirk predates Arrow Lake. The throughput penalty is **worse** there: 4× (4 per cycle
  → 1) against about 2× on Skymont. Latency is 1 → 2 on both. So Skymont softened the throughput
  cost while keeping the latency cost — this looks like a deliberate trade-off, not a bug.
- **10 · Only LEA pays.** With the same address, loads, stores and `add rax,[mem]` are identical
  with and without `+0`, in latency *and* throughput, on both cores. The AGU computes the address
  for free; only the ALU charges for this form.
- **11 · Prefixes and sizes.** The rule survives the `0x67` prefix (32-bit addressing) and a 32-bit
  destination, so it is not about the 64-bit adder width. RIP-relative is unaffected by its
  displacement value. A 16-bit destination is slow for *every* form (2 cycles on the P-core,
  ≈3.6 on Gracemont) and so hides the `+0` effect entirely.
- **12 · Small constants.** On Raptor Cove, `lea rax,[rax+k]` and `add rax,k` behave identically:
  0.17 cycles for k = 0 or ±1, 0.33 at 127/128, 0.52 at 1023/−1024, and a normal 1.00 from 1024 on.
  Only the **value** matters, not disp8 vs disp32 — the exact mirror of the E-core effect, which
  depends on the **encoding** and ignores the value. One core reads the value, the other reads the form.

---

## Q&A bank (no slide)

**"One cycle — who cares?"** We measured gcc `-O2` output too (`realcode.csv`, emitted assembly in
`codegen/real_kernels.s`). Cycles per loop iteration:

| compiler-generated loop | P | E | LP-E |
|---|---|---|---|
| `x = x + y*4 + 8`, the `lea` on the loop-carried chain | 2.00 | 2.01 | 2.02 |
| the same, restructured so only an `add` is on the chain | **1.00** | **1.48** | 2.11 |
| `a[idx[k]+1]`, the same addressing form inside a **load** | 1.02 | 1.07 | 1.76 |
| `a[idx[k]]`, the same load without the displacement | 1.02 | 1.06 | 1.75 |

A clean 2× when scaled address arithmetic sits on a loop-carried chain, and restructuring the source
recovers it — except on the LP E-core, which is narrow enough that the extra instruction costs what
the shorter chain saves. Inside a load's addressing mode the displacement is **free** on every core.
And **gcc never emits the scale-1 form this talk is named after**: for `x + y + 8` it emits
`add` + `add imm`, so the pure `[rax+rcx*1+0]` effect is not reachable from C — which is why it has
gone unnoticed. But gcc does emit the scaled 3-component LEA, `-march=gracemont` included.

**"Could it be X?"**

| alternative | why not |
|---|---|
| instruction length / fetch | disp8 and disp32 cost the same; `[rax+0]` as disp32 (7 B) is fast while `[rax+rcx*1+0]` as disp8 (5 B) is slow |
| the index multiply `*1` | every index form has `*1`; `[rax+rcx*1]` is fast, and on E-cores even `*4` costs no latency |
| register values | with `rcx` = 0 and disp = 0 every form computes exactly `rax`; timings don't move |
| frequency / turbo | per-measurement `add rax,rcx` calibration; `imul` comes out at expected integers |
| noise | 7 reps, two CPUs per core type, agreement within ±2% |
| a bug in our harness | every value matches uops.info (ARL-P, ARL-E, MTL-E) |
| just this one chip | replicated on a second chip, one E-core generation older (slide 9) |
| the 64-bit adder width | the `0x67` prefix and a 32-bit destination still pay (slide 11) |

**Calibration mistake worth admitting.** The AI-drafted plan said to calibrate with `add rax,1`. On
these cores that costs about 0.17 cycles, not 1, because the renamer folds immediate adds — every
result came out 5–6× too high. A second sanity check (`imul` should be 3 cycles) caught it, and the
reference became `add rax,rcx`.

## Limitations, if pressed

- Cycles are rdtsc-calibrated, not read from a core-cycle counter.
- Micro-op counts were taken on the **13700H only** (Gracemont and Raptor Cove). Skymont, Crestmont
  and Lion Cove were never micro-op-counted; we infer they behave the same because their timing does.
- VTune's E-core counts are noisy — single rounds of the 1-micro-op rows range 0.91–1.19, and
  background work on the pinned CPU leaks in — so the second decimal means nothing. But no round of
  the slow form came near 2, which is all the 1-vs-2 question needs.
- No per-port counters on Windows, so **why** that micro-op needs a second cycle is still a hypothesis.
- "Crestmont" for the 285H's LP E-core is inferred from matching uops.info's Meteor Lake-E rows.
- Still open: the 13700H P-core did only 2 loads per cycle where Intel documents 3.
