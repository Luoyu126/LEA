#!/usr/bin/env python3
"""Generate kernels.S, kernels.h and kernels.json (metadata) for all experiments.

Every kernel has signature  void k(long long iters, void *mem).
Usage: gen.py OUT_DIR [win|sysv]   (default: win on Windows, sysv elsewhere)

Register state at loop entry (set by every kernel's prologue):
  rax=0 rcx=1 rbx=1 rdx=0 rsi=0 rdi=0 r8=0 r9=0 r12=0 rbp=16 r13=16 r14=16 r15=1
  r10=mem (64B-aligned self-pointer buffer), r11=loop counter
"""
import json
import os
import re
import sys

N = 200  # unrolled instructions per loop iteration

KERNELS = []  # dicts: name, exp, form, path, metric, setup, body, per_op


def k(name, exp, form, path, metric, body, setup="", per_op=1):
    KERNELS.append(dict(name=name, exp=exp, form=form, path=path, metric=metric,
                        setup=setup, body=body, per_op=per_op))


def lat(name, exp, form, path, body, **kw):
    k(name, exp, form, path, "latency", body, **kw)


def byt(hexstr):
    """Raw machine code, to force an exact encoding the assembler might otherwise shorten."""
    return ".byte " + ",".join("0x" + b for b in hexstr.split())


# --- 0: calibration / sanity ---
lat("empty", "0", "loop only", "-", [])
lat("add_rr_chain", "0", "add rax,rcx", "-", ["add rax, rcx"])  # calibration reference (1 cycle)
lat("add_imm_chain", "0", "add rax,1", "-", ["add rax, 1"])     # folded at rename on new cores
lat("imul_chain", "0", "imul rax,rax", "-", ["imul rax, rax"], setup="mov rax, 3")
k("add_4chains", "0", "4x add r,rcx", "-", "throughput",
  ["add rax, rcx", "add rbx, rcx", "add rdx, rcx", "add rsi, rcx"])

# --- 1: LEA latency sweep (chain register rax) ---
for name, form, path, ins in [
    ("b",        "base",              "base",  "lea rax, [rax]"),
    ("bd8",      "base+disp8",        "base",  "lea rax, [rax+8]"),
    ("bd32",     "base+disp32",       "base",  "lea rax, [rax+4096]"),
    ("bi",       "base+index",        "base",  "lea rax, [rax+rcx]"),
    ("bi",       "base+index",        "index", "lea rax, [rcx+rax]"),
    ("bi4",      "base+index*4",      "base",  "lea rax, [rax+rcx*4]"),
    ("bi4",      "base+index*4",      "index", "lea rax, [rcx+rax*4]"),
    ("bi8",      "base+index*8",      "base",  "lea rax, [rax+rcx*8]"),
    ("i4d",      "index*4+disp",      "index", "lea rax, [rax*4+8]"),
    ("bid",      "base+index+disp",   "base",  "lea rax, [rax+rcx+8]"),
    ("bid",      "base+index+disp",   "index", "lea rax, [rcx+rax+8]"),
    ("bi4d",     "base+index*4+disp", "base",  "lea rax, [rax+rcx*4+8]"),
    ("bi4d",     "base+index*4+disp", "index", "lea rax, [rcx+rax*4+8]"),
    ("rbp_i",    "rbp+index",         "index", "lea rax, [rbp+rax]"),
    ("r13_i",    "r13+index",         "index", "lea rax, [r13+rax]"),
    ("bid32bit", "base+index+disp (32-bit dst)", "base", "lea eax, [rax+rcx+8]"),
]:
    lat(f"e1_{name}_{path}", "1", form, path, [ins])

