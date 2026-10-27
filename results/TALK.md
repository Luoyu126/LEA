# 5-minute talk: adding zero to an LEA

Figure: `fig_zero_disp_simple.png`. Data: `zero_disp.csv`.

## The result

|  | P-core | E-core | LP E-core |
|---|---|---|---|
| `lea rax,[rax+rcx*1]` | 1 | 1 | 1 |
| `lea rax,[rax+rcx*1+0]` (1-byte or 4-byte zero) | 1 | **2** | **2** |

Latency in cycles. The two instructions are functionally identical: same registers, same result.
The only difference is an encoded displacement of zero. Measured on an Intel Core Ultra 9 285H
(Arrow Lake), which has all three core types on one chip.

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
  single-step path, so combining them takes a second step. We can't tell whether that step is a
  second micro-op or one micro-op that takes 2 cycles; timing alone predicts 2 cycles for both.
- This also explains a textbook rule: "LEA with RBP as the base is slow." x86 cannot encode
  `[rbp+rax*1]` without a displacement byte, so it is always secretly `[rbp+rax*1+0]`.

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

## 5. Takeaway (0:30)

A displacement of zero is not free. On Intel E-cores, any LEA with both an index and a
displacement takes 2 cycles instead of 1, whatever their values, even when the result is just
`rax`. The P-core on the same chip doesn't care. Same chip, same instruction, different answer.

Limitation: the internal mechanism (why index + displacement is slower on E-cores) is a
hypothesis. Windows exposes no per-port counters, so we can't see inside the core.
