#!/usr/bin/env python3
"""Scan a GSA/array pipeline root directory and report the furthest
completed stage, based on which PLINK filesets actually exist on disk.

GSA pipelines here are staged (GenomeStudio QC -> PLINK QC steps ->
post-imputation), and "done" is only ever implicit in which final-stage
files exist - there's no single status marker. This scanner makes that
implicit signal explicit.

Usage: scan_gsa.py <root_dir> > gsa_scan.json
"""
import json
import re
import sys
from pathlib import Path

# PLINK triplet + QC output extensions we look for, for the "most complete"
# fileset found anywhere under the root. Covers both PLINK1.9 naming
# (.frq/.hwe/.imiss/.lmiss) and PLINK2 naming (.smiss/.vmiss) - a real
# run (gwas2026_2) used PLINK2 conventions and was falsely flagged
# incomplete before this was widened.
PLINK_CORE = {".bed", ".bim", ".fam"}
PLINK_QC = {".frq", ".hwe", ".het", ".imiss", ".lmiss", ".smiss", ".vmiss"}

# Separate QC evidence that doesn't share a PLINK fileset basename with the
# core .bed/.bim/.fam (e.g. GWAS2026-2/qc/*.het, *.king.*, *.pca.eigenvec) -
# scored per-directory as a fallback signal, not tied to one fileset name.
QC_SIDE_FILE_MARKERS = ("het", "king", "pca.eigenvec", "ibd", "miss")


def find_plink_filesets(root: Path) -> dict[str, set[str]]:
    """Return {basename_without_ext: {extensions found}} across the whole tree."""
    filesets: dict[str, set[str]] = {}
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        stem, ext = f.stem, f.suffix
        base = str(f.parent / stem)
        if ext in PLINK_CORE or ext in PLINK_QC:
            filesets.setdefault(base, set()).add(ext)
    return filesets


