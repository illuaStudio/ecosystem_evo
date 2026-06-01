#!/usr/bin/env python3
"""colony ヘルパーが __future__ より前にあるテストファイルを修正。"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(
    r"^from src\.game\.colony_session import.*\n\n"
    r"def colony\(world\):\n"
    r"    return get_colony_orchestrator\(world\)\n\n",
    re.M,
)

for p in (ROOT / "tests").rglob("*.py"):
    t = p.read_text(encoding="utf-8")
    if not BLOCK.search(t):
        continue
    if t.find("from __future__") > 0 and t.find("def colony") < t.find("from __future__"):
        block = BLOCK.search(t).group(0)
        t2 = BLOCK.sub("", t, count=1)
        fut_idx = t2.find("from __future__")
        if fut_idx >= 0:
            line_end = t2.find("\n", fut_idx) + 1
            t2 = t2[:line_end] + "\n" + block + t2[line_end:].lstrip("\n")
        else:
            t2 = block + t2
        p.write_text(t2, encoding="utf-8")
        print("fixed", p.relative_to(ROOT))
