# Genotyping Data Catalog

Generates a fact-based catalog of every genotyping dataset (GSA array, WES,
WGS, targeted panels) from what actually exists on disk, instead of a
hand-maintained HTML page that can silently drift from reality.

## Why this exists

The previous catalog (`data-sources.html` in the `uzbek-variant-frequency-explorer`
repo) was a hand-edited JS array. Two of its 8 entries turned out to be wrong
in ways nobody had caught: `cardio_main` cited a file
(`all_samples_pathogenic_variants.tsv`) that exists but is empty, while
ignoring the one file that actually has content
(`rare_potential_pathogenic.tsv`); and its claimed sample count (n=65) had no
basis anywhere in the underlying data (see "Investigation: cardio_main" below
for how the real number, 25, was found).

The fix is structural, not a one-off correction: sample counts, file
inventories, and completion status are now **derived from disk on every run**,
so they can't silently drift from what's hand-typed into a catalog page again.

## Architecture

```
registry.json  (hand-maintained)     scan_wes.py / scan_gsa.py  (live disk facts)
      \                                        /
       \                                      /
        v                                    v
              generate_catalog.py
                       |
                       v
                catalog.json  (generated, never hand-edited)
```

- **`registry.json`** — the only hand-maintained file. Holds what no scanner
  can infer: dataset id, display name, date, type (`gsa`/`wes`/`wgs`),
  root path(s), and a human description. Every field here is a claim, and
  `generate_catalog.py` checks each claim against reality.
- **`scan_wes.py`** — scans a WES/WGS output directory and reports, per
  sample, which output files exist and whether the sample is complete.
  Recognizes three naming conventions found in the wild (see below).
- **`scan_gsa.py`** — scans a GSA/array pipeline directory tree and reports
  the furthest completed stage, based on which PLINK filesets actually exist
  (handles both PLINK1.9 and PLINK2 output naming, plus QC evidence that
  lives in a separate `qc/` directory rather than same-basename siblings).
- **`generate_catalog.py`** — runs the right scanner against each registry
  entry, merges the results, and flags any disagreement between what the
  registry claims and what the scanner found (`discrepancies` field per
  dataset). Supports datasets whose real output spans multiple directories
  (`sub_paths`), summing sample counts across them.

Run it with:
```
python3 generate_catalog.py registry.json catalog.json
```

## Sequencing output naming conventions recognized by scan_wes.py

Three conventions were found across existing datasets - a single hardcoded
pattern would have kept missing real data, the way it did for `cardio_oct`
and `cardio_main` before this was generalized:

| Convention | Example | Seen in |
|---|---|---|
| `bcftools_sarek` | `sample01.bcftools.hard-filtered.vcf.gz` | `cardio_wes_v350432671` |
| `sample_zip` | `sample_DjorayevEldor.zip` | `cardio_oct` |
| `dragen_native` | `Cardio1.hard-filtered.vcf.gz`, `Cardio1.bam` | `cardio_main` |

Raw, unprocessed FASTQ is also detected as a fallback (`<name>_R1/R2.fastq.gz`
or `_1/_2.fq.gz`) so an unprocessed sequencing directory reports "N raw
samples, 0 processed" instead of a flat, misleading "0 samples".

## GSA/array completion signal

GSA pipelines are staged (GenomeStudio QC -> PLINK filtering steps ->
post-imputation), and there's no single "done" marker - completion is only
ever implicit in which files exist. `scan_gsa.py` looks for the most complete
PLINK fileset (`.bed/.bim/.fam` + QC extensions) anywhere under the given
root, preferring paths under a directory named like a late stage (e.g.
`3_post-imputation`) when multiple candidate filesets exist, and reports any
equally-complete alternative rather than silently picking one.

It recognizes QC evidence in two forms:
1. Same-basename sibling files (PLINK1.9: `.frq/.hwe/.het/.imiss/.lmiss`,
   or PLINK2: `.smiss/.vmiss`)
2. QC evidence in a separate directory that doesn't share the core
   fileset's basename (e.g. a dedicated `qc/` dir with `*_het.het`,
   `*_king.*`, `*_pca.eigenvec`) - `gwas2026_2` uses this pattern and was
   initially (incorrectly) flagged incomplete before this was added.

## Investigation: cardio_main's real sample count

The original catalog claimed n=65 for `cardio_main` ("Cardio - Cases /
Controls / Transplant"). No file anywhere under `/staging/cardio/sophia/`
supports that number. The actual, verified structure:

- **12 cases**: `/staging/cardio/sophia/fastq/results/` (Cardio1-Cardio12),
  also reprocessed against a pangenome reference in `results_pangenome_cases/`
- **12 controls**: `/staging/cardio/sophia/fastq/healthy/results/`, also in
  `healthy/results_pangenome_controls/`
- **1 transplant sample** (Cardio1017): `/staging/cardio/sophia/fastq/transplant/`
  (also present redundantly inside `results/`, since it went through the same
  demultiplexing run as the cases)
- **Total: 25 unique samples**, confirmed independently three ways:
  `annotations/cases.tsv` (12 lines) + `annotations/controls.tsv` (12 lines)
  + 1 transplant; and the real `aggregated_pathogenic_variants.json` itself
  reports `case_count: 12, control_count: 12` consistently across every
  variant it lists.
- `CardioUndetermined` (the demux leftover/unassigned-reads bucket) is
  correctly excluded - it has DRAGEN-native output files but is not a
  biological sample.

`registry.json`'s `cardio_main` entry has been corrected to n=25 with this
reasoning recorded inline (`n_claimed_note`), and `sub_paths` points scanning
at the two real per-cohort output directories (`results/`, `healthy/results/`)
rather than the single raw-FASTQ path the original catalog pointed to.

## Known open items

- `cardio_main`'s "cases" count (13, from `results/`) includes the transplant
  sample Cardio1017 alongside the 12 true cases, since it physically lives in
  the same directory. The total (25) is correct because the separate
  `transplant/` directory is deliberately excluded from counting to avoid
  double-counting Cardio1017 - but a fully accurate per-cohort breakdown
  would need to cross-reference `annotations/cases.tsv`'s authoritative
  sample list rather than trust directory contents alone.
- `results_pangenome_cases/`, `healthy/results_pangenome_controls/`, and
  `annotations_transplant/` are real, additional output directories not yet
  represented in the catalog at all (pangenome-reference reruns of the same
  25 samples, and the transplant sample's separate pathogenic-variant
  annotation).
- `pavel_wes_saidkarimova`'s date_confidence and `cardio_wes_v350432671`'s
  date both need a human to confirm the true run date - the extracted values
  looked more like "last edited" timestamps than true experiment dates.
