# Adding zero to an LEA: does it replicate on Raptor Lake?

An extension of the study in `../README.md` (Abby Xiong and Yunyi Chen), run on a second laptop:
an **Intel Core i7-13700H (Raptor Lake)** with 6 hyperthreaded P-cores (**Raptor Cove**) and 8
E-cores (**Gracemont**). The students measured an Intel Core Ultra 9 285H (Arrow Lake: Lion Cove
P-cores and Skymont E-cores). Gracemont is the E-core generation *before* Skymont.

**Short answer:** yes, it replicates. On Gracemont, `lea rax,[rax+rcx+0]` takes **2 cycles** while
`lea rax,[rax+rcx]` takes **1**, even though both compute the same thing. On the P-core both take 1.
So the slowdown **existed before Arrow Lake**, and on Gracemont it is even harsher for throughput.
It only affects `lea`. Stores, loads and `add rax,[mem]` don't care about a zero displacement.

## How I measured (same method as the students)

- Same harness (`../harness/`), unchanged except for two things. `run_all.py` gained an `--outdir`
  option so nothing in `../results/` gets overwritten. New kernels live in `gen_ext.py`
  (names start with `x`).
- **Which CPU is which.** `bench list` reports Windows' efficiency class. On this laptop it is the
  reverse of the 285H: **CPUs 0–11 are P-cores** (6 cores × 2 threads; CPUs 0+1 share a core,
  2+3 share a core, and so on) and **CPUs 12–19 are E-cores**. I used **P = CPU 2 and CPU 8**
  (two different physical cores, one thread each; I skipped CPU 0 because Windows handles a lot of
  background interrupts there) and **E = CPU 12 and CPU 16** (one from each 4-core E-cluster).
- Each instruction is repeated in a chain (each one waits for the last), 200 per loop × 200,000
  loops, median of 7 runs. Timer ticks are turned into cycles by comparing with `add rax,rcx`,
  which takes exactly 1 cycle.
- **Every new encoding is written byte by byte and checked by disassembling it.** The full listing
  is in `encodings.txt`. All 340 instructions decode to what their labels say.
- The two CPUs of each type agree to within 0.05 cycles on 491 of 500 rows. The other 9 differ by
  at most 0.07, except one at 0.13 (`e3E_lea3s`, `e4_*`, `e2_b`, a few mixes, `x3f_bi_d8`). None of
  these changes a conclusion, so the tables below show one number per core type.
- Toolchain: WinLibs gcc 16.2, Python 3.12, Windows 11. The first full run of Part 1 was on battery
  and everything else was on AC power. The CPU clock differed by ~35% between those runs, yet the
  kernels that appear in both runs gave identical cycle counts, so the calibration works.

## Part 1: replication

Full table for every kernel: `compare_results.csv` and `compare_zero_disp.csv`. Figure:
`fig_mine_replication.png`.

| `lea` latency (cycles) | my P (Raptor Cove) | my E (Gracemont) | their P (Lion Cove) | their E (Skymont) |
|---|---|---|---|---|
| `[rax+rcx]` | 1 | 1 | 1 | 1 |
| `[rax+rcx+0]` disp8 / disp32 | 1 | **2** | 1 | **2** |
| `[rax+rcx+8]`, `-8`, `+127`, `+4096` | 1 | **2** | 1 | **2** |
| `[rax+rcx+0]` with rcx = 0 | 1 | **2** | 1 | **2** |
| `[rax*1+0]` (index + disp, no base) | 1 | **2** | 1 | **2** |
| `[rbp+rax+0]`, `[r13+rax+0]` | 1 | **2** | 1 | **2** |
| `[rax]`, `[rax+0]` (no index) | **0.17** | 1 | 1 | 1 |
| `[rax+rcx*4]` | 2 | 1 | 2 | 1 |

| `lea` throughput (cycles per instruction) | my P | my E | their P | their E |
|---|---|---|---|---|
| `[r14+r15]` | 0.20 | 0.25 | 0.17 | 0.13 |
| `[r14+r15+0]` | 0.20 | **1.00** | 0.17 | **0.30** |

**What matched the students:**
- Their rule holds exactly on Gracemont: **an index and a displacement field encoded together cost a
  second cycle**, whatever the displacement's value, sign or size, and whatever the index's value.
  It is not about "three parts": `[rax*1+0]` has two parts and is still slow.
- The P-core shows no `+0` penalty, and pays a cycle for a scale factor (×4, ×8), just like Lion Cove.
- Splitting a slow `lea` into `lea`+`add` doesn't help on E. Hoisting the constant out of the loop does
  (2 → 1 cycle).
- All the students' Exp 1 and Exp 3 latencies matched, except the P-core's `[rax]` and `[rax+8]`,
  which my P-core runs almost for free (next section).

**What's different on my chip:**
- **Throughput is hit 4× on Gracemont** (0.25 → 1.00): only one such `lea` per cycle, versus 4 per
  cycle for the fast form. The students' Skymont lost only about 2×. Gracemont looks like their
  LP E-core (Crestmont) here. Skymont seems to have softened the throughput penalty while keeping
  the latency one.
