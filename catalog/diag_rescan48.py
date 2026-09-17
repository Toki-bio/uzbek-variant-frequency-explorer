#!/usr/bin/env python3
"""Trace rescan48 (and every dataset) end to end: what the catalog says, what
the crosswalk says, and what the raw .fam actually contains."""
import json
from pathlib import Path

cat = json.load(open("/staging/data_catalog/catalog.json"))
sam = json.load(open("/staging/data_catalog/samples.json"))

print("=== catalog.json: headline sample counts ===")
for ds in cat["datasets"]:
    s = ds.get("live_scan", {})
    n = s.get("sample_count_including_sub_paths", s.get("sample_count"))
    raw = s.get("raw_fastq_samples_detected")
    print(f"  {ds['id']:<26} sample_count={n!r:<8} raw_fastq={raw!r}")

print("\n=== samples.json: crosswalk per-dataset counts ===")
for k, v in sam["dataset_sample_counts"].items():
    print(f"  {k:<26} {v}")

print("\n=== rescan48 raw truth ===")
r = next(d for d in cat["datasets"] if d["id"] == "rescan48")
base = r["live_scan"].get("best_fileset")
print(f"  best_fileset: {base}")
fam = Path(str(base) + ".fam")
print(f"  .fam exists : {fam.exists()}")
if fam.exists():
    lines = [l for l in fam.read_text(errors="ignore").splitlines() if l.strip()]
    print(f"  .fam lines  : {len(lines)}")
    print("  first 3 raw lines:")
    for l in lines[:3]:
        print(f"    {l!r}")
    ids = [l.split()[1] for l in lines if len(l.split()) >= 2]
    print(f"  parsed IIDs : {len(ids)}  distinct: {len(set(ids))}")
    print(f"  sample IIDs : {ids[:5]}")

print("\n=== is rescan48 present in the crosswalk index at all? ===")
hits = [k for k, v in sam["samples"].items() if "rescan48" in v["datasets"]]
print(f"  samples listing rescan48: {len(hits)}")
print(f"  examples: {hits[:5]}")
