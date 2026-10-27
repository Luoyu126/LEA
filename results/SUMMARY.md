# x86 addressing-mode timing — results (native Windows, Intel Core Ultra 9 285H)

Raw data: `results.csv` (216 rows), per-core raw output in `raw/`, reference values in
`uops_info_reference.csv`, compiler output in `codegen/`, figures `fig_exp*.png`.
Reproduce: `harness\run_all.py` (build + run, ~2 min) then `harness\plot.py`.

## Focus for the talk: `lea rax,[rax+rcx]` vs `lea rax,[rax+rcx+0]`

Data: `zero_disp.csv` (2 logical CPUs per core type: P = 0,10; E = 2,6; LP-E = 14,15; the two CPUs
of a type agree within 6%). Figure: `fig_zero_disp.png`. All encodings forced with `.byte` /
`{disp8}` and checked with objdump.

| form (latency, cycles) | P | E | LP-E |
|---|---|---|---|
| `[rax+rcx]` | 1 | 1 | 1 |
| `[rax+rcx+0]` disp8 / disp32 | 1 | **2** | **2** |
| `[rax+rcx+8]`, `-8`, `+127`, `+4096` | 1 | **2** | **2** |
| `[rax]`, `[rax+0]` disp8 / disp32 (no index) | 1 | 1 | 1 |
| `[rbx+rax]` | 1 | 1 | 1 |
| `[rbp+rax+0]`, `[r13+rax+0]` (disp forced by the ISA) | 1 | **2** | **2** |

| form (throughput, cycles/instr) | P | E | LP-E |
|---|---|---|---|
| `[r14+r15]` | 0.17 | 0.14 | 0.25 |
| `[r14+r15+0]` disp8 / disp32 | 0.17 | **0.30** | **1.00** |

What this shows:
- Two **functionally identical** instructions (same registers, same result) differ 2× in latency on
  E-cores, and 2.2× / 4× in throughput. Only the encoding of the addressing mode differs.
- The trigger is **an index and a displacement field together**. Exhaustive check with every input
  except rax set to zero: base, base+disp, base+index = 1 c; index+disp (`[rax*1+0]`, no base) and
  base+index+disp = 2 c on E/LP-E (1 c on P). So it is not "three parts": index+disp has two.
  The displacement's value (0, ±8, 127, 4096), sign and size (1 or 4 bytes) do not matter, and nor does
  the index register's value (rcx = 0 behaves like rcx = 1).
  → the core classifies the LEA by its encoded *form*, not by what it computes; it does not check
  for a zero displacement or a zero index.
- Instruction length is ruled out: `[rax+0]` disp32 (7 bytes) is fast, `[rax+rcx+0]` disp8 (5 bytes) is slow.
- The well-known "RBP/R13-based LEA is slow" rule is this same effect: x86 cannot encode rbp/r13 as a
  base without a displacement byte, so `[rbp+rax]` is always really `[rbp+rax+0]`. rsp/r12 (which need a
  SIB byte instead) are fast.
- The P-core (Lion Cove) shows no effect at all → it depends on the microarchitecture.
- Consistent with uops.info: ARL-E / MTL-E list base+index+disp8 at 2 cycles; ARL-P at 1.
- Mechanism (hypothesis, not observable without uop/port counters): on Skymont/Crestmont the index
  input and the displacement cannot be combined in a single step, so that combination takes a second
  step (or a restricted unit), and the decoder picks that path from the encoding alone.

## Setup

