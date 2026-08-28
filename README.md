# Uzbek Variant Frequency Explorer

Interactive clinical genomics tool for comparing allele frequencies of disease-associated variants in the **Uzbek (ALSU) population** against gnomAD v4 NFE (European) and SAS (South Asian) reference frequencies.

**Live tool:** https://toki-bio.github.io/uzbek-variant-frequency-explorer/

---

## Features

- **179 panel variants** embedded — carrier screening, oncology, and pharmacogenomics (PGx)
- **7 input modes:** RS IDs, file upload, gene name, genomic coordinates/BED, drug (CPIC), disease/phenotype, HGVS notation
- **Multi-source data:** gnomAD v4, ClinVar, 1000 Genomes, live DRAGEN UZB lookup
- **Sortable table** by gene, pathogenicity, UZB frequency, delta vs NFE, R2
- **Drag-and-drop** row reorder, checkbox selection, row removal
- **Indel proxy warnings** — flags cases where imputed SNP frequency proxies a panel indel
- **CPIC pharmacogenomics** data with drug and star allele annotations
- **Self-contained** — works offline for embedded panel data; APIs require internet

## Data

| File | Description |
|------|-------------|
| `data/panel_data.json` | 179-variant panel with gnomAD, ClinVar, CPIC data |
| `data/uzb_freq_matched.tsv` | 52 variants with UZB imputation frequency + R2 |

### Uzbek cohort (ALSU)
- N = 1,256 unrelated individuals (spring2026 expanded imputed cohort (N=1256))
- Genotyped on Illumina GSA v3 array (hg38)
- Imputed to ~10M variants via Michigan Imputation Server (Minimac4)
- UZB allele frequencies are **imputed** (not directly sequenced) for most variants
- R2 (imputation quality) and confidence flags provided per variant

### Population frequency sources
- **gnomAD v4** NFE and SAS frequencies (from panel annotation and live gnomAD API)
- **1000 Genomes Phase 3** via Ensembl REST (AFR/AMR/EAS/EUR/SAS)

### Important caveats
- Variants flagged **INDEL_PROXY**: imputed SNP frequency reflects a nearby tagging SNP, not the actual indel — do not use for clinical interpretation without direct sequencing
- Low R2 (< 0.4): imputation unreliable, especially for rare pathogenic alleles in a Central Asian cohort with no native reference panel

## Live DRAGEN Connection

The tool can query a live server for UZB frequencies across all 48.9M imputed variants (not just the 179 panel variants). Requires:
1. `uzb_freq_server.py` running on DRAGEN (port 8765)
2. SSH tunnel: `plink -L 8765:localhost:8765 copilot@100.104.25.22`
3. Or Tailscale direct access — set URL in the Setup Guide section of the tool

See the collapsible **Connection & Setup Guide** inside the tool for full instructions.

## Citation / Contact

ALSU study — Uzbek population genetics cohort.
For questions about the data or tool, open an issue in this repository.

## License

Tool and code: MIT. Panel variant data sourced from public databases (ClinVar, gnomAD, CPIC) under their respective terms.