# Static UZB frequency tables (built 2026-11-20)

Used by `lookup.html`. No server needed: the page fetches one 1 Mb piece per lookup.

- Cohort: ALSU analysis cohort, **N = 1,256** (`keep_UZB.txt` of the 1,256 PBS/ADMIXTURE runs).
- Reference: NYGC 1000 Genomes 30x (3,202 samples), GRCh38.
- Layout: `typed/chrN/<floor(pos/1e6)>.tsv.gz` and `imputed/chrN/<floor(pos/1e6)>.tsv.gz`, tab-separated, no header, sorted by position.

## typed/ — every SNP genotyped on the GSA array after QC (452,377)

Source `FULL_QC_FINAL` (1,268 samples, 452,377 SNPs), restricted to the 1,256. Alleles as in the array file (Illumina TOP strand).

| col | content |
|---|---|
| 1 | position (GRCh38) |
| 2 | rsID from the original array file `ConvSK` (`.` if none) |
| 3, 4 | a1, a2 (array bases, TOP strand) |
| 5, 6, 7 | genotype counts a1a1, a1a2, a2a2 |
| 8 | missing genotypes |
| 9 | Hardy-Weinberg p (plink `--hardy`) |
| 10 | flag: `ok` (bases match 1000G), `flipped` (complement matches; normal, TOP strand), `pal_mixed_strand` (A/T or C/G; columns 5-9 and 11-36 empty, see below), `nygc_multi`, `nygc_absent`, `allele_mismatch` |
| 11–36 | frequency of **a1** (complemented to + strand when flipped) ×10,000 in ACB ASW ESN GWD LWK MSL YRI CLM MXL PEL PUR CDX CHB CHS JPT KHV CEU FIN GBR IBS TSI BEB GIH ITU PJL STU (empty when no 1000G match) |

## imputed/ — every variant imputed with R² ≥ 0.80 and MAF ≥ 0.001 (9,808,764)

Source `imputation_results/hq_filtered/chr*.HQ.vcf.gz` (Michigan run 3: 1000G phase 3 30x GRCh38, Eagle 2.4, Minimac 4.1.6), restricted to the 1,256. No further MAF cut. Alleles = VCF REF/ALT on the GRCh38 + strand.

| col | content |
|---|---|
| 1 | position |
| 2, 3 | REF, ALT |
| 4 | 1 = also genotyped on the array (Michigan TYPED flag) |
| 5 | R² (Michigan, 1,268 samples) |
| 6, 7, 8 | best-guess genotype counts REF/REF, REF/ALT, ALT/ALT |
| 9 | missing |
| 10–14 | ALT frequency ×10,000 in AFR AMR EAS EUR SAS (NYGC INFO AF, exact match on position + REF + ALT; empty = not in 1000G) |

## Checks done before publishing

- Complemented vs direct typed SNPs: Uzbek-vs-EUR frequency correlation 0.907 vs 0.906 (reversed orientation −0.907).
- A/T and C/G typed SNPs (1,712): **counts and frequencies withheld** (version 2, 2026-11-20). The batch merge (`FULL_MERGED`, carried into `FULL_QC_FINAL`) could not detect strand differences at palindromic SNPs; ALSU-vs-DRAGEN batch allele frequencies at 8,841 palindromic SNPs correlate r = 0.009 and 4,265 look reversed (non-palindromic: r = 0.988, 6 reversed of 585,757). These SNPs were removed before imputation, so the imputed table is not affected. Version 1 of the typed pieces (commit 4835116) showed mixed-strand numbers for them.
- Imputed chr22 test: hard-call AF vs Michigan dosage AF r = 0.99996; UZB vs EUR r = 0.968; 99.0% exact 1000G match; imputed vs typed frequency at 6,442 array SNPs r = 0.9998.
- Row counts after splitting: 452,377 / 452,377 typed, 9,808,764 / 9,808,764 imputed. rs2476601 reads back identically.

## Where the full tables and scripts are

DRAGEN `/staging/ALSU-analysis/spring2026/full_expanded_cohort/uzb_static_table_2026-11-20/`:
`uzb_typed_1256_nygc.v2.tsv` (published typed table, palindromic rows blanked), `uzb_typed_1256_nygc.tsv` (version 1, kept for the record), `uzb_imputed_1256_nygc.tsv`, `keep1256.txt`, `scripts/` (`uzbtab.sh`, `imptab.sh`, `uzbcheck.sh`, `run3.sh`, `pack.sh`, `fixpal.sh`), `run3.log`, `MD5SUMS`, `static.tar` (v1), `static_typed_v2.tar`.

Pipeline schematic and the allele-coding traps (TOP strand, palindromic SNPs, REF/ALT vs A1/A2): https://claude.ai/artifact/HwSvvnJvdJxz4Dnb9FwF4s