def scan(root: Path) -> dict:
    if not root.is_dir():
        return {"error": f"not a directory: {root}"}

    filesets = find_plink_filesets(root)

    # Rank filesets by completeness: full core+QC > core only. Prefer paths
    # under a directory literally named like a late pipeline stage
    # (e.g. "3_post-imputation") when scores tie, since multiple staged
    # PLINK filesets can coexist and a naive "most extensions" pick is
    # fragile to that.
    # Explicit stage ordering, not just a binary "is it final" flag - staged
    # PLINK pipelines here go raw -> sampleqc -> geno10 -> varqc (-> final/
    # post-imputation), and every stage shares identical .bed/.bim/.fam
    # extensions, so extension-count alone can't tell them apart (this is
    # exactly how gwas2026_2 got the wrong fileset picked: raw and varqc
    # scored equal on extensions, and raw happened to sort first).
    STAGE_ORDER = ["raw", "mind20", "sampleqc", "dedup", "geno10", "snpqc",
                   "varqc", "final_clean", "final", "post-imputation", "post_imputation"]

    def stage_hint(base: str) -> int:
        # A filename can contain multiple stage keywords (e.g.
        # "ConvSK_mind20_dedup_snpqc" matches "mind20", "dedup", AND
        # "snpqc") - take the latest (highest-ranked) one present, not the
        # first keyword found in STAGE_ORDER.
        lowered = base.lower()
        matches = [rank for rank, keyword in enumerate(STAGE_ORDER) if keyword in lowered]
        return max(matches) if matches else -1

    best_base, best_exts = None, set()
    for base, exts in filesets.items():
        score = (len(exts & PLINK_CORE) * 10 + len(exts & PLINK_QC), stage_hint(base))
        best_score = (len(best_exts & PLINK_CORE) * 10 + len(best_exts & PLINK_QC),
                      stage_hint(best_base) if best_base else -1)
        if score > best_score:
            best_base, best_exts = base, exts

    # QC evidence that lives as separate side-files (not sharing the core
    # fileset's basename) rather than same-basename siblings - e.g. a
    # dedicated qc/ directory with *_het.het, *_king.*, *_pca.eigenvec, etc.
    qc_side_files = sorted(
        str(f) for f in root.rglob("*")
        if f.is_file() and any(m in f.name.lower() for m in QC_SIDE_FILE_MARKERS)
    )

    if best_base is None:
        stage = "no_plink_output_found"
    elif PLINK_CORE.issubset(best_exts) and (best_exts & PLINK_QC or qc_side_files):
        stage = "post_imputation_qc_complete"
    elif PLINK_CORE.issubset(best_exts):
        stage = "plink_fileset_present_no_full_qc"
    else:
        stage = "partial_plink_fileset"

    # Surface ambiguity rather than hide it: list any other fileset that's
    # as complete as the chosen "best" one, so a human can catch a wrong pick.
    best_completeness = (len(best_exts & PLINK_CORE), len(best_exts & PLINK_QC))
    ties = [b for b, e in filesets.items()
            if b != best_base and (len(e & PLINK_CORE), len(e & PLINK_QC)) >= best_completeness]

    # Real sample count: count rows in the best fileset's .fam file directly.
    # This was missing entirely before - the scanner reported which fileset
    # exists and its QC stage, but never actually counted samples, so every
    # GSA dataset silently had no sample_count field at all.
    # Emit the actual per-sample records, not just a count. Without these the
    # detail view has nothing to list and renders "Samples (0)" for every
    # array dataset while the row above it correctly shows n=48/1074/etc.
    # .fam delimiting is inconsistent here (ALSU space-separated, rescan48
    # tab-separated), so split on any whitespace.
    sample_count = None
    samples = {}
    if best_base is not None:
        fam_path = Path(best_base + ".fam")
        if fam_path.exists():
            with open(fam_path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        samples[parts[1]] = {
                            "convention": "plink_fileset",
                            "fileset": Path(best_base).name,
                            "fid": parts[0],
                            "complete": True,
                        }
            sample_count = len(samples)

    # Capability flags, each tied to a concrete file observed under root.
    # Match on FILE NAMES, not full paths: gwas96/rescan48 live under a
    # directory literally called admixture_analysis/, which made a path
    # substring match report population-genetics output they don't have.
    files = [f for f in root.rglob("*") if f.is_file()]
    names = [f.name.lower() for f in files]
    rels  = [str(f.relative_to(root)).lower() for f in files]
    def any_name(*subs): return any(s in n for n in names for s in subs)
    def any_rel(*subs):  return any(s in r for r in rels  for s in subs)
    # Population-genetics outputs: ADMIXTURE .Q/.P files, Fst, ROH, or a PCA
    # that is NOT just the sample-QC PCA sitting under a qc/ directory.
    popgen_pca = any(r.endswith((".eigenvec", ".eigenval")) and "qc/" not in r for r in rels)
    popgen_adm = any(re.fullmatch(r".+\.\d+\.[qp]", n) for n in names)  # e.g. UZB_v2_admix.5.Q
    has = {
        "per_sample": bool(samples),
        # raw array scans: IDAT/GTC intensity files or Illumina .sdf scan descriptors
        "raw_reads": any_name(".idat", ".gtc", ".sdf"),
        "panel_variants": False,
        "clinical_reports": False,
        "coverage_flags": False,
        # .frq/.afreq present, or computable from the .bed by plink --freq
        "allele_freqs": bool(best_base) and (bool(best_exts & {".frq", ".afreq"}) or ".bed" in best_exts),
        "allele_freqs_precomputed": bool(best_exts & {".frq", ".afreq"}),
        "panel_coverage": bool(best_base) and ".bim" in best_exts,
        "sample_qc": bool(best_exts & PLINK_QC) or bool(qc_side_files),
        # The scanned root itself may sit INSIDE an imputation output tree
        # (alsu_expanded: .../imputation_results/hq_filtered/), in which case
        # no path beneath it contains the marker - so check the root too.
        "imputation": any_rel("post_imputation/", "post-imputation/", "imputation_results/")
                      or any_name(".dose.vcf")
                      or any(m in str(root).lower() for m in ("post_imputation", "post-imputation", "imputation_results")),
        "popgen": popgen_pca or popgen_adm or any_name(".fst", ".hom", ".hom.indiv", ".roh"),
        "sub_cohorts": False,
    }
    return {
        "root_path": str(root),
        "plink_filesets_found": len(filesets),
        "best_fileset": best_base,
        "best_fileset_extensions": sorted(best_exts),
        "sample_count": sample_count,
        "samples": samples,
        "inferred_stage": stage,
        "equally_or_more_complete_alternatives": sorted(ties),
        "qc_side_files_found": len(qc_side_files),
        "has": has,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <root_dir>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(scan(Path(sys.argv[1])), indent=2))
