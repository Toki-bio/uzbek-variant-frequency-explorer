# Data placement rules for human sequencing on DRAGEN

Agreed with the owner step by step, starting 2026-11-13. This file is the rule book; the data_sources page
must match what these rules put on disk. The layout below is the one the owner built on DRAGEN for
WES batch 2 lane L01 (checked on the server 2026-11-13).

## Layout

All human sequencing (WES now, WGS later) lives under `/staging/human/`.

```
/staging/human/
  raw/<assay>/<YYYY-MM-DD>_<flowcell>/        source data of one sequencing batch, never changed after arrival
      fastq/                                  real sample reads, flat, original file names
          <flowcell>_<lane>_FileInfo.txt      vendor MD5 of every fastq of that lane
          BioInfo.csv, summaryTable.csv, BarcodeStat.txt, SequenceStat.txt, BasecallQC.txt, version.json
                                              lane-level run files (same names in every lane - see open question)
          qc/<lane>/                          all other sequencer QC of that lane:
                                                per-barcode *.fq.fqStat.txt and *.report.html (samples and noise),
                                                *.allfq.fqStat.txt, undecoded *.fqStat.txt,
                                                lane reports *.summaryReport/heatmapReport/bestFovReport/allCycleHeatmap.html
          unusable/                           fastq of barcodes with no sample + undecoded reads
  analysis/<YYYY-MM-DD>_<pipeline>-<version>_<ref>_<flowcell>[+<flowcell>…]/
                                              one folder per pipeline run: samplesheet, run script, logs, results
```

## Rules

1. **Assay folder**: `wes`, `wgs`, `panel`.
2. **Batch folder name** = sequencing date from the sequencer's `BioInfo.csv` (`Sequence Date`) + flowcell ID,
   e.g. `2026-10-28_V350431082`. The flowcell ID is in every vendor file name, so it identifies the batch uniquely.
3. **Real sample fastq lie flat in `fastq/`.** No lane subfolders: MGI names already carry flowcell, lane, barcode and
   read (`V350431082_L01_17_1.fq.gz` = flowcell V350431082, lane 1, barcode 17, read 1), so names cannot collide.
   Fastq names are never changed.
4. **Noise goes to `fastq/unusable/`.** The sequencer writes a file for every barcode in its list (1–128 and more)
   plus `undecoded` reads. Barcodes with no sample loaded hold at most tens of thousands of misread reads (a real
   sample: 22–50 M per lane) and are not data; `undecoded` = reads whose barcode matched no sample (~1 % of a lane).
5. **`<flowcell>_<lane>_FileInfo.txt` is the MD5 record** of the lane's fastq. Keep it next to the fastq.
6. **Per-file and lane reports go to `fastq/qc/<lane>/`.**
7. **Results never go into `raw/`.** Each pipeline run gets its own dated folder in `analysis/`; a re-run gets a new
   folder and never overwrites. A run that covers several batches lists all their flowcells in its name.
8. **No patient names in any path.** Samples are identified by barcode / lab code only.
9. **Moves within `/staging` use `mv -n`** (same filesystem, instant rename, never overwrites); every move is checked
   by file count and byte sizes against the list taken before the move.

## Open question

The six lane-level files `BioInfo.csv`, `summaryTable.csv`, `BarcodeStat.txt`, `SequenceStat.txt`, `BasecallQC.txt`,
`version.json` have the same name in every lane. L01's copies now sit in `fastq/`; L02's would overwrite them
(or be refused by `mv -n`). To decide before L02: move them into `fastq/qc/<lane>/`, or prefix them with
`<flowcell>_<lane>_` (e.g. `V350431082_L01_BioInfo.csv`).

## Batch log

### 2026-10-28_V350431082 (WES batch 2)

- Source: `/staging/sarek_runs/V350431082/L01..L04/` (702 files per lane).
- Real samples: barcodes 17–32 (16 samples), 4 lanes, R1/R2 = **128 fastq.gz, 209.2 GB**
  (list with sizes: `batches/2026-10-28_V350431082_fastq.tsv`, taken from the server 2026-11-13).
- Analysed in the joint run `/staging/sarek_runs/WES16_cardio/` (with batch V350432671), finished 2026-11-05.
  Its `samplesheet32.csv` points to the old paths.
- State on DRAGEN, checked 2026-11-13:
  - L01 done: `fastq/` 32 sample fastq (sizes identical to the pre-move list) + `V350431082_L01_FileInfo.txt`
    + the six lane-level files; `fastq/qc/L01/` 419 files; `fastq/unusable/` 244 files (121 noise barcodes × R1/R2
    + 2 undecoded). Old `L01/` folder is empty.
  - L02, L03, L04: still in `/staging/sarek_runs/V350431082/`, 702 files each.
  - Not yet done: MD5 check against `FileInfo.txt`; results folder.
