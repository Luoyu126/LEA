	.file	"real_kernels.c"
	.intel_syntax noprefix
	.text
	.p2align 4
	.globl	"w1_naive"
	.def	"w1_naive";	.scl	2;	.type	32;	.endef
	.seh_proc	"w1_naive"
"w1_naive":
	.seh_endprologue
	mov	rax, r8
	test	rdx, rdx
	jle	.L2
	xor	r9d, r9d
	.p2align 5
	.p2align 4
	.p2align 3
.L3:
	mov	r8, r9
	add	r9, 1
	and	r8d, 63
	mov	r8, QWORD PTR [rcx+r8*8]
	lea	rax, 8[rax+r8*4]
	cmp	rdx, r9
	jne	.L3
.L2:
	ret
	.seh_endproc
	.p2align 4
	.globl	"w1_split"
	.def	"w1_split";	.scl	2;	.type	32;	.endef
	.seh_proc	"w1_split"
"w1_split":
	.seh_endprologue
	mov	rax, r8
	test	rdx, rdx
	jle	.L7
	xor	r10d, r10d
	.p2align 4
	.p2align 3
.L8:
	mov	r8, r10
	add	r10, 1
	and	r8d, 63
	mov	r8, QWORD PTR [rcx+r8*8]
	lea	r9, 8[0+r8*4]
	add	rax, r9
	cmp	rdx, r10
	jne	.L8
.L7:
	ret
	.seh_endproc
	.p2align 4
	.globl	"w1_naive_s1"
	.def	"w1_naive_s1";	.scl	2;	.type	32;	.endef
	.seh_proc	"w1_naive_s1"
"w1_naive_s1":
	.seh_endprologue
	mov	rax, r8
	test	rdx, rdx
	jle	.L11
	xor	r8d, r8d
	.p2align 5
	.p2align 4
	.p2align 3
.L12:
	mov	r9, r8
	add	r8, 1
	and	r9d, 63
	add	rax, QWORD PTR [rcx+r9*8]
	add	rax, 8
	cmp	rdx, r8
	jne	.L12
.L11:
	ret
	.seh_endproc
	.p2align 4
	.globl	"w1_split_s1"
	.def	"w1_split_s1";	.scl	2;	.type	32;	.endef
	.seh_proc	"w1_split_s1"
"w1_split_s1":
	.seh_endprologue
	mov	rax, r8
	test	rdx, rdx
	jle	.L15
	xor	r10d, r10d
	.p2align 4
	.p2align 3
.L16:
	mov	r8, r10
	add	r10, 1
	and	r8d, 63
	mov	r9, QWORD PTR [rcx+r8*8]
	add	r9, 8
	add	rax, r9
	cmp	rdx, r10
	jne	.L16
.L15:
	ret
	.seh_endproc
	.p2align 4
	.globl	"w2_disp"
	.def	"w2_disp";	.scl	2;	.type	32;	.endef
	.seh_proc	"w2_disp"
"w2_disp":
	.seh_endprologue
	test	r8, r8
	jle	.L21
	lea	r9, [rdx+r8*4]
	xor	eax, eax
	.p2align 5
	.p2align 4
	.p2align 3
.L20:
	movsxd	r8, DWORD PTR [rdx]
	add	rdx, 4
	add	rax, QWORD PTR 8[rcx+r8*8]
	cmp	r9, rdx
	jne	.L20
	ret
	.p2align 4,,10
	.p2align 3
.L21:
	xor	eax, eax
	ret
	.seh_endproc
	.p2align 4
	.globl	"w2_nodisp"
	.def	"w2_nodisp";	.scl	2;	.type	32;	.endef
	.seh_proc	"w2_nodisp"
"w2_nodisp":
	.seh_endprologue
	test	r8, r8
	jle	.L26
	lea	r9, [rdx+r8*4]
	xor	eax, eax
	.p2align 4
	.p2align 4
	.p2align 3
.L25:
	movsxd	r8, DWORD PTR [rdx]
	add	rdx, 4
	add	rax, QWORD PTR [rcx+r8*8]
	cmp	r9, rdx
	jne	.L25
	ret
	.p2align 4,,10
	.p2align 3
.L26:
	xor	eax, eax
	ret
	.seh_endproc
	.p2align 4
	.globl	"w3_stride"
	.def	"w3_stride";	.scl	2;	.type	32;	.endef
	.seh_proc	"w3_stride"
"w3_stride":
	.seh_endprologue
	test	rdx, rdx
	jle	.L31
	lea	rax, [rdx+rdx*2]
	add	rcx, 8
	lea	rdx, [rcx+rax*8]
	xor	eax, eax
	.p2align 4
	.p2align 4
	.p2align 3
.L30:
	add	rax, QWORD PTR [rcx]
	add	rcx, 24
	cmp	rcx, rdx
	jne	.L30
	ret
	.p2align 4,,10
	.p2align 3
.L31:
	xor	eax, eax
	ret
	.seh_endproc
	.ident	"GCC: (MinGW-W64 x86_64-ucrt-posix-seh, built by Brecht Sanders, r3) 16.2.0"
