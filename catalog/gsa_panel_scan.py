#!/usr/bin/env python3
"""Cross-dataset focal-panel scanner for GSA/array data: given a gene panel
BED (in the genome build matching the target .bim file) and a PLINK
fileset, find which panel SNPs are actually on the chip and their real
allele frequency - computed via plink --freq if no .frq/.afreq already
exists, never fabricated.

Usage: gsa_panel_scan.py <panel.bed> <bim_prefix> <dataset_label> [existing_frq]
Output: JSON to stdout.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

PLINK = "/usr/bin/plink"


def load_bed(bed_path):
    regions = []
    for line in open(bed_path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        chrom = f[0].replace("chr", "")
        regions.append((f[3], chrom, int(f[1]), int(f[2])))
    return regions


def gene_for(chrom, pos, regions):
    for gene, g_chrom, start, end in regions:
        if chrom == g_chrom and start <= pos <= end:
            return gene
    return None


def main():
    bed_path, bim_prefix, dataset_label = sys.argv[1:4]
    existing_frq = sys.argv[4] if len(sys.argv) > 4 else None
    regions = load_bed(bed_path)

    hits = []  # (snp_id, chrom, pos, gene)
    with open(f"{bim_prefix}.bim", encoding="utf-8") as f:
        for line in f:
            chrom, snp_id, _cm, pos, a1, a2 = line.rstrip("\n").split("\t")
            pos = int(pos)
            gene = gene_for(chrom, pos, regions)
            if gene:
                hits.append((snp_id, chrom, pos, gene, a1, a2))

    freqs = {}  # snp_id -> maf
    if existing_frq:
        with open(existing_frq, encoding="utf-8") as f:
            header = f.readline().split()
            snp_idx, maf_idx = header.index("SNP"), header.index("MAF")
            for line in f:
                parts = line.split()
                freqs[parts[snp_idx]] = float(parts[maf_idx])
    elif hits:
        with tempfile.TemporaryDirectory() as td:
            snplist = Path(td) / "snps.txt"
            snplist.write_text("\n".join(h[0] for h in hits))
            out_prefix = Path(td) / "panelfreq"
            subprocess.run(
                [PLINK, "--bfile", bim_prefix, "--extract", str(snplist),
                 "--freq", "--out", str(out_prefix)],
                capture_output=True, text=True, check=True,
            )
            frq_file = out_prefix.with_suffix(".frq")
            if frq_file.exists():
                with open(frq_file, encoding="utf-8") as f:
                    header = f.readline().split()
                    snp_idx, maf_idx = header.index("SNP"), header.index("MAF")
                    for line in f:
                        parts = line.split()
                        freqs[parts[snp_idx]] = float(parts[maf_idx])

    result = {
        "dataset": dataset_label,
        "bim_prefix": bim_prefix,
        "panel_snps_on_chip": len(hits),
        "snps": [
            {"snp_id": sid, "chrom": chrom, "pos": pos, "gene": gene,
             "a1": a1, "a2": a2, "maf": freqs.get(sid)}
            for sid, chrom, pos, gene, a1, a2 in sorted(hits, key=lambda h: (h[1], h[2]))
        ],
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