# --- 3: equivalent encodings (latency) ---
# A: same value 2*rax; [rax*2] has no base so it must carry a disp32
lat("e3A_rax_rax", "3A", "lea rax,[rax+rax] (4B)", "-", [byt("48 8D 04 00")])
lat("e3A_rax_x2", "3A", "lea rax,[rax*2+0] (8B, disp32)", "-", [byt("48 8D 04 45 00 00 00 00")])
# B: [rax+rcx] with no / zero disp8 / zero disp32
lat("e3B_nodisp", "3B", "[rax+rcx] no disp (4B)", "-", [byt("48 8D 04 08")])
lat("e3B_disp8", "3B", "[rax+rcx+0] disp8 (5B)", "-", [byt("48 8D 44 08 00")])
lat("e3B_disp32", "3B", "[rax+rcx+0] disp32 (8B)", "-", [byt("48 8D 84 08 00 00 00 00")])
# C: special base registers; rbp/r13 need a disp8, rsp/r12 a SIB byte (all index = rax)
lat("e3C_rbx", "3C", "[rbx+rax] (4B)", "index", [byt("48 8D 04 03")])
lat("e3C_rsp", "3C", "[rsp+rax] (4B)", "index", [byt("48 8D 04 04")])
lat("e3C_r12", "3C", "[r12+rax] (4B)", "index", [byt("49 8D 04 04")])
lat("e3C_rbp", "3C", "[rbp+rax+0] (5B, disp8)", "index", [byt("48 8D 44 05 00")])
lat("e3C_r13", "3C", "[r13+rax+0] (5B, disp8)", "index", [byt("49 8D 44 05 00")])
# D: LEA vs equivalent ALU instruction
lat("e3D_lea_x4", "3D", "lea rax,[rax*4+0]", "-", [byt("48 8D 04 85 00 00 00 00")])
lat("e3D_shl", "3D", "shl rax,2", "-", ["shl rax, 2"])
lat("e3D_lea_bi", "3D", "lea rax,[rax+rcx]", "-", ["lea rax, [rax+rcx]"])
lat("e3D_add", "3D", "add rax,rcx", "-", ["add rax, rcx"])
# E: one complex LEA vs the same arithmetic split into simpler instructions (cycles per original op)
lat("e3E_lea3", "3E", "lea rax,[rax+rcx+8]", "-", ["lea rax, [rax+rcx+8]"])
lat("e3E_lea_add", "3E", "lea rax,[rax+rcx]; add rax,8", "-", ["lea rax, [rax+rcx]", "add rax, 8"], per_op=2)
lat("e3E_add_add", "3E", "add rax,rcx; add rax,8", "-", ["add rax, rcx", "add rax, 8"], per_op=2)
lat("e3E_lea3s", "3E", "lea rax,[rax+rcx*4+8]", "-", ["lea rax, [rax+rcx*4+8]"])
lat("e3E_leas_add", "3E", "lea rax,[rax+rcx*4]; add rax,8", "-", ["lea rax, [rax+rcx*4]", "add rax, 8"], per_op=2)
lat("e3E_hoist", "3E", "lea rdx,[rcx*4+8]; add rax,rdx", "-", ["lea rdx, [rcx*4+8]", "add rax, rdx"], per_op=2)

# --- 4: load-use latency, pointer chasing on a self-pointer (every form hits the same line) ---
for name, form, ins in [
    ("b",      "base",            "mov rax, [rax]"),
    ("bi",     "base+index",      "mov rax, [rax+rcx]"),
    ("bi8",    "base+index*8",    "mov rax, [rax+rcx*8]"),
    ("bd8",    "base+disp8",      "mov rax, [rax+8]"),
    ("bd32",   "base+disp32",     "mov rax, [rax+4096]"),
    ("bid",    "base+index+disp", "mov rax, [rax+rcx+8]"),
]:
    lat(f"e4_{name}", "4", form, "base", [ins], setup="mov rax, r10\n    xor ecx, ecx")

# --- 2: LEA throughput (8 independent destinations, fixed sources r14/r15) ---
DST = ["rax", "rbx", "rdx", "rsi", "rdi", "r8", "r9", "r12"]
TP_FORMS = [
    ("b",     "base",              "[r14]"),
    ("bd8",   "base+disp8",        "[r14+8]"),
    ("bi",    "base+index",        "[r14+r15]"),
    ("bi4",   "base+index*4",      "[r14+r15*4]"),
    ("i4d",   "index*4+disp",      "[r15*4+8]"),
    ("bid",   "base+index+disp",   "[r14+r15+8]"),
    ("bi4d",  "base+index*4+disp", "[r14+r15*4+8]"),
    ("rbp_i", "rbp+index",         "[rbp+r15]"),
    ("r13_i", "r13+index",         "[r13+r15]"),
    ("rip",   "rip-relative",      "[rip+k_empty]"),
]
for name, form, mem in TP_FORMS:
    k(f"e2_{name}", "2", form, "-", "throughput", [f"lea {d}, {mem}" for d in DST])
