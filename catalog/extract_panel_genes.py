#!/usr/bin/env python3
"""Extract gene-level coordinates for the 26-gene cardiomyopathy panel from
the official NCBI RefSeq GRCh38.p14 GTF (same build already cited as the
source for the 2 pre-verified genes), add the same +/-1kb flank convention,
and cross-check the 2 already-verified genes match exactly before trusting
this for the other 24.

Usage: extract_panel_genes.py genes.txt genomic.gtf.gz existing.bed > new_panel.bed
"""
import gzip
import sys

NC_TO_CHR = {
    "NC_000001.11": "chr1", "NC_000002.12": "chr2", "NC_000003.12": "chr3",
    "NC_000004.12": "chr4", "NC_000005.10": "chr5", "NC_000006.12": "chr6",
    "NC_000007.14": "chr7", "NC_000008.11": "chr8", "NC_000009.12": "chr9",
    "NC_000010.11": "chr10", "NC_000011.10": "chr11", "NC_000012.12": "chr12",
    "NC_000013.11": "chr13", "NC_000014.9": "chr14", "NC_000015.10": "chr15",
    "NC_000016.10": "chr16", "NC_000017.11": "chr17", "NC_000018.10": "chr18",
    "NC_000019.10": "chr19", "NC_000020.11": "chr20", "NC_000021.9": "chr21",
    "NC_000022.11": "chr22", "NC_000023.11": "chrX", "NC_000024.10": "chrY",
}
FLANK = 1000


def parse_attr(field, key):
    marker = f'{key} "'
    i = field.find(marker)
    if i == -1:
        return None
    i += len(marker)
    j = field.find('"', i)
    return field[i:j]


def main():
    genes_path, gtf_path, existing_bed_path = sys.argv[1:4]
    wanted = set(l.strip() for l in open(genes_path, encoding="utf-8") if l.strip())

    found = {}  # gene -> (chrom, start, end) [0-based BED, flank already added]
    with gzip.open(gtf_path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9 or fields[2] != "gene":
                continue
            gene = parse_attr(fields[8], "gene")
            if gene not in wanted:
                continue
            chrom = NC_TO_CHR.get(fields[0])
            if not chrom:
                continue
            start, end = int(fields[3]), int(fields[4])
            # Matches the existing verified BED's convention exactly (confirmed by
            # cross-check below): flank applied directly to the 1-based GTF
            # coordinates, not a separate 0-based half-open conversion.
            bed_start = max(0, start - FLANK)
            bed_end = end + FLANK
            if gene in found:
                sys.stderr.write(f"WARNING: duplicate gene entry for {gene}, keeping first\n")
                continue
            found[gene] = (chrom, bed_start, bed_end)

    # Cross-check against the 2 already-verified entries.
    existing = {}
    for line in open(existing_bed_path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        existing[f[3]] = (f[0], int(f[1]), int(f[2]))

    mismatches = []
    for gene, coords in existing.items():
        if gene not in found:
            mismatches.append(f"{gene}: not found in GTF extraction at all")
        elif found[gene] != coords:
            mismatches.append(f"{gene}: GTF gives {found[gene]}, existing verified BED has {coords}")

    if mismatches:
        sys.stderr.write("VALIDATION FAILED - GTF extraction does not match already-verified coordinates:\n")
        for m in mismatches:
            sys.stderr.write("  " + m + "\n")
        sys.stderr.write("Refusing to emit a panel BED built on an unvalidated extraction method.\n")
        sys.exit(1)

    sys.stderr.write(f"Validation OK: {len(existing)} pre-verified gene(s) match exactly.\n")
    missing = wanted - found.keys()
    if missing:
        sys.stderr.write(f"NOT FOUND in GTF (skipped, not written): {sorted(missing)}\n")

    print("#chrom\tstart\tend\tgene\tsource")
    for gene in sorted(found, key=lambda g: (found[g][0], found[g][1])):
        chrom, start, end = found[gene]
        print(f"{chrom}\t{start}\t{end}\t{gene}\tNCBI RefSeq GCF_000001405.40 GRCh38.p14, +/-1kb flank")


if __name__ == "__main__":
    main()
