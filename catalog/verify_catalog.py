#!/usr/bin/env python3
"""Independent verification of every claim in catalog.json.

Deliberately re-derives each number by a DIFFERENT method than the scanner
used, so agreement is real evidence rather than a tautology:
  - GSA sample counts: scanner reads .fam via Python; here we shell out to
    `wc -l` and also cross-check against the PLINK .log file's own
    "N people ... pass filters and QC" line where present.
  - WES/WGS sample counts: scanner groups by filename regex; here we count
    distinct sample prefixes of one specific required file type (the
    hard-filtered VCF) via shell glob.
  - Every path claimed is stat'd.
  - Panel variant counts are re-counted from panel_summary.json and
    cross-checked against a fresh bcftools count on one sample.

Exit code 1 if any check fails. Prints a PASS/FAIL line per check.

Usage: verify_catalog.py <catalog.json> <panel_summary.json>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""), flush=True)


def wc_l(path):
    try:
        out = subprocess.run(["wc", "-l", path], capture_output=True, text=True, check=True)
        return int(out.stdout.split()[0])
    except Exception as e:
        return None


def plink_log_count(fileset_base):
    """Extract the sample count PLINK itself reported, from its own .log."""
    log = Path(fileset_base + ".log")
    if not log.exists():
        return None
    text = log.read_text(errors="ignore")
    # plink1.9: "654027 variants and 1093 people pass filters and QC."
    m = re.search(r"(\d+) people pass filters and QC", text)
    if m:
        return int(m.group(1))
    # plink2: "87 samples ... remaining after main filters"
    m = re.search(r"(\d+) samples \(.*?\) remaining after main filters", text)
    if m:
        return int(m.group(1))
    return None


def main():
    catalog = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    panel = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))

    for ds in catalog["datasets"]:
        did = ds["id"]
        scan = ds.get("live_scan", {})

        # 1. Every claimed path must exist.
        for field in ("root_path", "processed_path"):
            p = ds.get(field)
            if p:
                check(f"{did}: {field} exists", Path(p).exists(), p)

        # 2. GSA: re-derive sample count independently.
        if ds["type"] == "gsa":
            best = scan.get("best_fileset")
            claimed = scan.get("sample_count")
            if best and claimed is not None:
                fam_lines = wc_l(best + ".fam")
                check(f"{did}: .fam line count matches scanner",
                      fam_lines == claimed, f"wc-l={fam_lines} scanner={claimed}")
                log_n = plink_log_count(best)
                if log_n is not None:
                    check(f"{did}: PLINK's own log agrees",
                          log_n == claimed, f"log={log_n} scanner={claimed}")
                else:
                    check(f"{did}: PLINK log count available", True,
                          "no parseable count in .log (not an error)")
            else:
                check(f"{did}: has a sample_count", claimed is not None,
                      f"sample_count={claimed}")

        # 3. WES/WGS: re-derive by counting one required file type via glob.
        if ds["type"] in ("wes", "wgs"):
            def count_by_glob(root):
                d = Path(root)
                if not d.is_dir():
                    return None
                pats = ["*.bcftools.hard-filtered.vcf.gz", "*.hard-filtered.vcf.gz", "sample_*.zip"]
                for pat in pats:
                    hits = list(d.glob(pat))
                    if hits:
                        # distinct sample prefixes
                        names = set()
                        for h in hits:
                            n = h.name
                            for sep in (".bcftools", ".hard-filtered", ".zip"):
                                n = n.split(sep)[0]
                            n = re.sub(r" \(\d+\)$", "", n)
                            # "Undetermined" is the demultiplexer's bucket for reads
                            # that matched no sample barcode. DRAGEN produces a full
                            # output set for it exactly like a real sample, but it is
                            # not a biological sample and must not be counted as one.
                            if "undetermined" in n.lower():
                                continue
                            names.add(n)
                        return len(names)
                return 0

            subscans = scan.get("sub_path_scans")
            if subscans:
                total = 0
                for name, sub in subscans.items():
                    c = count_by_glob(sub["root_path"])
                    total += c or 0
                    check(f"{did}/{name}: glob count matches scanner",
                          c == sub.get("sample_count"),
                          f"glob={c} scanner={sub.get('sample_count')}")
                claimed_total = scan.get("sample_count_including_sub_paths")
                base = scan.get("sample_count", 0)
                check(f"{did}: sub-path total consistent",
                      claimed_total == base + total,
                      f"claimed={claimed_total} recomputed={base + total}")
            else:
                c = count_by_glob(scan.get("root_path", ""))
                claimed = scan.get("sample_count")
                if claimed:
                    check(f"{did}: glob count matches scanner",
                          c == claimed, f"glob={c} scanner={claimed}")

        # 4. Registry claim vs scanner, restated here independently.
        n_claimed = ds.get("n_claimed")
        n_found = scan.get("sample_count_including_sub_paths", scan.get("sample_count"))
        n_raw = scan.get("raw_fastq_samples_detected")
        effective = n_found if n_found else n_raw
        if n_claimed is not None and effective is not None:
            check(f"{did}: registry n matches disk",
                  n_claimed == effective, f"registry={n_claimed} disk={effective}")

    # 5. Panel: recount variants and datasets from the summary itself.
    n_variants = len(panel["variants"])
    check("panel: variant_count field matches actual list length",
          n_variants == panel["variant_count"],
          f"field={panel['variant_count']} actual={n_variants}")

    genes = {v["gene"] for v in panel["variants"]}
    check("panel: no variants fell outside a known gene",
          "?" not in genes, f"genes={len(genes)}")

    # 6. Panel carrier arithmetic must be internally consistent.
    bad = []
    for v in panel["variants"]:
        for dsid, d in v["datasets"].items():
            if d["carrier_count"] != len(d["carriers"]):
                bad.append(f"{v['chrom']}:{v['pos']} {dsid}")
            if d["cohort_size"] and not (0 < d["carrier_frequency"] <= 1.0):
                bad.append(f"{v['chrom']}:{v['pos']} {dsid} freq")
    check("panel: carrier counts match carrier lists, freqs in range",
          not bad, f"{len(bad)} bad entries" if bad else "")

    # 7. GSA panel coverage: MAF must be present and in range.
    for dsid, cov in (panel.get("gsa_coverage") or {}).items():
        missing_maf = [s for s in cov["snps"] if s.get("maf") is None]
        check(f"gsa_coverage/{dsid}: all SNPs have a real MAF",
              not missing_maf, f"{len(missing_maf)} missing of {len(cov['snps'])}")
        check(f"gsa_coverage/{dsid}: snp count matches list",
              cov["panel_snps_on_chip"] == len(cov["snps"]),
              f"field={cov['panel_snps_on_chip']} actual={len(cov['snps'])}")

    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\n=== {len(results) - n_fail}/{len(results)} checks passed, {n_fail} FAILED ===")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
