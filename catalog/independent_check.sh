#!/bin/bash
# Independent spot-check of the catalog's headline numbers.
# Uses ONLY standard tools (wc, ls, grep, bcftools, plink) - no code from
# this project is involved, so agreement is not self-confirming.
# Run it yourself:  bash independent_check.sh

echo "=== 1. GSA sample counts: count lines in the .fam PLINK itself wrote ==="
for f in \
  "/staging/ALSU-analysis/winter2025/3_post-imputation/ConvSK_final_clean.fam|alsu (page says 1074)" \
  "/staging/ALSU-analysis/spring2026/full_expanded_cohort/imputation_results/hq_filtered/UZB_imputed_HQ_clean.fam|alsu_expanded (page says 1268)" \
  "/staging/GWAS2026-2/plink/gwas2026_2_varqc.fam|gwas2026_2 (page says 87)" \
  "/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas2026/plink/gwas2026_varqc.fam|gwas96 (page says 83)" \
  "/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas48redone/plink/gwas48redone_raw.fam|rescan48 (page says 48)" ; do
  p="${f%%|*}"; label="${f##*|}"
  printf "  %-46s %s\n" "$label" "$(wc -l < "$p")"
done

echo
echo "=== 2. Cross-check: PLINK's own log, not the .fam ==="
# These logs are PLINK2 format ('N samples ... remaining after main filters'),
# not PLINK1.9 format ('N people pass filters and QC'). Matching only the
# latter made this check silently print nothing, which is worse than no check
# at all - so both phrasings are matched, and absence is reported explicitly.
for pair in \
  "/staging/GWAS2026-2/plink/gwas2026_2_varqc.log|gwas2026_2" \
  "/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas2026/plink/gwas2026_varqc.log|gwas96" ; do
  log="${pair%%|*}"; name="${pair##*|}"
  # PLINK phrasings differ by version and by which stage wrote the log:
  #   plink1.9 : "N variants and M people pass filters and QC."
  #   plink2   : "M samples (...) loaded from ..." / "... remaining after main filters"
  # Match any of them; a check that silently matches nothing is worthless.
  line=$(grep -hE "people pass filters and QC|samples \(.*\) (remaining after main filters|loaded from)" \
         "$log" 2>/dev/null | tail -1)
  if [ -n "$line" ]; then printf "  %-12s %s\n" "$name:" "$line"
  else printf "  %-12s NO MATCHING LINE FOUND in %s\n" "$name:" "$log"; fi
done

echo
echo "=== 3. Sequencing sample counts: count actual VCF files ==="
printf "  cardio_wes (page says 16)      %s\n" \
  "$(ls /staging/WES_sarek/clinical_reports/*.bcftools.hard-filtered.vcf.gz 2>/dev/null | wc -l)"
printf "  cardio_main cases (12+transpl) %s\n" \
  "$(ls /staging/cardio/sophia/fastq/results/Cardio*.hard-filtered.vcf.gz 2>/dev/null | grep -vc Undetermined)"
printf "  cardio_main controls (12)      %s\n" \
  "$(ls /staging/cardio/sophia/fastq/healthy/results/Cardio*.hard-filtered.vcf.gz 2>/dev/null | wc -l)"
printf "  cardio_oct (page says 12)      %s\n" \
  "$(ls /staging/cardio/sophia/october2025-12samples/sample_*.zip 2>/dev/null | sed 's/ (1)//' | sort -u | wc -l)"

echo
echo "=== 4. cardio_main: DISTINCT SAMPLE IDs in the annotation tables ==="
# These are variant tables (one row per variant per sample), NOT sample lists.
# Counting lines here gives 196/206 and means nothing about sample count -
# an earlier note in this project made exactly that mistake. Column 1 is the
# sample ID, so the meaningful number is the count of distinct values.
for pair in "cases|/staging/cardio/sophia/fastq/annotations/cases.tsv" \
            "controls|/staging/cardio/sophia/fastq/annotations/controls.tsv" ; do
  name="${pair%%|*}"; f="${pair##*|}"
  printf "  %-9s %s lines total, %s distinct sample IDs in col 1\n" \
    "$name:" "$(wc -l < "$f")" "$(cut -f1 "$f" | grep . | sort -u | wc -l)"
  printf "            %s\n" "$(cut -f1 "$f" | grep . | sort -u | tr '\n' ' ')"
done

echo
echo "=== 5. A panel variant, straight from the VCF (no project code) ==="
echo "  MYBPC3 region, sample01 - page claims variants exist here:"
BCF=/staging/conda/envs/bioinfo/bin/bcftools
$BCF view -H -r chr11:47330406-47353702 \
  /staging/WES_sarek/clinical_reports/sample01.bcftools.annotated.vcf.gz 2>/dev/null \
  | awk '{print "   ", $1, $2, $4">"$5, $10}' | head -5
echo "  total records in that gene for sample01:"
printf "    %s\n" "$($BCF view -H -r chr11:47330406-47353702 /staging/WES_sarek/clinical_reports/sample01.bcftools.annotated.vcf.gz 2>/dev/null | wc -l)"

echo
echo "=== 6. Panel BED coordinates came from NCBI RefSeq - verify MYBPC3 ==="
echo "  what the panel file says:"
grep -P "\tMYBPC3\t" /staging/data_catalog/cardiomyopathy_genes_grch38.bed | sed 's/^/    /'
echo "  what the NCBI GTF says (gene line, +/-1kb applied by the extractor):"
zcat /staging/users/user2/GCF_000001405.40_GRCh38.p14_genomic.gtf.gz 2>/dev/null \
  | awk -F'\t' '$3=="gene" && $9 ~ /gene "MYBPC3"/ {print "    NC_000011.10 raw:", $4, $5, "-> +/-1kb:", $4-1000, $5+1000}' | head -1

echo
echo "=== done - compare these against the page ==="