- One CPU, three microarchitectures: CPU 0 = P-core (Lion Cove), CPU 2 = E-core (Skymont),
  CPU 14 = LP E-core (behaves exactly like uops.info's Meteor Lake-E, i.e. Crestmont).
  Core type identified via Windows `GetSystemCpuSetInformation` EfficiencyClass + clock speed;
  each run pinned with `SetThreadAffinityMask`, high priority.
- Kernel = loop with 200 unrolled instructions × 200k iterations; 7 reps, median/min/max.
- Cycles = rdtsc ticks ÷ ticks of an `add rax,rcx` chain (1 cycle) measured right before and after,
  so frequency changes cancel. Spread is typically within ±2%.
- **The plan's sanity check was wrong for this CPU**: `add rax,1` chains run at 0.17 c (P) / 0.24 c (E),
  because newer cores fold immediate adds at rename. Using it as the 1-cycle reference made `imul`
  look like 16.5 cycles. Reference switched to `add rax,rcx`; `imul` then measures 3 / 4 / 5 c
  (P / E / LP-E), as expected.

## Exp 1 — LEA latency (cycles)

| form | P | E | LP-E |
|---|---|---|---|
| base, base+disp8/disp32, base+index | 1 | 1 | 1 |
| base+index×4 / ×8 | **2** | 1 | 1 |
| index×4+disp (no base) | **2** | **2** | **2** |
| base+index+disp | 1 | **2** | **2** |
| base+index×4+disp | **2** | **2** | **2** |
| rbp+index, r13+index | 1 | **2** | **2** |

Base path and index path give the same numbers. Every value matches uops.info (ARL-P / ARL-E / MTL-E).
**Answer to the question: yes, addressing form changes LEA time — but *which* form is slow depends on
the core.** P-core: a scale factor costs. E-cores: a displacement field (3 components) costs.
Skylake's "3-component LEA = 3 cycles" rule does not apply to any core here.

## Exp 3 — equivalent encodings (same result)

- **A** `[rax+rax]` = 1 c everywhere; `[rax*2+0]` = 2 c everywhere. The "simpler" form
  is slower, because the no-base form is really index×scale+disp32.
- **B** `[rax+rcx]` vs the same with disp8=0 vs disp32=0: P-core 1/1/1; E and LP-E 1/**2/2**.
  The *presence* of a displacement field matters even when its value is 0; its *length* (1 vs 4 bytes)
  does not → it is a form/decoder-classification effect, not instruction length or fetch.
- **C** rsp/r12 as base (need a SIB byte) = no penalty; rbp/r13 as base (need a disp8) = 2 c on E/LP-E.
  Same mechanism as B: rbp/r13 are slow *because* they force a displacement.
- **D** `lea [rax*4]` = 2 c vs `shl rax,2` = 1 c; `lea [rax+rcx]` = `add rax,rcx` = 1 c.
- **E** `lea [rax+rcx+8]` vs split `lea + add 8`: P 1 c vs 1 c (the add imm is folded, free);
  E/LP-E 2 c vs 2 c — splitting does not help. Hoisting the loop-invariant part
  (`lea rdx,[rcx*4+8]` once, then `add rax,rdx`) does: 2 c → 1 c on all cores.
- gcc 16 `-O2` keeps the single 3-component LEA for `a+b*4+8` with every `-march` tried
  (native=arrowlake, skylake, alderlake, gracemont, x86-64, even bonnell/silvermont).

## Exp 4 — load-use latency, same address for every form (cycles)

| form | P | E | LP-E |
|---|---|---|---|
| [base], [base+disp8] | 4 | 4 | **3** |
| [base+index], [base+index×8], [base+disp32], [base+index+disp] | 4 | 4 | 4 |

On P and E the addressing mode does not affect load latency at all, whereas the LEA latency for
the same forms varies 1–2 c. LP-E has a 3-cycle fast path only for simple base(+small disp).
**LEA timing is therefore not a proxy for memory-addressing cost** (ALU vs AGU are separate hardware).

## Exp 2 — LEA throughput (cycles/instr, 8 independent chains)

| form | P | E | LP-E |
|---|---|---|---|
| base / +disp8 / base+index | 0.17 (6/cycle) | 0.13 (~7/cycle) | 0.25 (4/cycle) |
| scaled-index forms | 0.33 (3/cycle) | **1.0 (1/cycle)** | **1.0** |
| base+index+disp, rbp/r13+index | 0.17 | 0.30 | **1.0** |
| rip-relative | 0.33 | 0.25 | 0.25 |

Notable: on the E-core, `[base+index*4]` has *1-cycle latency but only 1/cycle throughput* — the
slow-throughput and slow-latency classes are different sets of forms.

**Port inference (no port counters on Windows — this is inference, not measurement).**
Interleave a LEA 1:1 with an instruction of known class and compare to each alone:
on the P-core, scaled LEA + `imul` = 0.69 c/pair and + `shlx` = 0.67 c/pair ≈ the sum of each alone
(0.33 + 0.33), while + `add` = 0.35 c. So slow LEAs on Lion Cove compete for the same ~3 execution
ports as multiply and shift, while fast LEAs can use all 6 ALUs.

## Alternate hypotheses — how each was handled

| alternative | result |
|---|---|
| frequency / turbo | per-measurement `add rax,rcx` calibration; `imul` comes out at expected integers |
| encoding length / front end | Exp 3B: disp8 vs disp32 identical → length is irrelevant |
| loop overhead | empty loop = 0.005 c/instr |
| noise | 7 reps; min–max typically ±2% |
| P/E mixing | pinned to one logical CPU per core type, reported separately |
| LEA ≠ memory addressing | Exp 4: load latency is flat where LEA varies |
| microarchitecture | three core types measured; every LEA value matches uops.info |
| bad calibration reference | caught: `add rax,1` is folded at rename on P/E cores |

## Limitations

- Cycles are rdtsc-calibrated, not read from a core-cycle counter (ETW `UnhaltedCoreCycles` exists on
  Windows but needs admin; not done).
- No port-level counters on Windows (needs VTune or native Linux) → port claims are by interference.
- One logical CPU per core type; laptop ran on battery, Balanced power plan.
- "LP-E = Crestmont" is inferred from matching uops.info MTL-E numbers, not from documentation.

## AI-usage notes for the talk

- The plan (LLM-assisted) assumed `add rax,1` = 1 cycle and Skylake-style 3-cycle 3-component LEAs;
  both were wrong for this CPU. Caught by the `imul` sanity check and by checking uops.info.
- Bugs hit while building the harness with AI: `long` being 32-bit on Windows in the codegen test
  (gave `lea eax` instead of `lea rax`), missing `_WIN32_WINNT` for the CPU-set API. Designed around:
  Win64 passes the first argument in rcx, which the kernels use as an operand → loop counter moved to r11.
