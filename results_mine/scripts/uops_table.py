"""Part 4: turn the VTune per-CPU counts into micro-ops per instruction.

Input:  results_mine/vtune/raw/cpu<N>_<kernel>_r<rep>_hw.csv  (vtune -report hw-events -group-by cpuid)
Output: results_mine/vtune/uops.csv (one row per CPU x kernel x repeat) and a printed summary.

How the kernel is isolated:
  * Only the row for the CPU the program was pinned to is used (other CPUs = other programs).
  * The `empty` kernel (same program, zero loop body) is run on the same CPU in the same repeat;
    its counts (program start-up, exit, background on that CPU) are subtracted.
  * What is left is divided by the extra instructions retired:
        per_instr(X) = (X_kernel - X_empty) / (INST_kernel - INST_empty)
  * add_rr_chain (one plain add per instruction) is the control and must come out at 1.00.
"""
import csv, glob, os, re, statistics as st
from collections import defaultdict

HERE = os.path.join(os.path.dirname(__file__), '..', 'vtune')
EXPECTED_INST = 200 * 200000 * 25  # body instructions per run


def read_hw(path):
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        lines = [l.strip() for l in f]
    hdr = next(i for i, l in enumerate(lines) if 'Hardware Event Count:' in l)
    cols = [c.replace('Hardware Event Count:', '') for c in lines[hdr].split(',')]
    out = {}
    for l in lines[hdr + 1:]:
        m = re.match(r'^cpu_(\d+),', l)
        if m:
            vals = l.split(',')
            out[int(m.group(1))] = {c: float(v) for c, v in zip(cols[1:], vals[1:]) if re.fullmatch(r'[0-9.]+', v)}
    return out


runs = {}
for p in glob.glob(os.path.join(HERE, 'raw', 'cpu*_r*_hw.csv')):
    m = re.match(r'cpu(\d+)_(.+)_r(\d+)_hw\.csv', os.path.basename(p))
    cpu, kernel, rep = int(m.group(1)), m.group(2), int(m.group(3))
    runs[(cpu, kernel, rep)] = read_hw(p)[cpu]

E_CPUS, P_CPUS = (12, 16), (2, 8)
METRICS = {  # what each core type can count
    'E': [('uops_retired', 'UOPS_RETIRED.ALL'), ('uops_issued', 'UOPS_ISSUED.ANY'),
          ('ms_uops', 'UOPS_RETIRED.MS'), ('cycles', 'CPU_CLK_UNHALTED.CORE')],
    'P': [('uops_retired', 'UOPS_RETIRED.SLOTS'), ('uops_issued', 'UOPS_ISSUED.ANY'),
          ('heavy_uops', 'UOPS_RETIRED.HEAVY'), ('ms_uops', 'UOPS_RETIRED.MS'),
          ('cycles', 'CPU_CLK_UNHALTED.THREAD')],
}
rows = []
for (cpu, kernel, rep), c in sorted(runs.items()):
    if kernel == 'empty' or (cpu, 'empty', rep) not in runs:
        continue
    e = runs[(cpu, 'empty', rep)]
    typ = 'E' if cpu in E_CPUS else 'P'
    d_inst = c['INST_RETIRED.ANY'] - e['INST_RETIRED.ANY']
    row = {'cpu': cpu, 'core': typ, 'kernel': kernel, 'rep': rep,
           'inst_extra': int(d_inst), 'inst_vs_expected': round(d_inst / EXPECTED_INST, 4)}
    for name, ev in METRICS[typ]:
        row[name + '_per_instr'] = round((c[ev] - e[ev]) / d_inst, 4)
    rows.append(row)

fields = ['cpu', 'core', 'kernel', 'rep', 'inst_extra', 'inst_vs_expected',
          'uops_retired_per_instr', 'uops_issued_per_instr', 'heavy_uops_per_instr', 'ms_uops_per_instr',
          'cycles_per_instr']
with open(os.path.join(HERE, 'uops.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in rows:
        w.writerow(r)

# Summary: mean and spread over the 3 repeats, per CPU
g = defaultdict(list)
for r in rows:
    g[(r['core'], r['kernel'], r['cpu'])].append(r)
print(f"{'core':4} {'kernel':13} {'cpu':>3} {'inst/exp':>8} {'uops ret':>14} {'uops iss':>14} {'heavy':>8} {'MS':>7} {'cycles':>7}")
for key in sorted(g, key=lambda k: (k[0], ['add_rr_chain', 'e3B_nodisp', 'e3B_disp8', 'x2b_w_bi'].index(k[1]), k[2])):
    rs = g[key]
    def ms(col):
        v = [r[col] for r in rs if col in r]
        return f"{st.mean(v):.3f}±{(max(v)-min(v))/2:.3f}" if v else '-'
    def m(col):
        v = [r[col] for r in rs if col in r]
        return f"{st.mean(v):.3f}" if v else '-'
    print(f"{key[0]:4} {key[1]:13} {key[2]:>3} {m('inst_vs_expected'):>8} {ms('uops_retired_per_instr'):>14} "
          f"{ms('uops_issued_per_instr'):>14} {m('heavy_uops_per_instr'):>8} {m('ms_uops_per_instr'):>7} {m('cycles_per_instr'):>7}  (n={len(rs)})")
