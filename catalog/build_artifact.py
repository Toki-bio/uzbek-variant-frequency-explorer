#!/usr/bin/env python3
"""Standalone build from the single page source: replaces the fetch block
(BOOTSTRAP-START/END) with inlined data and one call to onCatalogLoaded().
Everything else - markup, CSS, every function - is byte-identical to the
served page. Refuses to guess if the markers are missing.

Usage: build_artifact.py page.html catalog.json panel_web.json samples.json out.html [--fragment]
"""
import re, sys
from pathlib import Path

page, cat_p, pan_p, sam_p, out_p = sys.argv[1:6]
fragment = "--fragment" in sys.argv
html = Path(page).read_text(encoding="utf-8")
START, END = "/* BOOTSTRAP-START", "/* BOOTSTRAP-END */"
if START not in html or END not in html:
    sys.exit("ERROR: bootstrap markers not found - refusing to guess where the fetch block is.")
s, e = html.index(START), html.index(END) + len(END)
inlined = (
    f"var __CATALOG__ = {Path(cat_p).read_text(encoding='utf-8')};\n"
    f"var __PANEL__ = {Path(pan_p).read_text(encoding='utf-8')};\n"
    f"var __SAMPLES__ = {Path(sam_p).read_text(encoding='utf-8')};\n"
    "onCatalogLoaded(__CATALOG__, __PANEL__, __SAMPLES__, []);\n"
    "document.getElementById('mh-gen').textContent += ' (static snapshot)';\n"
)
html = html[:s] + inlined + html[e:]
if fragment:  # for the claude.ai Artifact wrapper, which supplies the document shell
    html = re.sub(r"^.*?<title>", "<title>", html, count=1, flags=re.S)
    html = html.replace("</head>", "", 1).replace("<body>", "", 1).replace("</body>", "").replace("</html>", "")
Path(out_p).write_text(html, encoding="utf-8")
print(f"wrote {out_p} ({Path(out_p).stat().st_size/1e6:.1f}MB)")
