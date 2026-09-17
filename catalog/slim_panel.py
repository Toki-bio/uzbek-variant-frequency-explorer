#!/usr/bin/env python3
"""Produce a web-sized panel file.

panel_summary.json is ~5.7MB, almost entirely per-carrier genotype records
(every carrier of every variant in every cohort). The table view only needs
counts, frequencies, and enough carrier names for a tooltip - so the full
record set is kept on disk / in the repo for analysis, and the web page
loads this slimmed copy instead.

Nothing is rounded or recomputed here: counts and frequencies are copied
verbatim. Only the tail of each carrier list is dropped, and the number
dropped is recorded per entry so the page can say so honestly.

Usage: slim_panel.py <panel_summary.json> <out panel_web.json> [keep_carriers]
"""
import json
import sys
from pathlib import Path

src, out = sys.argv[1], sys.argv[2]
KEEP = int(sys.argv[3]) if len(sys.argv) > 3 else 12

data = json.loads(Path(src).read_text(encoding="utf-8"))

for v in data["variants"]:
    for d in v["datasets"].values():
        carriers = d.get("carriers") or []
        if len(carriers) > KEEP:
            d["carriers"] = carriers[:KEEP]
            d["carriers_truncated"] = len(carriers) - KEEP
        # carrier_count / cohort_size / carrier_frequency are left untouched.

# GSA coverage: keep every SNP (needed for the gene list) but drop nothing -
# it is only ~220KB combined, already small enough.

data["_slim_note"] = (
    f"Carrier lists truncated to {KEEP} entries per variant/cohort for page weight; "
    "carrier_count, cohort_size and carrier_frequency are the full, unmodified values. "
    "The complete per-carrier records are in catalog/panel_summary.json."
)

Path(out).write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
print(f"{Path(src).stat().st_size/1e6:.1f}MB -> {Path(out).stat().st_size/1e6:.1f}MB")
