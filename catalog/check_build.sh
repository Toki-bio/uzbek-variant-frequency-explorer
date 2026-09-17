#!/bin/bash
# Which genome build is each array fileset actually in?
# Method: count SNPs falling inside each gene's hg38 window vs its hg19
# window. For genes where the two windows barely overlap, only the correct
# build yields a plausible SNP count. No assumption about what the docs say.
set -uo pipefail

declare -A HG38 HG19
# gene   hg38 chrom:start-end             hg19 chrom:start-end (from liftOver output)
HG38[TRDN]="6:123215339:123637950";  HG19[TRDN]="6:123536484:123959095"
HG38[MYBPC3]="11:47330406:47353702"; HG19[MYBPC3]="11:47351957:47375253"
HG38[SCN5A]="3:38547062:38650687";   HG19[SCN5A]="3:38588553:38692178"
HG38[DSP]="6:7540671:7587714";       HG19[DSP]="6:7540904:7587947"
HG38[RYR2]="1:237041184:237834988";  HG19[RYR2]="1:237204484:237998288"

count_in () { # bim, chrom, start, end
  awk -F'\t' -v c="$2" -v s="$3" -v e="$4" \
    '$1==c && $4>=s && $4<=e {n++} END{print n+0}' "$1"
}

for pair in \
  "alsu|/staging/ALSU-analysis/winter2025/3_post-imputation/ConvSK_final_clean.bim" \
  "alsu_expanded|/staging/ALSU-analysis/spring2026/full_expanded_cohort/imputation_results/hq_filtered/UZB_imputed_HQ_clean.bim" \
  "gwas2026_2|/staging/GWAS2026-2/plink/gwas2026_2_varqc.bim" \
  "gwas96|/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas2026/plink/gwas2026_varqc.bim" \
  "rescan48|/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas48redone/plink/gwas48redone_raw.bim" ; do
  name="${pair%%|*}"; bim="${pair##*|}"
  [ -f "$bim" ] || { echo "$name: bim not found"; continue; }
  echo "=== $name ($(wc -l < "$bim") variants) ==="
  h38tot=0; h19tot=0
  for g in TRDN MYBPC3 SCN5A DSP RYR2; do
    IFS=: read -r c38 s38 e38 <<< "${HG38[$g]}"
    IFS=: read -r c19 s19 e19 <<< "${HG19[$g]}"
    n38=$(count_in "$bim" "$c38" "$s38" "$e38")
    n19=$(count_in "$bim" "$c19" "$s19" "$e19")
    h38tot=$((h38tot+n38)); h19tot=$((h19tot+n19))
    printf "  %-8s hg38 window: %-6s   hg19 window: %-6s\n" "$g" "$n38" "$n19"
  done
  if [ "$h38tot" -gt "$h19tot" ]; then verdict="hg38 (GRCh38)"; else verdict="hg19 (GRCh37)"; fi
  printf "  TOTAL    hg38: %-6s hg19: %-6s  -> looks like %s\n\n" "$h38tot" "$h19tot" "$verdict"
done