PARTNERS = {"add": "add {d}, r15", "imul": "imul {d}, r14, 3", "shlx": "shlx {d}, r14, r15"}
for p, tmpl in PARTNERS.items():
    k(f"e2_ref_{p}", "2", f"{p} alone", "-", "throughput", [tmpl.format(d=d) for d in DST])
# interference: LEA interleaved 1:1 with an instruction of known port; cycles per (lea + partner) pair
for name, form, mem in [t for t in TP_FORMS if t[0] in ("bi", "bi4", "bid", "bi4d")]:
    for p, tmpl in PARTNERS.items():
        body = []
        for ld, pd in zip(DST[:4], DST[4:]):
            body += [f"lea {ld}, {mem}", tmpl.format(d=pd)]
        k(f"e2_mix_{name}_{p}", "2mix", f"{form} + {p}", p, "throughput", body, per_op=2)

# --- Z: focused zero-displacement study. Every form computes rax+rcx (or a 2-part control);
# encodings forced byte-for-byte so the assembler cannot drop a zero displacement. ---
for name, form, code in [
    ("bi",        "[rax+rcx]",                 "48 8D 04 08"),
    ("bi_d8_0",   "[rax+rcx+0] disp8",         "48 8D 44 08 00"),
    ("bi_d32_0",  "[rax+rcx+0] disp32",        "48 8D 84 08 00 00 00 00"),
    ("bi_d8_8",   "[rax+rcx+8] disp8",         "48 8D 44 08 08"),
    ("bi_d8_m8",  "[rax+rcx-8] disp8",         "48 8D 44 08 F8"),
    ("bi_d8_127", "[rax+rcx+127] disp8",       "48 8D 44 08 7F"),
    ("bi_d32_4k", "[rax+rcx+4096] disp32",     "48 8D 84 08 00 10 00 00"),
    ("b",         "[rax]",                     "48 8D 00"),
    ("b_d8_0",    "[rax+0] disp8",             "48 8D 40 00"),
    ("b_d32_0",   "[rax+0] disp32",            "48 8D 80 00 00 00 00"),
]:
    lat(f"ez_{name}_base", "Z", form, "base", [byt(code)])
for name, form, code in [
    ("bi",      "[rcx+rax]",          "48 8D 04 01"),
    ("bi_d8_0", "[rcx+rax+0] disp8",  "48 8D 44 01 00"),
    ("rbx",     "[rbx+rax]",          "48 8D 04 03"),
    ("rbp_d8_0", "[rbp+rax+0] disp8 (forced)", "48 8D 44 05 00"),
    ("r13_d8_0", "[r13+rax+0] disp8 (forced)", "49 8D 44 05 00"),
    ("rbp_d32_0", "[rbp+rax+0] disp32", "48 8D 84 05 00 00 00 00"),
]:
    lat(f"ez_{name}_index", "Z", form, "index", [byt(code)])
# Same forms with rcx = 0: [rax+rcx+0] then computes exactly rax, like [rax+0].
# If time depends on the encoded form, rcx's value must not matter.
for name, form, code in [
    ("bi",       "[rax+rcx], rcx=0",           "48 8D 04 08"),
    ("bi_d8_0",  "[rax+rcx+0] disp8, rcx=0",   "48 8D 44 08 00"),
    ("bi_d32_0", "[rax+rcx+0] disp32, rcx=0",  "48 8D 84 08 00 00 00 00"),
]:
    lat(f"ez0_{name}_base", "Z0", form, "base", [byt(code)], setup="xor ecx, ecx")
for name, form, code in [
    ("bi",      "[rcx+rax], rcx=0 (rcx is base)",          "48 8D 04 01"),
    ("bi_d8_0", "[rcx+rax+0] disp8, rcx=0 (rcx is base)",  "48 8D 44 01 00"),
]:
    lat(f"ez0_{name}_index", "Z0", form, "index", [byt(code)], setup="xor ecx, ecx")

