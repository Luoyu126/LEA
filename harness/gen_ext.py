"""Extension kernels (results_mine/): new LEA address modes, stores, add-with-memory, loads.

Called from gen.py. Every memory-operand instruction is emitted as raw bytes built by enc(),
so the assembler cannot shorten or drop a zero displacement; check with
    gcc -c kernels.S -o k.o && objdump -d -M intel k.o
Kernel names start with "x", so `run_all.py --only=x` runs just these.

Register state at loop entry (from gen.py): rax=0 rcx=1 rbx=1 rdx=0 rsi=0 rdi=0 r8=0 r9=0 r12=0
rbp=16 r13=16 r14=16 r15=1, r10=mem (mem[0]=mem[8]=mem[4096]=&mem, all other bytes 0).
"""

R = {n: i for i, n in enumerate(
    "rax rcx rdx rbx rsp rbp rsi rdi r8 r9 r10 r11 r12 r13 r14 r15".split())}
LOG2 = {1: 0, 2: 1, 4: 2, 8: 3}


def enc(opcode, reg, base=None, index=None, scale=1, disp=0, dsize=0, opsize=64, a32=False, rip=False):
    """x86-64 bytes for `opcode reg, [mem]` (or `opcode [mem], reg`, same ModRM layout).
    dsize: 0 = no displacement field, 1 = disp8, 4 = disp32 (kept even when disp == 0)."""
    reg, b, x = R[reg], R.get(base), R.get(index)
    rex_r, rex_x, rex_b = reg >> 3, 0, 0
    if rip:
        assert base is None and index is None and dsize == 4
        modrm, tail = [(reg & 7) << 3 | 5], []
    elif b is None:  # index only: SIB with base=101 and mod=00 always means disp32, no base
        assert x is not None and x != 4 and dsize == 4
        rex_x = x >> 3
        modrm, tail = [(reg & 7) << 3 | 4], [LOG2[scale] << 6 | (x & 7) << 3 | 5]
    else:
        assert not (dsize == 0 and (b & 7) == 5), "rbp/r13 base needs a displacement"
        mod = {0: 0, 1: 1, 4: 2}[dsize]
        rex_b = b >> 3
        if x is None and (b & 7) != 4:
            modrm, tail = [mod << 6 | (reg & 7) << 3 | (b & 7)], []
        else:  # SIB byte (needed for an index, or for rsp/r12 as base)
            assert x != 4, "rsp cannot be an index"
            xi = 4 if x is None else x
            rex_x = xi >> 3 if x is not None else 0
            modrm, tail = [mod << 6 | (reg & 7) << 3 | 4], [LOG2[scale] << 6 | (xi & 7) << 3 | (b & 7)]
    d = list((disp & (0xFF if dsize == 1 else 0xFFFFFFFF)).to_bytes(dsize, "little")) if dsize else []
    out = ([0x66] if opsize == 16 else []) + ([0x67] if a32 else [])
    rex = 0x40 | (opsize == 64) << 3 | rex_r << 2 | rex_x << 1 | rex_b
    if rex != 0x40:
        out.append(rex)
    return ".byte " + ",".join(f"0x{v:02X}" for v in out + opcode + modrm + tail + d)


LEA, LOAD, STORE, ADD = [0x8D], [0x8B], [0x89], [0x03]
DST = ["rax", "rbx", "rdx", "rsi", "rdi", "r8", "r9", "r12"]   # LEA throughput (sources r14/r15)
MDST = ["rax", "rbx", "rcx", "rdx", "rsi", "r9", "r12", "r13"]  # load/add throughput (r10/r8 = address)


