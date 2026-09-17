#!/usr/bin/env python3
"""Cross-dataset focal-panel scanner: given a gene panel BED (real genomic
coordinates, not gene names) and a list of per-dataset VCF glob patterns,
query each dataset's actual indexed VCFs for variants overlapping the panel
regions via `bcftools view -R`, and build one cross-dataset variant x sample
genotype table.

This reads real VCF records - it does not touch file-presence metadata.

Usage: panel_scan.py <panel.bed> <sources.json> <output.json>

sources.json shape:
{
  "cardio_wes_v350432671": {"glob": "/staging/WES_sarek/clinical_reports/*.bcftools.annotated.vcf.gz"},
  "cardio_main_cases": {"glob": "/staging/cardio/sophia/fastq/results/Cardio*.hard-filtered.vcf.gz"},
  ...
}
"""
import glob
import json
import subprocess
import sys

BCFTOOLS = "/staging/conda/envs/bioinfo/bin/bcftools"


def query_vcf(bed_path: str, vcf_path: str) -> list[dict]:
    """Return one record per ALT allele found in the panel regions, with the
    genotype of the single sample this VCF file represents."""
    try:
        out = subprocess.run(
            [BCFTOOLS, "view", "-R", bed_path, "-H", vcf_path],
            capture_output=True, text=True, timeout=120, check=True,
        )
    except subprocess.CalledProcessError as e:
        return [{"error": f"bcftools failed on {vcf_path}: {e.stderr.strip()[:300]}"}]
    except subprocess.TimeoutExpired:
        return [{"error": f"bcftools timed out on {vcf_path}"}]

    records = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) < 10:
            continue
        chrom, pos, _id, ref, alt, qual, filt, info, fmt, sample_gt = fields[:10]
        gt_fields = dict(zip(fmt.split(":"), sample_gt.split(":")))
        gt = gt_fields.get("GT", ".")
        # Skip hom-ref / no-call - only report actual variant genotypes.
        alleles = gt.replace("|", "/").split("/")
        if all(a in ("0", ".") for a in alleles):
            continue
        records.append({
            "chrom": chrom, "pos": int(pos), "ref": ref, "alt": alt,
            "qual": qual, "filter": filt, "genotype": gt,
        })
    return records


def sample_id_from_path(vcf_path: str) -> str:
    import os
    base = os.path.basename(vcf_path)
    for sep in (".bcftools", ".hard-filtered"):
        if sep in base:
            return base.split(sep)[0]
    return base


def main():
    if len(sys.argv) != 4:
        print(f"usage: {sys.argv[0]} <panel.bed> <sources.json> <output.json>", file=sys.stderr)
        sys.exit(1)

    bed_path, sources_path, output_path = sys.argv[1:4]
    sources = json.loads(open(sources_path, encoding="utf-8").read())

    result = {"panel_bed": bed_path, "datasets": {}}
    for dataset_id, cfg in sources.items():
        vcf_paths = sorted(glob.glob(cfg["glob"]))
        dataset_result = {"vcf_count": len(vcf_paths), "samples": {}, "errors": []}
        for vcf_path in vcf_paths:
            sample_id = sample_id_from_path(vcf_path)
            records = query_vcf(bed_path, vcf_path)
            errors = [r for r in records if "error" in r]
            variants = [r for r in records if "error" not in r]
            if errors:
                dataset_result["errors"].extend(errors)
            dataset_result["samples"][sample_id] = variants
        result["datasets"][dataset_id] = dataset_result
        print(f"{dataset_id}: {len(vcf_paths)} VCFs scanned", flush=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
