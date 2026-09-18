#!/usr/bin/env python3
"""Aggregate panel_scan.py's per-sample raw genotype dump into one
variant x dataset frequency table - the actual point of a focal panel:
"how common is this variant in each of our cohorts?"

Usage: panel_aggregate.py panel.bed results1.json [results2.json ...] > panel_summary.json
"""
import json
import sys


def load_gene_regions(bed_path):
    regions = []
    for line in open(bed_path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        regions.append((f[3], f[0], int(f[1]), int(f[2])))
    return regions


def gene_for(chrom, pos, regions):
    for gene, g_chrom, start, end in regions:
        if chrom == g_chrom and start <= pos <= end:
            return gene
    return "?"


def main():
    gene_regions = load_gene_regions(sys.argv[1])
    # Merge any number of scan outputs (native-hg38 bcftools scans plus lifted
    # zip scans). Dataset ids must be unique across files.
    data = {"datasets": {}}
    for p in sys.argv[2:]:
        d = json.loads(open(p, encoding="utf-8").read())
        for k, v in d["datasets"].items():
            if k in data["datasets"]:
                sys.exit(f"duplicate dataset id across inputs: {k}")
            data["datasets"][k] = v
    gene_tags = {}  # key -> gene supplied by the scanner itself, if any
    variants = {}  # (chrom,pos,ref,alt) -> {dataset: {carriers: [], alt_allele_count: int, samples_genotyped: int}}

    builds = {}
    for dataset_id, ds in data["datasets"].items():
        if ds.get("source_build"):
            builds[dataset_id] = {"source_build": ds["source_build"], "lifted_to": ds.get("lifted_to"),
                                  "positions_unmapped_by_liftover": ds.get("positions_unmapped_by_liftover")}
        n_samples = len(ds["samples"])
        for sample_id, records in ds["samples"].items():
            seen_keys = set()
            for r in records:
                key = (r["chrom"], r["pos"], r["ref"], r["alt"])
                if r.get("gene"):
                    gene_tags[key] = r["gene"]
                seen_keys.add(key)
                v = variants.setdefault(key, {})
                d = v.setdefault(dataset_id, {"carriers": [], "n_samples_in_dataset": n_samples})
                alleles = r["genotype"].replace("|", "/").split("/")
                alt_count = sum(1 for a in alleles if a not in ("0", "."))
                d["carriers"].append({"sample": sample_id, "genotype": r["genotype"], "alt_alleles": alt_count})

    summary = []
    for (chrom, pos, ref, alt), by_dataset in sorted(variants.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        entry = {
            "chrom": chrom, "pos": pos, "ref": ref, "alt": alt,
            "gene": gene_tags.get((chrom, pos, ref, alt)) or gene_for(chrom, pos, gene_regions),
            "datasets": {},
        }
        for dataset_id, d in by_dataset.items():
            n_carriers = len(d["carriers"])
            n_total = d["n_samples_in_dataset"]
            alt_alleles = sum(c["alt_alleles"] for c in d["carriers"])
            entry["datasets"][dataset_id] = {
                "carrier_count": n_carriers,
                "cohort_size": n_total,
                "carrier_frequency": round(n_carriers / n_total, 4) if n_total else None,
                "alt_allele_count": alt_alleles,
                "carriers": d["carriers"],
            }
        summary.append(entry)

    print(json.dumps({"panel": f"cardiomyopathy ({len(gene_regions)}/26 genes, GRCh38 coords from NCBI RefSeq GCF_000001405.40 GRCh38.p14, verified)",
                       "dataset_builds": builds,
                       "variant_count": len(summary), "variants": summary}, indent=2))


if __name__ == "__main__":
    main()