def add_kernels(lat, k):
    def tp(name, exp, form, body, **kw):
        k(name, exp, form, "-", "throughput", body, **kw)

    # ---------------- Part 2A: 0x67 address-size prefix (32-bit address arithmetic) ----------------
    # References in the same run, 64-bit addressing
    lat("x2r_bi", "X2A", "lea rax,[rax+rcx] (64-bit addr, reference)", "base", [enc(LEA, "rax", "rax", "rcx")])
    lat("x2r_bi_d8", "X2A", "lea rax,[rax+rcx+0] disp8 (64-bit addr, reference)", "base",
        [enc(LEA, "rax", "rax", "rcx", dsize=1)])
    for name, form, kw in [
        ("b",      "lea rax,[eax]",                {"base": "rax"}),
        ("b_d8",   "lea rax,[eax+0] disp8",        {"base": "rax", "dsize": 1}),
        ("bi",     "lea rax,[eax+ecx]",            {"base": "rax", "index": "rcx"}),
        ("bi_d8",  "lea rax,[eax+ecx+0] disp8",    {"base": "rax", "index": "rcx", "dsize": 1}),
        ("bi_d32", "lea rax,[eax+ecx+0] disp32",   {"base": "rax", "index": "rcx", "dsize": 4}),
        ("bi_8",   "lea rax,[eax+ecx+8] disp8",    {"base": "rax", "index": "rcx", "disp": 8, "dsize": 1}),
        ("i_d32",  "lea rax,[eax*1+0] no base",    {"index": "rax", "dsize": 4}),
    ]:
        lat(f"x2a_{name}", "X2A", form, "index" if name == "i_d32" else "base", [enc(LEA, "rax", a32=True, **kw)])
    lat("x2a_e_bi", "X2A", "lea eax,[eax+ecx]", "base", [enc(LEA, "rax", "rax", "rcx", opsize=32, a32=True)])
    lat("x2a_e_bi_d8", "X2A", "lea eax,[eax+ecx+0] disp8", "base",
        [enc(LEA, "rax", "rax", "rcx", dsize=1, opsize=32, a32=True)])
    tp("x2a_tp_bi", "X2A", "lea r64,[r14d+r15d]", [enc(LEA, d, "r14", "r15", a32=True) for d in DST])
    tp("x2a_tp_bi_d8", "X2A", "lea r64,[r14d+r15d+0] disp8", [enc(LEA, d, "r14", "r15", dsize=1, a32=True) for d in DST])

    # ---------------- Part 2B: destination size (16-bit vs 32-bit) ----------------
    for sz, tag in [(16, "w"), (32, "d")]:
        dn = "ax" if sz == 16 else "eax"
        for name, form, kw in [
            ("b",     f"lea {dn},[rax]",             {"base": "rax"}),
            ("b_d8",  f"lea {dn},[rax+0] disp8",     {"base": "rax", "dsize": 1}),
            ("bi",    f"lea {dn},[rax+rcx]",         {"base": "rax", "index": "rcx"}),
            ("bi_d8", f"lea {dn},[rax+rcx+0] disp8", {"base": "rax", "index": "rcx", "dsize": 1}),
        ]:
            lat(f"x2b_{tag}_{name}", "X2B", form, "base", [enc(LEA, "rax", opsize=sz, **kw)])
    lat("x2b_w67_bi", "X2B", "lea ax,[eax+ecx]", "base", [enc(LEA, "rax", "rax", "rcx", opsize=16, a32=True)])
    lat("x2b_w67_bi_d8", "X2B", "lea ax,[eax+ecx+0] disp8", "base",
        [enc(LEA, "rax", "rax", "rcx", dsize=1, opsize=16, a32=True)])
    # 16-bit writes merge into the old register, so each of the 8 destinations is its own chain
    tp("x2b_tp_w_bi", "X2B", "lea r16,[r14+r15] (8 merge chains)", [enc(LEA, d, "r14", "r15", opsize=16) for d in DST])
    tp("x2b_tp_w_bi_d8", "X2B", "lea r16,[r14+r15+0] disp8 (8 merge chains)",
       [enc(LEA, d, "r14", "r15", dsize=1, opsize=16) for d in DST])

    # ---------------- Part 2C: RIP-relative (no register input: throughput only) ----------------
    tp("x2c_rip_0", "X2C", "lea r64,[rip+0] disp32", [enc(LEA, d, dsize=4, rip=True) for d in DST])
    tp("x2c_rip_64", "X2C", "lea r64,[rip+64] disp32", [enc(LEA, d, disp=64, dsize=4, rip=True) for d in DST])
    tp("x2c_eip_0", "X2C", "lea r64,[eip+0] disp32 (0x67)", [enc(LEA, d, dsize=4, rip=True, a32=True) for d in DST])
    tp("x2c_b", "X2C", "lea r64,[r14] (reference)", [enc(LEA, d, "r14") for d in DST])
    tp("x2c_b_d32", "X2C", "lea r64,[r14+0] disp32 (reference)", [enc(LEA, d, "r14", dsize=4) for d in DST])

    # ---------------- Part 2D: index only, no base (always disp32) vs same-value forms ----------------
    for name, form, kw in [
        ("b",      "lea rax,[rax] (same value, base form)",     {"base": "rax"}),
        ("b_d32",  "lea rax,[rax+0] disp32 (base form)",        {"base": "rax", "dsize": 4}),
        ("i1_0",   "lea rax,[rax*1+0] no base",                 {"index": "rax", "dsize": 4}),
        ("i1_8",   "lea rax,[rax*1+8] no base",                 {"index": "rax", "disp": 8, "dsize": 4}),
        ("bb",     "lea rax,[rax+rax*1] (=2*rax, base form)",   {"base": "rax", "index": "rax"}),
        ("i2_0",   "lea rax,[rax*2+0] no base (=2*rax)",        {"index": "rax", "scale": 2, "dsize": 4}),
        ("i4_0",   "lea rax,[rax*4+0] no base",                 {"index": "rax", "scale": 4, "dsize": 4}),
        ("i8_0",   "lea rax,[rax*8+0] no base",                 {"index": "rax", "scale": 8, "dsize": 4}),
    ]:
        lat(f"x2d_{name}", "X2D", form, "index", [enc(LEA, "rax", **kw)])
    for name, form, kw in [
        ("b",    "lea r64,[r15] (base form)",     {"base": "r15"}),
        ("i1_0", "lea r64,[r15*1+0] no base",     {"index": "r15", "dsize": 4}),
        ("i1_8", "lea r64,[r15*1+8] no base",     {"index": "r15", "disp": 8, "dsize": 4}),
        ("i4_0", "lea r64,[r15*4+0] no base",     {"index": "r15", "scale": 4, "dsize": 4}),
    ]:
        tp(f"x2d_tp_{name}", "X2D", form, [enc(LEA, d, **kw) for d in DST])

    # ---------------- Part 2F (bonus): which displacement values does the P-core fold? ----------------
    for v, ds in [(0, 4), (1, 1), (1, 4), (127, 1), (128, 4), (1023, 4), (1024, 4), (2047, 4), (2048, 4),
                  (-1, 1), (-1024, 4), (-1025, 4), (4096, 4)]:
        nm = f"{'m' if v < 0 else ''}{abs(v)}_d{ds * 8}"
        lat(f"x2f_{nm}", "X2F", f"lea rax,[rax{v:+d}] disp{ds * 8}", "base",
            [enc(LEA, "rax", "rax", disp=v, dsize=ds)])
    for v in (1, 1023, 1024, 4096):
        lat(f"x2f_add_{v}", "X2F", f"add rax,{v} (reference)", "-", [f"add rax, {v}"])

    # ---------------- Part 3: other instructions, with vs without a (zero) displacement ----------------
    # Memory forms. Index register r8 = 0, so every form addresses the same byte.
    def forms(b, idx="r8"):
        return [
            ("b",       f"[{b}]",             {"base": b}),
            ("b_d8",    f"[{b}+0] disp8",     {"base": b, "dsize": 1}),
            ("b_d32",   f"[{b}+0] disp32",    {"base": b, "dsize": 4}),
            ("bi",      f"[{b}+{idx}]",       {"base": b, "index": idx}),
            ("bi_d8",   f"[{b}+{idx}+0] disp8",  {"base": b, "index": idx, "dsize": 1}),
            ("bi_d32",  f"[{b}+{idx}+0] disp32", {"base": b, "index": idx, "dsize": 4}),
            ("bi8",     f"[{b}+{idx}*8]",     {"base": b, "index": idx, "scale": 8}),
            ("bi8_d8",  f"[{b}+{idx}*8+0] disp8", {"base": b, "index": idx, "scale": 8, "dsize": 1}),
            ("i1_d32",  f"[{b}*1+0] no base", {"index": b, "dsize": 4}),
        ]

    # 3S: store throughput, mov [mem], rax. Stores go to mem+1024 (unused by other kernels).
    for name, f, kw in forms("rdi"):
        tp(f"x3s_{name}", "X3S", f"mov {f}, rax", [enc(STORE, "rax", **kw)], setup="lea rdi, [r10+1024]")
    # 3F: store -> load forwarding latency, per (store + load) pair, same form for both
    for name, f, kw in forms("rdi"):
        if name in ("b", "b_d8", "bi", "bi_d8", "i1_d32"):
            lat(f"x3f_{name}", "X3F", f"mov {f},rax; mov rax,{f}", "-",
                [enc(STORE, "rax", **kw), enc(LOAD, "rax", **kw)], setup="lea rdi, [r10+1024]", per_op=2)
    # 3L: load-use latency, pointer chase mov rax,[rax...] (mem[0] = &mem)
    for name, f, kw in forms("rax"):
        lat(f"x3l_{name}", "X3L", f"mov rax,{f}", "base", [enc(LOAD, "rax", **kw)], setup="mov rax, r10")
    # 3A: add rax,[mem] with the ADDRESS on the chain: rax = mem+16 and mem[16] = 0, so rax never changes
    for name, f, kw in forms("rax"):
        lat(f"x3a_{name}", "X3A", f"add rax,{f} (address on chain)", "base", [enc(ADD, "rax", **kw)],
            setup="lea rax, [r10+16]")
    # 3R: add rax,[mem] with only the REGISTER operand on the chain (load is independent)
    for name, f, kw in forms("r10"):
        lat(f"x3r_{name}", "X3R", f"add rax,{f} (register on chain)", "-", [enc(ADD, "rax", **kw)])
    # 3T: add-with-memory throughput, 8 accumulators
    for name, f, kw in forms("r10"):
        tp(f"x3t_{name}", "X3T", f"add r64,{f}", [enc(ADD, d, **kw) for d in MDST])
    # 3LT: load throughput, 8 destinations
    for name, f, kw in forms("r10"):
        tp(f"x3lt_{name}", "X3LT", f"mov r64,{f}", [enc(LOAD, d, **kw) for d in MDST])

    # 3LT check: is 0.5 c/load a same-address artifact? 8 loads to 8 different cache lines.
    tp("x3lt_chk_lines", "X3LT", "mov r64,[r10+64*j] (8 different lines, check)",
       [enc(LOAD, d, "r10", disp=64 * j, dsize=4) for j, d in enumerate(MDST)])
    tp("x3lt_chk_32", "X3LT", "mov r32,[r10] (32-bit loads, check)", [enc(LOAD, d, "r10", opsize=32) for d in MDST])
