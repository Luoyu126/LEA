# 5-minute talk: adding zero to an LEA

Figure: `fig_zero_disp_simple.png`. Data: `zero_disp.csv`.

## The result

| | P-core | E-core | LP E-core | P-core (2nd chip) | E-core (2nd chip) |
|---|---|---|---|---|---|
| `lea rax,[rax+rcx*1]` | 1 | 1 | 1 | 1 | 1 |
| `lea rax,[rax+rcx*1+0]` (1-byte or 4-byte zero) | 1 | **2** | **2** | 1 | **2** |

Latency in cycles. The two instructions are functionally identical: same registers, same result.
The only difference is an encoded displacement of zero. Measured on an Intel Core Ultra 9 285H
(Arrow Lake: Lion Cove, Skymont, Crestmont), which has all three core types on one chip, and
replicated on an i7-13700H (Raptor Lake: Raptor Cove and Gracemont, one E-core generation older).

### Every base / index / disp combination (scale 1), all computing exactly `rax`

| parts present | instruction | P-core | E-core | LP E-core |
|---|---|---|---|---|
| base | `lea rax,[rax]` | 1 | 1 | 1 |
| base + disp | `lea rax,[rax+0]` | 1 | 1 | 1 |
| base + index | `lea rax,[rax+rcx*1]`, rcx = 0 | 1 | 1 | 1 |
| **index + disp** | `lea rax,[rax*1+0]` | 1 | **2** | **2** |
| **base + index + disp** | `lea rax,[rax+rcx*1+0]`, rcx = 0 | 1 | **2** | **2** |
| index only | not encodable: with no base, x86 always adds a disp32 | – | – | – |
| disp only | `lea rax,[0]`: no register input, so no latency chain | – | – | – |

Every input besides `rax` is zero, so all forms produce the same value. On E-cores the slow forms
are exactly those with **both an index and a displacement**. The number of parts doesn't matter:
index + disp is only two parts and is still slow. Values don't matter either (a zero index, a zero
displacement, or 8 / -8 / 127 / 4096 all behave the same): the core decides from the encoded form alone.
`[rax+rcx+rcx]` (two indexes) and `[rax+0+0]` (two displacements) can't be encoded; an address has at
most one base, one index and one displacement.

Every index is written with its scale `*1`: the encoding always stores a scale for the index, and
all these forms use 1, so multiplying by 1 is the same in every row and can't explain the difference.
Writing `rax*1` is also how you tell the assembler to put rax in the *index* slot: `[rax+0]` (rax as
base) is 1 cycle, `[rax*1+0]` (rax as index) is 2 on E-cores, though both compute rax + 0.

## 1. Question (0:30)

Can functionally equivalent x86 instructions differ in speed only because of how the address is
written? The literature says complex LEAs can be slow. So we asked: what is the smallest possible
change to an addressing mode that still costs time?

## 2. Method (1:00)

- Dependency chain: each LEA's result feeds the next one, so total time / count = latency.
  The loop is unrolled 200x and run 200k times, repeated 7 times, and we report the median.
- Encodings are written byte by byte (`48 8D 04 08` vs `48 8D 44 08 00`, i.e. `[rax+rcx*1]` vs
  `[rax+rcx*1+0]`) and checked with objdump,
  because an assembler would silently drop a `+0`.
- Each run is pinned to one core (Windows `SetThreadAffinityMask`), so P-, E- and LP E-cores are
  measured separately.
- Cycles come from rdtsc, calibrated against an `add rax,rcx` chain (known to be 1 cycle).
- AI-use example: the AI-drafted plan said to calibrate with `add rax,1`. On this CPU that takes
  0.17 cycles, not 1, because newer cores optimize it away early, so every result came out
  5-6x too high. We caught it with a second sanity check (`imul` should be 3 cycles) and fixed
  the reference.

## 3. Result (2:00)

- E-cores: adding a zero doubles latency, from 1 to 2 cycles. Throughput also falls: 0.14 → 0.30
  cycles/instr on the E-core, 0.25 → 1.00 on the LP E-core.
- P-core: no difference.
- The value of the displacement doesn't matter: +0, +8, -8, +127 and +4096 are all equally slow.
  Its presence is the trigger. The core classifies the LEA by its encoded form and never notices
  that the displacement is zero.
- Exhaustive control (all forms compute exactly `rax`): base, base + disp and base + index take
  1 cycle; index + disp and base + index + disp take 2 on E-cores. Our first guess, "three parts
  are slow", was wrong: `[rax*1+0]` has two parts and is slow. The rule is **index and
  displacement together**. The P-core handles every combination in 1 cycle.
- It isn't the `*1` either: `[rax+rcx*1]` has the same index×1 and is fast. Even a real scale
  costs no latency on E-cores (`[rax+rcx*4]` = 1 cycle), only throughput (1 per cycle).
- Possible reading (hypothesis): on E-cores the index input and the displacement don't share a
  single-step path, so combining them takes a second step. **Micro-op counters say that step is not
  a second micro-op**: on Gracemont the slow form is 1.0 micro-op and still takes 2 cycles, so the
  extra cycle happens inside one micro-op (Abby's extension, Part 4 — VTune, with `add rax,rcx` as
  a known 1-micro-op control).
- This also explains a textbook rule: "LEA with RBP as the base is slow." x86 cannot encode
  `[rbp+rax*1]` without a displacement byte, so it is always secretly `[rbp+rax*1+0]`.
- **It replicates on a second chip, one generation older.** On an i7-13700H (Gracemont E-core) the
  same rule holds exactly, and the throughput penalty is worse: 4 per cycle → 1 per cycle (4×),
  against about 2× on Skymont. So the quirk predates Arrow Lake, and Skymont softened the
  throughput cost while keeping the latency cost.
