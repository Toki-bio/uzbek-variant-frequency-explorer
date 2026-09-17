#!/bin/bash
# Independently recount panel carrier counts using bcftools directly,
# and compare to what panel_summary.json claims. No project code involved
# in the recount - only bcftools and shell.
#
# Picks the N variants with the highest claimed carrier counts (the ones
# most likely to be cited, and where an error would matter most), plus a
# few singletons, and recounts each from the raw VCFs.

set -uo pipefail
BCF=/staging/conda/envs/bioinfo/bin/bcftools
SUM=/staging/data_catalog/panel_summary.json
WES_DIR=/staging/WES_sarek/clinical_reports
N=${1:-8}

# Pull the variants to test, and what the summary claims for the WES cohort.
python3 - "$SUM" "$N" <<'PY' > /tmp/panel_targets.txt
import json, sys
d = json.load(open(sys.argv[1])); n = int(sys.argv[2])
rows = []
for v in d["variants"]:
    w = v["datasets"].get("cardio_wes_v350432671")
    if w:
        rows.append((w["carrier_count"], v["chrom"], v["pos"], v["ref"], v["alt"],
                     w["cohort_size"], v["gene"]))
rows.sort(reverse=True)
picked = rows[:n] + [r for r in rows if r[0] == 1][:3]
for c, ch, p, rf, al, cs, g in picked:
    print(f"{ch}\t{p}\t{rf}\t{al}\t{c}\t{cs}\t{g}")
PY

printf "%-22s %-10s %-9s %-9s %s\n" "VARIANT" "GENE" "CLAIMED" "RECOUNT" "VERDICT"
fail=0; total=0
while IFS=$'\t' read -r chrom pos ref alt claimed cohort gene; do
  [ -z "${chrom:-}" ] && continue
  total=$((total+1))
  # Recount: how many of the 16 WES samples carry a non-ref genotype here?
  actual=0
  for vcf in "$WES_DIR"/*.bcftools.annotated.vcf.gz; do
    gt=$($BCF view -H -r "${chrom}:${pos}-${pos}" "$vcf" 2>/dev/null \
         | awk -v r="$ref" -v a="$alt" -F'\t' '$4==r && $5==a {split($10,f,":"); print f[1]; exit}')
    case "$gt" in
      ""|"0/0"|"0|0"|"./."|".|.") : ;;
      *) actual=$((actual+1)) ;;
    esac
  done
  if [ "$actual" -eq "$claimed" ]; then verdict="OK"
  else verdict="MISMATCH"; fail=$((fail+1)); fi
  printf "%-22s %-10s %-9s %-9s %s\n" "${chrom}:${pos}" "$gene" "$claimed/$cohort" "$actual/16" "$verdict"
done < /tmp/panel_targets.txt

echo
echo "recounted $total variants, $fail mismatched"
