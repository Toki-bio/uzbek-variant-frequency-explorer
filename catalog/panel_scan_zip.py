#!/usr/bin/env python3
"""Focal-panel scan for VCFs delivered inside per-sample zips (cardio_oct).

Plain, unindexed GRCh37 VCFs of ~1.5k records are streamed out of the zips
and filtered in Python against the hg19 panel BED. In-panel positions are
then lifted to GRCh38 with UCSC liftOver so records can be merged with the
native-hg38 datasets on the same coordinate; the original hg19 position is
kept on every record. Nothing is extracted to disk except a tiny temp BED
for liftOver.

Usage: panel_scan_zip.py <hg19_panel.bed> <zip_dir> <dataset_id> \
                         <hg19ToHg38.chain> > out.json
"""
import io, json, re, subprocess, sys, tempfile, zipfile
from pathlib import Path

LIFTOVER = "/staging/conda/envs/bioinfo/bin/liftOver"
SAMPLE_RE = re.compile(r"^sample_(.+?) \(\d+\)\.zip$", re.I)  # deliverable zips only


def load_bed(p):
    out = []
    for line in Path(p).read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            f = line.split("\t")
            out.append((f[0].replace("chr", ""), int(f[1]), int(f[2]), f[3] if len(f) > 3 else "?"))
    return out


def in_panel(chrom, pos, regions):
    for c, s, e, g in regions:
        if chrom == c and s <= pos <= e:
            return g
    return None


def lift(positions, chain):
    """{(chr19, pos19)} -> {(chr19,pos19): (chr38,pos38)}; unmapped omitted."""
    if not positions:
        return {}
    with tempfile.TemporaryDirectory() as td:
        src, dst, un = Path(td, "in.bed"), Path(td, "out.bed"), Path(td, "un.bed")
        src.write_text("".join(f"chr{c}\t{p-1}\t{p}\t{c}:{p}\n" for c, p in sorted(positions)))
        subprocess.run([LIFTOVER, str(src), chain, str(dst), str(un)],
                       check=True, capture_output=True)
        m = {}
        for line in dst.read_text().splitlines():
            c38, s, e, key = line.split("\t")[:4]
            c19, p19 = key.split(":")
            m[(c19, int(p19))] = (c38, int(e))
        return m


def main():
    bed, zdir, dsid, chain = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    regions = load_bed(bed)
    raw = {}  # sid -> [records in hg19]
    for z in sorted(zdir.glob("*.zip")):
        m = SAMPLE_RE.match(z.name)
        if not m:
            continue
        sid = m.group(1)
        with zipfile.ZipFile(z) as zf:
            vcf = next((n for n in zf.namelist() if n.lower().endswith(".vcf")), None)
            if not vcf:
                continue
            recs = []
            with zf.open(vcf) as fh:
                for line in io.TextIOWrapper(fh, encoding="utf-8", errors="ignore"):
                    if line.startswith("#"):
                        continue
                    f = line.rstrip("\n").split("\t")
                    if len(f) < 10:
                        continue
                    chrom, pos = f[0].replace("chr", ""), int(f[1])
                    gene = in_panel(chrom, pos, regions)
                    if not gene:
                        continue
                    gt = dict(zip(f[8].split(":"), f[9].split(":"))).get("GT", ".")
                    if all(a in ("0", ".") for a in gt.replace("|", "/").split("/")):
                        continue
                    recs.append((chrom, pos, f[3], f[4], f[5], f[6], gt, gene))
            raw[sid] = recs

    positions = {(r[0], r[1]) for recs in raw.values() for r in recs}
    lifted = lift(positions, chain)
    unmapped = len(positions) - len(lifted)

    samples = {}
    for sid, recs in raw.items():
        out = []
        for chrom, pos, ref, alt, qual, filt, gt, gene in recs:
            l = lifted.get((chrom, pos))
            if not l:
                continue  # unmapped by liftOver - excluded, counted below
            out.append({"chrom": l[0], "pos": l[1], "ref": ref, "alt": alt,
                        "qual": qual, "filter": filt, "genotype": gt, "gene": gene,
                        "source_build": "GRCh37", "source_pos": f"chr{chrom}:{pos}"})
        samples[sid] = out

    result = {"panel_bed": bed,
              "datasets": {dsid: {"vcf_count": len(raw), "samples": samples, "errors": [],
                                  "source_build": "GRCh37", "lifted_to": "GRCh38",
                                  "positions_in_panel": len(positions),
                                  "positions_unmapped_by_liftover": unmapped}}}
    print(json.dumps(result, indent=2))
    print(f"{dsid}: {len(raw)} VCFs, {len(positions)} in-panel positions, "
          f"{len(lifted)} lifted, {unmapped} unmapped", file=sys.stderr)


if __name__ == "__main__":
    main()
