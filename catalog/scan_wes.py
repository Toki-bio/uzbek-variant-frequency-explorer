#!/usr/bin/env python3
"""Scan a WES/WGS clinical_reports directory and produce a fact-based
inventory: which samples exist, which output files each has, and an
inferred completion status. No hand-maintained metadata here - only
what can be observed on disk.

Usage: scan_wes.py <clinical_reports_dir> > wes_scan.json
"""
import json
import re
import sys
from pathlib import Path

# Files that make up a "complete" per-sample WES run, based on the
# observed cardio_wes_v350432671 output shape (bcftools/sarek convention).
EXPECTED_SUFFIXES = [
    ".bcftools.raw.vcf.gz",
    ".bcftools.hard-filtered.vcf.gz",
    ".bcftools.annotated.vcf.gz",
    ".markdup.cram",
    ".case.pathogenic.jsonl",
    ".report.html",
]

# DRAGEN's own native single-sample germline pipeline output convention
# (e.g. cardio_main: Cardio1.bam, Cardio1.hard-filtered.vcf.gz, ...) - a
# second, distinct convention seen in the wild alongside the bcftools one above.
DRAGEN_NATIVE_SUFFIXES = [
    ".bam",
    ".hard-filtered.vcf.gz",
    ".hard-filtered.vcf.annotated.json.gz",
    ".wgs_coverage_metrics.csv",
    ".roh.bed",
]

# Three naming conventions observed in the wild: "sampleNN.<suffix>" for
# bcftools/sarek pipeline output, "sample_<Name>.zip" for a different lab's
# per-sample zip deliverable, and "<Prefix><N>.<suffix>" for DRAGEN's own
# native single-sample germline output (e.g. Cardio1.bam).
SAMPLE_RE = re.compile(r"^(sample\d+)\.")
SAMPLE_ZIP_RE = re.compile(r"^sample_([^.]+?)(?: \(\d+\))?\.zip$", re.IGNORECASE)
DRAGEN_NATIVE_RE = re.compile(r"^([A-Za-z]+\d+)\.")

# Raw FASTQ naming: <name_or_num>_S\d+_L\d+_R[12]_001.fastq.gz (Illumina/MGI
# style) or <barcode>_L\d+_<name>_[12].fq.gz. Used as a fallback so a raw,
# unprocessed sequencing directory reports "N raw samples, 0 processed"
# instead of a flat, misleading "0 samples".
FASTQ_RE = re.compile(r"^(.+?)_(?:R[12]|[12])(?:_001)?\.(?:fastq|fq)\.gz$", re.IGNORECASE)


def scan(clinical_reports_dir: Path) -> dict:
    if not clinical_reports_dir.is_dir():
        return {"error": f"not a directory: {clinical_reports_dir}", "samples": {}}

    files_by_sample: dict[str, list[str]] = {}
    cohort_level_files: list[str] = []
    raw_fastq_samples: set[str] = set()
    for f in clinical_reports_dir.iterdir():
        if not f.is_file():
            continue
        m = SAMPLE_RE.match(f.name) or SAMPLE_ZIP_RE.match(f.name) or DRAGEN_NATIVE_RE.match(f.name)
        if m:
            files_by_sample.setdefault(m.group(1), []).append(f.name)
            continue
        fq = FASTQ_RE.match(f.name)
        if fq:
            raw_fastq_samples.add(fq.group(1))
            cohort_level_files.append(f.name)
            continue
        cohort_level_files.append(f.name)

    samples = {}
    for sample_id, files in sorted(files_by_sample.items()):
        present_sarek = [suf for suf in EXPECTED_SUFFIXES if any(fn.endswith(suf) for fn in files)]
        present_dragen = [suf for suf in DRAGEN_NATIVE_SUFFIXES if any(fn.endswith(suf) for fn in files)]
        if present_sarek:
            convention, present, expected = "bcftools_sarek", present_sarek, EXPECTED_SUFFIXES
        elif present_dragen:
            convention, present, expected = "dragen_native", present_dragen, DRAGEN_NATIVE_SUFFIXES
        else:
            convention, present, expected = "unrecognized", [], []
        missing = [suf for suf in expected if suf not in present]

        if expected:
            complete = not missing
        else:
            # Unrecognized convention (e.g. per-sample zip deliverable) - can't
            # check against a known suffix set, so completeness just means
            # "at least one output file exists for this sample".
            complete = len(files) > 0

        entry = {
            "file_count": len(files),
            "convention": convention,
            "expected_present": present,
            "expected_missing": missing,
            "complete": complete,
        }
        if convention == "unrecognized":
            entry["files"] = sorted(files)
        samples[sample_id] = entry

    n_complete = sum(1 for s in samples.values() if s["complete"])
    result = {
        "root_path": str(clinical_reports_dir),
        "sample_count": len(samples),
        "samples_complete": n_complete,
        "samples_incomplete": len(samples) - n_complete,
        "status": "complete" if samples and n_complete == len(samples) else
                  ("partial" if n_complete > 0 else "pending"),
        "samples": samples,
        "cohort_level_files": sorted(cohort_level_files),
    }
    if not samples and raw_fastq_samples:
        result["raw_fastq_samples_detected"] = len(raw_fastq_samples)
        result["status"] = "raw_data_only_not_yet_processed"
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <clinical_reports_dir>", file=sys.stderr)
        sys.exit(1)
    result = scan(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
