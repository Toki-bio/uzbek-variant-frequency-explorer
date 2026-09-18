#!/usr/bin/env python3
"""Turn the lab's ORIGINAL data-sources.html into the data-aware catalog page
by exact-match patching. Every anchor must match verbatim or this aborts, so
the diff against the original stays small and reviewable. Layout, palette,
sort/filter/select/drag/notes - all the original's - are left byte-identical.

What changes:
  1. the hand-typed host meta-row is filled from catalog.host
  2. `var DATA=[...]` is replaced by a loader that fetches catalog.json and
     maps it INTO the original row shape (id/date/name/desc/n/nl/tech/tl/path/
     gb/sl/status/kv/tree/note), so render() needs no changes to its columns
  3. the expanded row gains data-aware sections between "File structure" and
     "Notes", each gated on live_scan.has.<flag>
  4. a tab bar adds "Focal panel" and "Samples across runs" as extra views;
     the original table is the default view and is untouched
  5. path cells become browse links when SHARE_BASE is set

Usage: patch_original.py <original.html> <extensions.js> <out.html>
"""
import re
import sys
from pathlib import Path

orig, ext_js, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
html = orig.read_text(encoding="utf-8")
ext = ext_js.read_text(encoding="utf-8")
changes = []


def replace_once(anchor, replacement, label):
    global html
    n = html.count(anchor)
    if n != 1:
        sys.exit(f"ABORT [{label}]: anchor found {n} times, expected exactly 1:\n{anchor[:120]!r}")
    html = html.replace(anchor, replacement, 1)
    changes.append(label)


# 1. host meta-row -> ids, filled by JS
replace_once(
    '<div class="m-cell"><span class="m-k">Host</span><span class="m-v">biotech2024</span></div>',
    '<div class="m-cell"><span class="m-k">Host</span><span class="m-v" id="mh-host">…</span></div>', "meta host")
replace_once(
    '<div class="m-cell"><span class="m-k">IP</span><span class="m-v">100.104.25.22</span></div>',
    '<div class="m-cell"><span class="m-k">IP</span><span class="m-v" id="mh-ip">…</span></div>', "meta ip")
replace_once(
    '<div class="m-cell"><span class="m-k">OS</span><span class="m-v">RHEL 8.6</span></div>',
    '<div class="m-cell"><span class="m-k">OS</span><span class="m-v" id="mh-os">…</span></div>', "meta os")
replace_once(
    '<div class="m-cell"><span class="m-k">DRAGEN</span><span class="m-v">4.5.4 / 4.4.4</span></div>',
    '<div class="m-cell"><span class="m-k">DRAGEN</span><span class="m-v" id="mh-dragen">…</span></div>', "meta dragen")
replace_once(
    '<div class="m-cell"><span class="m-k">RAM</span><span class="m-v">503 GB</span></div>',
    '<div class="m-cell"><span class="m-k">RAM</span><span class="m-v" id="mh-ram">…</span></div>', "meta ram")
replace_once(
    '<div class="m-cell"><span class="m-k">/staging free</span><span class="m-v">7.1 TB / 14 TB</span></div>',
    '<div class="m-cell"><span class="m-k">/staging free</span><span class="m-v" id="mh-free">…</span></div>', "meta free")
replace_once(
    '<div class="m-cell"><span class="m-k">Scanned</span><span class="m-v">2026-05-19</span></div>',
    '<div class="m-cell"><span class="m-k">Data generated</span><span class="m-v" id="mh-gen">…</span></div>', "meta scanned")

# 2. tech filter gains the panel type
replace_once(
    '      <option value="wes">WES</option>\n    </select>',
    '      <option value="wes">WES</option>\n      <option value="panel">Targeted panel</option>\n    </select>', "tech filter")

# 3. tab bar before the table; wrap the table in the datasets view
replace_once(
    '<div class="tbl-wrap">',
    '<div class="vtabs">'
    '<span class="vtab active" data-view="datasets">Datasets</span>'
    '<span class="vtab" data-view="panel">Focal panel: cardiomyopathy</span>'
    '<span class="vtab" data-view="samples">Samples across runs</span>'
    '</div>\n'
    '<div class="vview active" id="vv-datasets">\n<div class="tbl-wrap">', "tab bar")
replace_once(
    '</table>\n',
    '</table>\n</div>\n</div>\n'
    '<div class="vview" id="vv-panel"></div>\n'
    '<div class="vview" id="vv-samples"></div>\n', "close datasets view")

# 4. replace the hardcoded DATA array with an empty one (loader fills it)
m = re.search(r"var DATA=\[.*?\];\n", html, flags=re.S)
if not m:
    sys.exit("ABORT: var DATA=[...] block not found")
html = html[:m.start()] + "var DATA=[]; /* filled by loadCatalog() from catalog.json */\n" + html[m.end():]
changes.append("DATA -> loader")

