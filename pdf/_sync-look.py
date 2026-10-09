#!/usr/bin/env python3
"""Copy the notes look from doc-kit into this repository.

This repository builds without doc-kit, so the look lives here as copies:
  preamble.tex     the part between the "the look" and "this repository's
                   environments" markers comes from latex/phunotes.sty
  phu-output.lua   extensions/phu/phu-output.lua (code output, unchanged)
  phu.theme        extensions/phu/phu.theme (code highlighting)
Run it after changing the look in doc-kit:  python3 Notes/pdf/_sync-look.py
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KIT = Path.home() / "code" / "doc-kit"
START = "% --- the look (from doc-kit phunotes.sty)"
END = "% --- this repository's environments"

if not KIT.is_dir():
    sys.exit(f"doc-kit not found at {KIT}")

sty = (KIT / "latex" / "phunotes.sty").read_text()
body = sty[sty.index("% --- fonts"):sty.index("% --- spacing")]
section = (START + " " + "-" * 30 + "\n\\usepackage{caption}\n\\makeatletter\n"
           "\\newif\\ifphu@fonts \\phu@fontstrue\n" + body + "\\makeatother\n\n")
pre = (HERE / "preamble.tex").read_text()
i, j = pre.index(START), pre.index(END)
(HERE / "preamble.tex").write_text(pre[:i] + section + pre[j:])
for name in ("phu-output.lua", "phu.theme"):
    shutil.copy(KIT / "extensions" / "phu" / name, HERE / name)
print("synced preamble.tex, phu-output.lua, phu.theme from", KIT)