- **Only LEA pays.** With the same address, loads, stores and `add rax,[mem]` are identical with
  and without `+0` — in latency *and* throughput, on both cores. The address arithmetic is free when
  the load unit's own adder does it; only the ALU charges for it.

## 4. Alternate hypotheses (1:00)

| Could it be... | Why not |
|---|---|
| Longer instruction / instruction fetch | A 1-byte and a 4-byte zero cost the same. `[rax+0]` with a 4-byte zero (7 bytes) is fast, while `[rax+rcx*1+0]` with a 1-byte zero (5 bytes) is slow. |
| The index multiplication (`*1`) | Every index form has `*1`; `[rax+rcx*1]` is fast. On E-cores even `*4` costs no latency. |
| Register values | With rcx = 0 and disp = 0 every form computes exactly rax, and the timings don't change. |
| Frequency changes | Each measurement is calibrated against a 1-cycle add chain. |
| Noise | 7 repetitions, 2 different CPUs per core type, agreement within 6%. |
| P/E cores mixed | Each run is pinned to one logical CPU. |
| A bug in our harness | Same numbers as uops.info (ARL-E / MTL-E: 2 cycles, ARL-P: 1 cycle). |
| Something about this one chip | Replicated on a second laptop (i7-13700H, Gracemont): same rule, same numbers. |
| The 64-bit adder width | The `0x67` prefix (32-bit addressing) and a 32-bit destination still pay. |

## 5. Takeaway (0:30)

A displacement of zero is not free. On two generations of Intel E-cores, any LEA with both an index
and a displacement takes 2 cycles instead of 1, whatever their values, even when the result is just
`rax`. The P-cores don't care, and neither do real loads and stores with the same address.
Same chip, same instruction, different answer.

Limitation: we know the slow form is **one micro-op that takes two cycles**, not two micro-ops, but
*why* that micro-op needs a second cycle is still our hypothesis. Micro-op counters can't show how
the adder is built, and there are no per-port counters on Windows, so we can't see inside the core.
Still open: on the i7-13700H the P-core did only 2 loads per cycle where Intel documents 3, and we
don't know why.

## Backup slide — "one cycle, who cares?"

Not in the 5 minutes; this is the answer to the question we will get. Full table in
`SUMMARY.md` Exp 5, data in `realcode.csv`, emitted assembly in `codegen/real_kernels.s`.

We measured gcc `-O2` output, not hand-written assembly. Cycles per loop iteration:

| compiler-generated loop | P | E | LP-E |
|---|---|---|---|
| `x = x + y*4 + 8` — the LEA is on the loop-carried chain | 2.00 | 2.01 | 2.02 |
| the same, restructured so only an `add` is on the chain | **1.00** | **1.48** | 2.11 |
| `a[idx[k]+1]` — the same addressing form inside a **load** | 1.02 | 1.07 | 1.76 |
| `a[idx[k]]` — the same load without the displacement | 1.02 | 1.06 | 1.75 |

Three things to say:

- **It is real: a clean 2× on a dependency chain**, and restructuring the source recovers it
  (2.00 → 1.00 on the P-core). On the LP E-core the fix doesn't help — that core is narrow enough
  that the extra instruction costs what the shorter chain saves.
- **Inside a load's addressing mode the displacement is free** on every core. The AGU computes it;
  only the ALU charges for it. So this is not a reason to rewrite your array code.
- **gcc never emits the scale-1 form** we built the talk around: for `x + y + 8` it emits
  `add` + `add imm`. The 3-component LEA shows up only with a real scale factor — which is
  exactly why this effect has gone unnoticed. (And in that case the P-core also pays 2 cycles,
  but for its own reason: the scale, not the displacement.)

So: it costs a cycle only when scaled address arithmetic sits on a loop-carried chain. Narrow
window — but gcc walks into it, `-march=gracemont` included.

## The deck's other backup slides (extension, i7-13700H)

Full write-up and caveats: `results_mine/FINDINGS.md`. One line each, for questions:

- **`bk_uops` — micro-op counts.** `lea rax,[rax+rcx+0]` on Gracemont: 1.0 micro-op, 2 cycles.
  Control `add rax,rcx` came out at 1.0 as it must. 16-bit `lea ax,...` is a different animal:
  ≈3 micro-ops on Gracemont, ≈2 of them from the microcode ROM, and 2 micro-ops (no microcode)
  on the P-core. If pressed on precision: the E-core rounds scatter about ±0.1–0.2 and background
  work on the pinned CPU leaks in, so the second decimal means nothing — but no round came near 2,
  which is all the 1-vs-2 question needs.
- **`bk_modes` — prefixes and operand sizes.** The rule survives the `0x67` prefix (32-bit
  addressing) and a 32-bit destination, so it is not about the 64-bit adder width. RIP-relative is
  unaffected by its displacement value. A 16-bit destination is slow for *every* form (2 cycles on
  the P-core, ≈3.6 on Gracemont) and so masks the `+0` effect entirely.
- **`bk_fold` — the opposite effect on the other core.** The Raptor Cove P-core adds a small
  constant almost for free: `lea rax,[rax+k]` and `add rax,k` both run at 0.17 cycles for k = 0, ±1,
  rising to 1.00 from k = 1024 on. Only the **value** matters, not disp8 vs disp32 — the exact
  mirror image of the E-core effect, which depends on the **encoding** and ignores the value.
  Lion Cove on the 285H does not do this for `lea`. This is the cleanest one-slide way to say
  "one core reads the value, the other reads the form."
