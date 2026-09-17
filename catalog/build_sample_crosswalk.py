#!/usr/bin/env python3
"""Layer 4: per-sample cross-dataset aggregation.

Builds samples.json - for every sample ID, which datasets/runs contain it.
This is the join that makes "show me everything ever run on this individual"
possible.

Method is deliberately conservative and stated per-link:
  - "exact_id"  : the same sample ID string appears in two datasets' own
                  sample lists (.fam for arrays, output filenames for
                  sequencing). Strong evidence for arrays within the same
                  ID namespace.
  - "normalized": IDs match after stripping a documented prefix/suffix
                  convention (e.g. PLINK FID_IID doubling).
No genotype-level matching is claimed here - cross-technology identity
(array vs exome) is NOT inferable from IDs alone and is handled separately.

Usage: build_sample_crosswalk.py <catalog.json> <out samples.json>
"""
import json
import re
import sys
from pathlib import Path


def fam_ids(fileset_base):
    """Return sample IDs from a PLINK .fam (IID column, col 2)."""
    fam = Path(fileset_base + ".fam")
    if not fam.exists():
        return []
    ids = []
    for line in fam.read_text(errors="ignore").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            ids.append(parts[1])
    return ids


def seq_ids(scan):
    """Return sample IDs from a sequencing scan's own sample dict."""
    out = list((scan.get("samples") or {}).keys())
    for sub in (scan.get("sub_path_scans") or {}).values():
        out.extend((sub.get("samples") or {}).keys())
    return out


def normalize(sid):
    """Strip documented artefacts so genuinely-equal IDs compare equal.

    - PLINK FID_IID doubling ("03-72_03-72" -> "03-72"), a real artefact
      documented in the ALSU integration notes.
    - surrounding whitespace / case for matching only (original kept).
    """
    s = sid.strip()
    m = re.fullmatch(r"(.+)_\1", s)
    if m:
        s = m.group(1)
    return s.lower()


def main():
    catalog = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    # dataset id -> list of (original_id, normalized_id)
    per_dataset = {}
    for ds in catalog["datasets"]:
        did, scan = ds["id"], ds.get("live_scan", {})
        if ds["type"] == "gsa":
            raw = fam_ids(scan["best_fileset"]) if scan.get("best_fileset") else []
        else:
            raw = seq_ids(scan)
        per_dataset[did] = [(r, normalize(r)) for r in raw]

    # normalized id -> {dataset: [original ids]}
    index = {}
    for did, pairs in per_dataset.items():
        for original, norm in pairs:
            index.setdefault(norm, {}).setdefault(did, []).append(original)

    multi = {k: v for k, v in index.items() if len(v) > 1}

    # Pairwise overlap matrix, for a readable summary.
    dids = sorted(per_dataset)
    overlap = {}
    for i, a in enumerate(dids):
        for b in dids[i + 1:]:
            na = {n for _, n in per_dataset[a]}
            nb = {n for _, n in per_dataset[b]}
            shared = na & nb
            if shared:
                overlap[f"{a} <-> {b}"] = {
                    "shared_sample_count": len(shared),
                    "pct_of_smaller": round(100 * len(shared) / min(len(na), len(nb)), 1),
                    "examples": sorted(shared)[:5],
                }

    out = {
        "method_note": (
            "Links are by sample-ID string match only (exact, or after stripping the "
            "documented PLINK FID_IID doubling artefact). This is reliable WITHIN the "
            "array ID namespace, where all batches inherit the same lab sample IDs. It "
            "does NOT attempt cross-technology identity (array vs exome/genome), which "
            "cannot be established from IDs alone - those cohorts use unrelated ID "
            "schemes (sample01..16, CardioN) and would require genotype concordance."
        ),
        "dataset_sample_counts": {d: len(p) for d, p in per_dataset.items()},
        "samples_in_multiple_datasets": len(multi),
        "pairwise_overlap": overlap,
        "samples": {
            k: {"datasets": {d: ids for d, ids in v.items()}}
            for k, v in sorted(index.items())
        },
    }
    Path(sys.argv[2]).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"total distinct samples: {len(index)}")
    print(f"samples appearing in >1 dataset: {len(multi)}")
    for k, v in overlap.items():
        print(f"  {k}: {v['shared_sample_count']} shared ({v['pct_of_smaller']}% of smaller)")


if __name__ == "__main__":
    main()
