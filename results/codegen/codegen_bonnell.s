	.file	"codegen.c"
	.intel_syntax noprefix
	.text
	.p2align 4
	.globl	"f_bi4d"
	.def	"f_bi4d";	.scl	2;	.type	32;	.endef
	.seh_proc	"f_bi4d"
"f_bi4d":
	.seh_endprologue
	lea	rax, 8[rcx+rdx*4]
	nop
	nop
	ret
	.seh_endproc
	.p2align 4
	.globl	"f_bid"
	.def	"f_bid";	.scl	2;	.type	32;	.endef
	.seh_proc	"f_bid"
"f_bid":
	.seh_endprologue
	lea	rax, 8[rcx+rdx]
	nop
	nop
	ret
	.seh_endproc
	.p2align 4
	.globl	"f_x2"
	.def	"f_x2";	.scl	2;	.type	32;	.endef
	.seh_proc	"f_x2"
"f_x2":
	.seh_endprologue
	lea	rax, [rcx+rcx]
	nop
	nop
	ret
	.seh_endproc
	.ident	"GCC: (MinGW-W64 x86_64-ucrt-posix-seh, built by Brecht Sanders, r3) 16.2.0"
