#!/usr/bin/env python3
"""Generate the standalone Artifact page FROM viewer.html - single source of
truth. The Artifact CSP blocks network fetches, so the fetch bootstrap block
(delimited by BOOTSTRAP-START/END markers) is replaced with inlined data;
everything else - markup, CSS, every render function - is byte-identical to
the code running on the live site.

Keeping a second hand-maintained copy of the viewer is exactly the drift that
caused real bugs earlier in this project, so it is deliberately avoided.

Usage: build_artifact.py viewer.html catalog.json panel_web.json samples.json out.html
"""
import re
import sys
from pathlib import Path

viewer, catalog_p, panel_p, samples_p, out_p = sys.argv[1:6]

html = Path(viewer).read_text(encoding="utf-8")

START = "/* BOOTSTRAP-START"
END = "/* BOOTSTRAP-END */"
if START not in html or END not in html:
    sys.exit("ERROR: bootstrap markers not found in viewer.html - refusing to "
             "guess where the fetch block is.")

start = html.index(START)
end = html.index(END) + len(END)

inlined = (
    f"const __CATALOG__ = {Path(catalog_p).read_text(encoding='utf-8')};\n"
    f"const __PANEL__ = {Path(panel_p).read_text(encoding='utf-8')};\n"
    f"const __SAMPLES__ = {Path(samples_p).read_text(encoding='utf-8')};\n"
    "(function(){\n"
    "  CATALOG = __CATALOG__; PANEL = __PANEL__; SAMPLES = __SAMPLES__;\n"
    "  document.getElementById('loadState').style.display = 'none';\n"
    "  document.getElementById('genStamp').textContent =\n"
    "    'static snapshot - live: 10.10.8.149:8090 and GitHub Pages';\n"
    "  renderSummary(); renderDatasets();\n"
    "  renderPanelNote(); populateGeneFilter();\n"
    "  renderPanelSummary(); renderPanel(); renderGsaCoverage();\n"
    "  renderSamplesTab();\n"
    "})();\n"
)

html = html[:start] + inlined + html[end:]

# The Artifact wrapper supplies <!doctype>/<html>/<head>/<body>.
html = re.sub(r"^.*?<title>", "<title>", html, count=1, flags=re.S)
html = html.replace("</head>", "", 1).replace("<body>", "", 1)
html = html.replace("</body>", "").replace("</html>", "")

Path(out_p).write_text(html, encoding="utf-8")
print(f"wrote {out_p} ({Path(out_p).stat().st_size/1e6:.1f}MB)")
