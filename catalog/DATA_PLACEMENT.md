# Data placement rules for human sequencing on DRAGEN

Agreed with the owner step by step, starting 2026-11-13. This file is the rule book; the data_sources page
must match what these rules put on disk.

## Root

All human sequencing (WES now, WGS later) lives under `/staging/human/`.

```
/staging/human/
  raw/<assay>/<YYYY-MM-DD>_<flowcell>/     source data of one sequencing batch, never changed after arrival
      fastq/                               only the real sample reads, flat, original file names
      qc/L01/ … qc/L0N/                    sequencer QC per lane (files have the same names in every lane)
  analysis/<YYYY-MM-DD>_<pipeline>-<version>_<ref>_<flowcell>[+<flowcell>…]/
                                           one folder per pipeline run: samplesheet, run script, logs, results
```

## Rules

1. **Assay folder**: `wes`, `wgs`, `panel`.
2. **Batch folder name** = sequencing date from the sequencer's `BioInfo.csv` (`Sequence Date`) + flowcell ID,
   e.g. `2026-10-28_V350431082`. The flowcell ID is in every vendor file name, so it identifies the batch uniquely.
3. **`fastq/` is flat.** No lane subfolders: MGI names already carry flowcell, lane, barcode and read
   (`V350431082_L01_17_1.fq.gz` = flowcell V350431082, lane 1, barcode 17, read 1), so names cannot collide.
   File names are never changed.
4. **Only real samples go to `fastq/`.** The sequencer writes a file for every barcode in its list (1–128 and more)
   plus `undecoded` reads; barcodes with no sample loaded hold a few thousand misread reads and are not data.
5. **`qc/` keeps lane subfolders**, because the lane-level files (`BioInfo.csv`, `summaryTable.csv`,
   `BarcodeStat.txt`, …) have identical names in every lane.
6. **Results never go into `raw/`.** Each pipeline run gets its own dated folder in `analysis/`; a re-run gets a new
   folder and never overwrites. A run that covers several batches lists all their flowcells in its name.
7. **No patient names in any path.** Samples are identified by barcode / lab code only.
8. **Moves within `/staging` use `mv`** (same filesystem, instant rename); every move is checked by file count and
   byte sizes before and after, and a `MOVED_FROM.txt` is left in the batch folder.

## Batch log

### 2026-10-28_V350431082 (WES batch 2)

- Source: `/staging/sarek_runs/V350431082/L01..L04/`
- Real samples: barcodes 17–32 (16 samples), 4 lanes, R1/R2 = **128 fastq.gz, 209.2 GB**
  (list: `batches/2026-10-28_V350431082_fastq.tsv`, taken from the server 2026-11-13).
- Destination of the reads: `/staging/human/raw/wes/2026-10-28_V350431082/fastq/`
- Analysed in the joint run `/staging/sarek_runs/WES16_cardio/` (with batch V350432671), finished 2026-11-05.
  Its `samplesheet32.csv` points to the old paths.
- Status: step 1 (fastq move) — command given to the owner 2026-11-13, not yet run.
  Still open: QC files, leftover barcodes, undecoded reads, results folder.
