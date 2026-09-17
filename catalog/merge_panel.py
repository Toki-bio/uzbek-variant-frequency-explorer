#!/usr/bin/env python3
"""Merge the sequencing variant-carrier panel summary with the GSA/array
SNP-coverage panel scans into one combined output for the viewer."""
import json
import sys

seq_summary_path, out_path = sys.argv[1], sys.argv[2]
gsa_paths = sys.argv[3:]

data = json.loads(open(seq_summary_path, encoding="utf-8").read())
data["gsa_coverage"] = {}
for p in gsa_paths:
    gsa = json.loads(open(p, encoding="utf-8").read())
    data["gsa_coverage"][gsa["dataset"]] = gsa

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)
print(f"merged -> {out_path}, gsa datasets: {list(data['gsa_coverage'].keys())}")