# Index + disp with NO base (only 2 parts). Without a base, x86 always encodes a disp32.
# "Count the parts" predicts 1 cycle here; "index and disp both present" predicts 2.
for name, form, code in [
    ("i1_d32_0", "[rax*1+0] index+disp32, no base", "48 8D 04 05 00 00 00 00"),
    ("i1_d32_8", "[rax*1+8] index+disp32, no base", "48 8D 04 05 08 00 00 00"),
    ("i2_d32_0", "[rax*2+0] index*2+disp32, no base", "48 8D 04 45 00 00 00 00"),
]:
    lat(f"ezi_{name}_index", "ZI", form, "index", [byt(code)])
# controls with rcx = 0: two registers, no displacement, every value but rax is zero
lat("ezi_rcx_rcx_index", "ZI", "[rcx+rax] base+index, rcx=0", "index", [byt("48 8D 04 01")], setup="xor ecx, ecx")

# throughput: 8 independent destinations, gas {disp8}/{disp32} pseudo-prefixes force the zero disp
for name, form, pre, mem in [
    ("bi",       "[r14+r15]",              "",         "[r14+r15]"),
    ("bi_d8_0",  "[r14+r15+0] disp8",      "{disp8} ", "[r14+r15]"),
    ("bi_d32_0", "[r14+r15+0] disp32",     "{disp32} ", "[r14+r15]"),
    ("b",        "[r14]",                  "",         "[r14]"),
    ("b_d8_0",   "[r14+0] disp8",          "{disp8} ", "[r14]"),
]:
    k(f"ez_tp_{name}", "Z", form, "-", "throughput", [f"{pre}lea {d}, {mem}" for d in DST])

# Zero-disp study labels: write every index with its (encoded) scale *1, so the ablation reads
# base / index / disp explicitly. The SIB byte always stores a scale; these kernels all use 1.
for kd in KERNELS:
    if kd["exp"] in ("Z", "Z0", "ZI"):
        kd["form"] = re.sub(r"\[(\w+)\+([a-z]\w*)\b(?!\*)", r"[\1+\2*1", kd["form"])

SAVED = ["rbx", "rbp", "rdi", "rsi", "r12", "r13", "r14", "r15"]
INIT = """    xor eax, eax
    mov ecx, 1
    mov ebx, 1
    xor edx, edx
    xor esi, esi
    xor edi, edi
    xor r8d, r8d
    xor r9d, r9d
    xor r12d, r12d
    mov ebp, 16
    mov r13d, 16
    mov r14d, 16
    mov r15d, 1"""


def main(out_dir, abi):
    a1, a2 = ("rcx", "rdx") if abi == "win" else ("rdi", "rsi")
    s = [".intel_syntax noprefix", ".text"]
    for kd in KERNELS:
        name, body = kd["name"], kd["body"]
        assert not body or N % len(body) == 0, name
        s += [f".globl k_{name}", ".p2align 6", f"k_{name}:"]
        s += [f"    push {r}" for r in SAVED]
        s += [f"    mov r11, {a1}", f"    mov r10, {a2}", INIT]
        if kd["setup"]:
            s.append("    " + kd["setup"])
        s += [".p2align 6", "1:"]
        s += ["    " + body[i % len(body)] for i in range(N if body else 0)]
        s += ["    dec r11", "    jnz 1b"]
        s += [f"    pop {r}" for r in reversed(SAVED)]
        s.append("    ret")
    if abi == "sysv":
        s.append('.section .note.GNU-stack,"",@progbits')
    open(os.path.join(out_dir, "kernels.S"), "w").write("\n".join(s) + "\n")

    h = [f"#define UNROLL {N}"]
    h += [f"void k_{kd['name']}(long long, void *);" for kd in KERNELS]
    h.append("static struct { const char *name; void (*fn)(long long, void *); } KERNELS[] = {")
    h += [f'  {{"{kd["name"]}", k_{kd["name"]}}},' for kd in KERNELS]
    h.append("};")
    open(os.path.join(out_dir, "kernels.h"), "w").write("\n".join(h) + "\n")
    json.dump(KERNELS, open(os.path.join(out_dir, "kernels.json"), "w"), indent=1)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    abi = sys.argv[2] if len(sys.argv) > 2 else ("win" if os.name == "nt" else "sysv")
    main(out, abi)