- **My P-core does `lea rax,[rax]` and `lea rax,[rax+0]` almost for free** (0.17 cycles, i.e. about 6
  per cycle). It treats them as "copy plus small constant" and resolves them before execution, the
  same trick that makes `add rax,1` free. Their Lion Cove did not do this for `lea` (1 cycle). See the
  bonus result below for which constants qualify.
- Gracemont does *not* fold `add rax,1` (1.0 cycle; Skymont 0.24).
- Other side differences: load-use latency is 5 cycles on my P-core (4 on theirs). `imul` latency is
  5 cycles on my E-core (4 on theirs). RIP-relative `lea` on my P-core runs only 1 per cycle (theirs 3).

## Part 2: new `lea` address modes

Figure: `fig_mine_part2_lea_modes.png`. Data: `extension.csv` (experiments X2A–X2F).

| `lea` form | P no disp | P +0 | E no disp | E +0 |
|---|---|---|---|---|
| 64-bit address `[rax+rcx]` (reference) | 1 | 1 | 1 | **2** |
| **0x67 prefix** (32-bit address) `lea rax,[eax+ecx]` | 1 | 1 | 1 | **2** |
| 0x67, base only `lea rax,[eax]` | 1 | 1 | 1 | 1 |
| 0x67 + 32-bit dest `lea eax,[eax+ecx]` | 1 | 1 | 1 | **2** |
| **32-bit destination** `lea eax,[rax+rcx]` | 1 | 1 | 1 | **2** |
| **16-bit destination** `lea ax,[rax+rcx]` | 2 | 2 | **3.6** | **3.6** |
| **index only** `[rax]` vs `[rax*1+0]`* | 0.17 | 1 | 1 | **2** |
| index only `[rax*4+0]`, `[rax*8+0]` | – | 2 | – | 2 |
| 0x67 throughput `[r14d+r15d]` (cycles/instr) | 0.20 | 0.20 | 0.25 | **1.00** |
| **RIP-relative** throughput `[rip+0]` vs `[rip+64]`** | 1.00 | 1.00 | 0.27 | 0.27 |

\* There is no way to encode "index, no base, no displacement": x86 always adds a 4-byte displacement
when there is no base. So the "no disp" column is the same-value form `[rax]`.
\** RIP-relative always carries a 4-byte displacement, so I compared 0 with 64. It also reads no
register, so you can't chain it to measure latency; only throughput is possible.

**What's new:**
- **The rule survives the 0x67 prefix and smaller destinations.** 32-bit addressing and a 32-bit
  result both still pay the second cycle on Gracemont for index + displacement. So the slowdown sits
  in how the core handles the address *form*, not in the 64-bit adder width.
- **RIP-relative is unaffected.** Its displacement value doesn't matter on either core.
- **16-bit destinations are slow everywhere, and they hide the `+0` effect.** `lea ax,...` takes
  2 cycles on the P-core and about 3.6 on Gracemont for *every* form. On Gracemont its throughput is
  also about 3.6 cycles per instruction, even with 8 independent chains. That suggests 16-bit `lea`
  goes down a separate slow path on that core, possibly microcode. Writing a 16-bit register has to
  merge with the old upper bits, which costs extra. I can't tell the exact mechanism from timing
  alone.
- **0x67 switches off the P-core's free `lea`.** `lea rax,[rax]` is 0.17 cycles, but `lea rax,[eax]`
  and `lea eax,[rax]` are 1 cycle. Truncating to 32 bits needs real work.

**Bonus: which constants does the P-core fold for free?** (X2F)

| constant in `lea rax,[rax+k]` or `add rax,k` | P-core cycles | E-core |
|---|---|---|
| 0, ±1 | 0.17 | 1 |
| 127, 128 | 0.33 | 1 |
| 1023, −1024 | 0.52 | 1 |
| 1024, −1025, 2047, 4096 | 1.00 | 1 |

`lea` and `add` behave identically. Whether the constant is stored in 1 or 4 bytes doesn't matter;
only its **value** does. Anything in −1024…1023 gets the shortcut, and bigger steps within that
range cost more (my guess: a small running-offset counter at rename overflows sooner). This is the
opposite of the E-core effect, which depends on the **encoding** and not the value.

## Part 3: other instructions with and without a zero displacement

Figure: `fig_mine_part3_other_instrs.png`. Data: `extension.csv` (experiments X3*). Index register
`r8` = 0, so all forms touch the same address.

| instruction (form `[b+i]` vs `[b+i+0]`) | P no disp | P +0 | E no disp | E +0 |
|---|---|---|---|---|
| store `mov [rdi+r8],rax`, throughput | 0.50 | 0.50 | 0.50 | 0.50 |
| load `mov r,[r10+r8]`, throughput | 0.50 | 0.50 | 0.50 | 0.50 |
| load-use latency `mov rax,[rax+r8]` | 5 | 5 | 4 | 4 |
| `add rax,[rax+r8]`, address on chain | 6 | 6 | 5 | 5 |
| `add rax,[r10+r8]`, register on chain | 1 | 1 | 1 | 1 |
| `add r,[r10+r8]`, throughput | 0.50 | 0.50 | 0.50 | 0.50 |
| store→load pair `[rdi+r8]` | 5.0 | 5.0 | ~4.6 | ~4.8 |