# 5. path cell becomes a browse link when a share base is configured
replace_once(
    "'<td class=\"path-v\" title=\"'+d.path+'\">'+d.path+'</td>'+",
    "'<td class=\"path-v\" title=\"'+d.path+'\">'+(shareLink(d.id,'raw')?'<a class=\"plink\" href=\"'+shareLink(d.id,'raw')+'\" target=\"_blank\" rel=\"noopener\" onclick=\"event.stopPropagation()\">'+d.path+'</a>':d.path)+'</td>'+",
    "path link")

# 6. status cell: real derived status word, not just complete/pending
replace_once(
    "    var stHtml=d.status==='complete'\n"
    "      ?'<span class=\"dot d-ok\"></span>Complete'\n"
    "      :'<span class=\"dot d-pend\"></span>Pending';",
    "    var stHtml=statusHtml(d);", "status cell")

# 7. technology badge class for the panel type
replace_once(
    "    var tc=d.tech==='wgs'?'b-wgs':d.tech==='wes'?'b-wes':'b-array';",
    "    var tc=d.tech==='wgs'?'b-wgs':d.tech==='wes'?'b-wes':d.tech==='panel'?'b-panel':'b-array';", "tech badge")

# 8. gated data-aware sections inserted between File structure and Notes
replace_once(
    "      '<div class=\"dp-sec\"><h4>File structure</h4>'+trH+'</div>'+\n"
    "      '<div class=\"nw\"><h4>Notes</h4>'+",
    "      '<div class=\"dp-sec\"><h4>File structure</h4>'+trH+'</div>'+\n"
    "      gatedSections(d)+\n"
    "      '<div class=\"nw\"><h4>Notes</h4>'+", "gated sections")

# 9. extensions (loader, gated sections, tabs, panel & samples views) before </script>
replace_once("\n</script>\n</body>", "\n" + ext + "\n</script>\n</body>", "extensions")

# 10. extra CSS appended inside the original <style>
extra_css = """
/* ---- additions: kept in the original's grey palette ---- */
.vtabs{display:flex;gap:2px;margin:0 0 10px;border-bottom:1px solid #e5e7eb}
.vtab{padding:7px 14px;font-size:13px;color:#6b7280;cursor:pointer;border-bottom:2px solid transparent}
.vtab.active{color:#111;border-bottom-color:#111;font-weight:600}
.vview{display:none}.vview.active{display:block}
.b-panel{background:#fef3c7;color:#92400e}
.plink{color:inherit;text-decoration:none;border-bottom:1px dotted #9ca3af}.plink:hover{border-bottom-style:solid}
.gs{margin-top:10px}.gs h4{margin:0 0 4px}
.gs .gs-hint{font-size:11px;color:#9ca3af;margin-bottom:6px}
.gs table{border-collapse:collapse;font-size:12px;width:100%}
.gs th{font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:#9ca3af;text-align:left;padding:3px 6px;border-bottom:1px solid #e5e7eb}
.gs td{padding:3px 6px;border-bottom:1px solid #f3f4f6;font-variant-numeric:tabular-nums}
.gs td.r{text-align:right}
.chip{display:inline-block;font-size:11px;background:#f3f4f6;border:1px solid #e5e7eb;border-radius:3px;padding:1px 6px;margin:1px 2px 1px 0}
.derived{font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.04em;margin-left:6px}
.conflict{background:#fef3c7;border-left:3px solid #d97706;padding:4px 8px;font-size:12px;color:#92400e;margin:4px 0}
.browse a{margin-right:10px;font-size:12px}
.bigtbl{overflow-x:auto}.bigtbl table{width:100%;border-collapse:collapse;font-size:12.5px;background:#fff}
.bigtbl th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.04em;color:#6b7280;padding:7px 8px;border-bottom:2px solid #e5e7eb;cursor:pointer;white-space:nowrap}
.bigtbl td{padding:6px 8px;border-bottom:1px solid #f3f4f6;vertical-align:top}
.bigtbl tr:nth-child(even) td{background:#f9fafb}
.mini{font-size:11px;color:#6b7280}
.sub-toolbar{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0}
.sub-toolbar input,.sub-toolbar select{font-size:12px;padding:5px 8px;border:1px solid #d1d5db;border-radius:4px}
.stat-row{display:flex;gap:22px;margin:6px 0 10px;font-variant-numeric:tabular-nums}
.stat-row b{font-size:18px;display:block}.stat-row span{font-size:10px;color:#9ca3af;text-transform:uppercase}
#loadState{margin:8px 0;padding:8px 12px;border:1px solid #e5e7eb;border-radius:4px;font-size:12.5px;background:#fff}
"""
replace_once("\n</style>", extra_css + "\n</style>", "extra css")

# 11. loading banner after the meta-row
replace_once('<div class="toolbar">', '<div id="loadState">Loading catalog data…</div>\n<div class="toolbar">', "load banner")

out.write_text(html, encoding="utf-8")
print(f"patched -> {out} ({len(html)} bytes); {len(changes)} changes:")
for c in changes:
    print("  -", c)
