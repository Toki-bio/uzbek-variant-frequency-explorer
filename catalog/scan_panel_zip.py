#!/usr/bin/env python3
"""Scanner for externally-delivered targeted-panel datasets shipped as
per-sample zips (cardio_oct: provider ddm, panel extCAS_v2, GRCh37).

Reads zip members via streaming - nothing is extracted to disk. The big
raw-FASTQ zips are inventoried by name/size only; the small deliverable zips
are opened to read the VCF header (panel name, build, provider) and to count
variants, flagged low-coverage regions, and report files.

Usage: scan_panel_zip.py <dir> > scan.json
"""
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

SAMPLE_RE = re.compile(r"^sample_(.+?)(?: \(\d+\))?\.zip$", re.I)


def read_vcf_meta(zf, name):
    meta = {"variants": 0, "chroms": set()}
    with zf.open(name) as fh:
        for raw in io.TextIOWrapper(fh, encoding="utf-8", errors="ignore"):
            if raw.startswith("##"):
                m = re.match(r"##(genePanel|provider|genome-build|reference|fileDate)=(.*)", raw.strip())
                if m:
                    meta[m.group(1)] = m.group(2)
            elif raw.startswith("#"):
                continue
            else:
                meta["variants"] += 1
                meta["chroms"].add(raw.split("\t", 1)[0])
    meta["chroms"] = sorted(meta["chroms"], key=lambda c: (len(c), c))
    return meta


def scan(d: Path):
    samples = defaultdict(lambda: {"raw_reads": None, "deliverable": None})
    for z in sorted(d.glob("*.zip")):
        m = SAMPLE_RE.match(z.name)
        if not m:
            continue
        sid = m.group(1)
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
            if any(n.lower().endswith((".fastq.gz", ".fq.gz")) for n in names):
                samples[sid]["raw_reads"] = {
                    "zip": z.name, "size_mb": round(z.stat().st_size / 1e6, 1),
                    "files": len(names),
                }
            else:
                vcf = next((n for n in names if n.lower().endswith(".vcf")), None)
                dl = {
                    "zip": z.name, "size_mb": round(z.stat().st_size / 1e6, 1),
                    "vcf": vcf,
                    "qa_report_pdf": next((n for n in names if n.lower().endswith(".pdf")), None),
                    "flagged_regions_txt": next((n for n in names if "flagged" in n.lower()), None),
                    "variant_table_txt": next((n for n in names if n.lower().endswith(".txt") and "flagged" not in n.lower()), None),
                }
                if vcf:
                    dl.update(read_vcf_meta(zf, vcf))
                fr = dl.get("flagged_regions_txt")
                if fr:
                    with zf.open(fr) as fh:
                        dl["flagged_low_coverage_regions"] = sum(
                            1 for l in io.TextIOWrapper(fh, errors="ignore")
                            if l.strip() and not l.startswith(("#", "id\t")))
                samples[sid]["deliverable"] = dl

    out = {}
    panels, builds, providers = set(), set(), set()
    for sid, s in samples.items():
        dl = s["deliverable"] or {}
        if dl.get("genePanel"): panels.add(dl["genePanel"])
        if dl.get("genome-build"): builds.add(dl["genome-build"])
        if dl.get("provider"): providers.add(dl["provider"])
        out[sid] = {
            "convention": "external_panel_zip",
            "complete": bool(dl.get("vcf")),
            "file_count": (2 if s["raw_reads"] else 0) + (4 if dl else 0),
            "raw_reads_zip": (s["raw_reads"] or {}).get("zip"),
            "raw_reads_mb": (s["raw_reads"] or {}).get("size_mb"),
            "vcf": dl.get("vcf"),
            "variants": dl.get("variants"),
            "flagged_low_coverage_regions": dl.get("flagged_low_coverage_regions"),
            "qa_report_pdf": dl.get("qa_report_pdf"),
            "variant_table_txt": dl.get("variant_table_txt"),
        }
    n_complete = sum(1 for v in out.values() if v["complete"])
    return {
        "root_path": str(d),
        "sample_count": len(out),
        "samples_complete": n_complete,
        "samples_incomplete": len(out) - n_complete,
        "status": "complete" if out and n_complete == len(out) else ("partial" if n_complete else "pending"),
        "panel": sorted(panels), "genome_build": sorted(builds), "provider": sorted(providers),
        "samples": dict(sorted(out.items())),
        "has": {
            "per_sample": bool(out),
            "raw_reads": any(v["raw_reads_zip"] for v in out.values()),
            "panel_variants": n_complete > 0,
            "clinical_reports": any(v["qa_report_pdf"] for v in out.values()),
            "coverage_flags": any(v["flagged_low_coverage_regions"] is not None for v in out.values()),
            "allele_freqs": False, "panel_coverage": False, "sample_qc": False,
            "imputation": False, "popgen": False, "sub_cohorts": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(scan(Path(sys.argv[1])), indent=2))