I also tested base only, `+0` as disp8 or disp32, scaled `*8`, and index only: same picture.

**What's new:**
- **A zero displacement costs nothing for real memory instructions on either core.** Stores, loads
  (latency *and* throughput) and `add` with a memory operand are identical with and without `+0`.
  Only `lea` has the penalty. This confirms the students' point that `lea` timing tells you nothing
  about memory-address cost, and now it holds for throughput and stores too.
- **Gracemont's 3-cycle fast load path depends on the index, not the displacement.** `[rax]`,
  `[rax+0]` (even as disp32) and `[rax+8]` load in 3 cycles. Anything with an index (including
  index-only) takes 4. `[rax+4096]` also takes 4, so the shortcut seems to need a *small*
  displacement value.
- **That fast path doesn't apply to `add rax,[mem]`.** It costs load + 1 = 5 cycles even for `[rax]`
  (a plain load is 3).
- **Store→load forwarding gets skipped entirely for simple addresses.** With `[rdi]` or `[rdi+0]`, a
  store then a load of the same spot costs only 0.5 cycles per pair, so the load never waits for the
  store. With `[rdi+r8]` it costs the normal ~5. Index-only `[rdi*1+0]` gets the shortcut on
  Gracemont (0.6) but not on Raptor Cove (5.0). Again the displacement doesn't matter, only the base
  and index. The E-core `[rdi+r8]` numbers are noisy (±30–50% between runs).
- **Open question:** my P-core does only 2 loads per cycle in these tests. Intel documents 3 for
  Raptor Cove. Loads to 8 different cache lines and 32-bit loads give the same 0.50
  (`extension_loadcheck.csv`), so the cause isn't the shared address. I couldn't find the reason
  from timing alone. It doesn't affect the with/without comparison.

## Part 4: micro-op counts (not done: VTune is not installed)

The question: on Gracemont, is `lea rax,[rax+rcx+0]` **two micro-ops** (split in two) or **one
micro-op that takes 2 cycles**? Timing can't separate these. A micro-op counter can.

To install and run it:
1. Download **Intel VTune Profiler** (standalone, free) from Intel's oneAPI download page and run the
   installer. It needs administrator rights and installs a sampling driver. Reboot if asked.
2. Open a *new* terminal so `vtune` is on the PATH (or run
   `"C:\Program Files (x86)\Intel\oneAPI\setvars.bat"`). Check with `vtune --version`.
3. From `harness/`, count retired micro-ops and instructions for the fast and slow kernels on an
   E-core (CPU 12). Event names can differ per VTune version; `vtune -collect-with runsa -knob
   event-config=? ` lists the ones available. On hybrid chips the E-core events carry a
   `cpu_atom/` prefix.
   ```
   vtune -collect-with runsa -knob event-config=UOPS_RETIRED.ALL,INST_RETIRED.ANY -r vt_fast -- bench.exe 12 200000 e3B_nodisp
   vtune -collect-with runsa -knob event-config=UOPS_RETIRED.ALL,INST_RETIRED.ANY -r vt_slow -- bench.exe 12 200000 e3B_disp8
   vtune -report summary -r vt_fast
   vtune -report summary -r vt_slow
   ```
4. Micro-ops per instruction = UOPS_RETIRED ÷ INST_RETIRED. The `add rax,rcx` calibration loop runs
   too, but it's 1 micro-op per instruction, so it only dilutes. Comparing fast and slow still shows
   the difference. **≈ 2 for the slow form** means it is split in two. **≈ 1** means one slower step.
   The 16-bit `lea ax,...` (≈3.6 cycles) would be a good second target.

## Files in this folder

| file | what it is |
|---|---|
| `FINDINGS.md` | this write-up |
| `results.csv`, `zero_disp.csv` | Part 1: the students' experiments on CPUs 2, 8 (P) and 12, 16 (E) |
| `compare_results.csv`, `compare_zero_disp.csv` | Part 1 side by side with the students' numbers |
| `extension.csv`, `extension_loadcheck.csv` | Parts 2 and 3 |
| `encodings.txt` | disassembly of every new kernel, proving the bytes match the labels |
| `fig_mine_*.png` | the three figures |
| `raw/` | unprocessed per-CPU output of `bench.exe` |
| `scripts/` | `compare.py`, `plot_mine.py`, `check_encodings.py` |

To reproduce, from `harness/`:
```
python run_all.py --outdir=..\results_mine 2:P 8:P 12:E 16:E
python run_all.py --only=ez --out=zero_disp.csv --outdir=..\results_mine 2:P 8:P 12:E 16:E
python run_all.py --only=x --out=extension.csv --outdir=..\results_mine 2:P 8:P 12:E 16:E
python ..\results_mine\scripts\compare.py results.csv
python ..\results_mine\scripts\compare.py zero_disp.csv
python ..\results_mine\scripts\plot_mine.py
```
(The third command now also runs the two load-check kernels, which were added after
`extension.csv` was recorded and saved separately in `extension_loadcheck.csv`.)
