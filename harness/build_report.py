#!/usr/bin/env python3
"""Inline results/*.png into an HTML template -> one self-contained report file.

Usage: python build_report.py TEMPLATE.html OUT.html [OUT2.html ...]
"""
import base64
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")


def inline(m):
    data = base64.b64encode(open(os.path.join(RES, m.group(1)), "rb").read()).decode()
    return f'src="data:image/png;base64,{data}"'


html = re.sub(r'src="(fig_[\w]+\.png)"', inline, open(sys.argv[1], encoding="utf-8").read())
for out in sys.argv[2:]:
    open(out, "w", encoding="utf-8").write(html)
    print(f"wrote {out} ({len(html) // 1024} KB)")
