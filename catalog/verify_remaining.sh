#!/bin/bash
# Independent checks for the parts not yet verified: the sample crosswalk,
# the GSA MAF values, and the rescan48 <-> alsu ID question.
# Standard tools only (comm, sort, cut, awk, plink) - no project code.
set -uo pipefail
PLINK=/usr/bin/plink
D=/staging/data_catalog

ALSU=/staging/ALSU-analysis/winter2025/3_post-imputation/ConvSK_final_clean
EXP=/staging/ALSU-analysis/spring2026/full_expanded_cohort/imputation_results/hq_filtered/UZB_imputed_HQ_clean
G2=/staging/GWAS2026-2/plink/gwas2026_2_varqc
G96=/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas2026/plink/gwas2026_varqc
R48=/staging/ALSU-analysis/admixture_analysis/temp/dragen_array_test_20260513/gwas48redone/plink/gwas48redone_raw

# PLINK .fam files here are NOT consistently delimited: ALSU's are
# space-separated, rescan48's are tab-separated. 'cut -f2' assumes tabs and
# silently returns the whole line for space-delimited files, which made every
# comparison against ALSU collapse to zero. awk's default field splitting
# handles any whitespace, which is what the Python crosswalk already does.
ids () { awk '{print $2}' "$1.fam" 2>/dev/null | tr -d '\r' | sort -u; }

echo "=== 1. Crosswalk overlaps, recomputed with comm (page claims in brackets) ==="
for pair in "alsu|$ALSU|alsu_expanded|$EXP|1026" \
            "gwas2026_2|$G2|alsu_expanded|$EXP|83" \
            "gwas96|$G96|alsu_expanded|$EXP|78" \
            "rescan48|$R48|alsu_expanded|$EXP|47" \
            "rescan48|$R48|alsu|$ALSU|0" ; do
  IFS='|' read -r n1 p1 n2 p2 claim <<< "$pair"
  ids "$p1" > /tmp/a.txt; ids "$p2" > /tmp/b.txt
  got=$(comm -12 /tmp/a.txt /tmp/b.txt | wc -l)
  [ "$got" = "$claim" ] && v=OK || v="MISMATCH"
  printf "  %-14s ^ %-14s  claimed %-5s got %-5s %s\n" "$n1" "$n2" "$claim" "$got" "$v"
done

echo
echo "=== 2. rescan48 vs alsu: why zero overlap? ==="
ids "$R48" > /tmp/r.txt; ids "$ALSU" > /tmp/al.txt; ids "$EXP" > /tmp/ex.txt
echo "  rescan48 ID examples : $(head -4 /tmp/r.txt | tr '\n' ' ')"
echo "  alsu     ID examples : $(head -4 /tmp/al.txt | tr '\n' ' ')"
echo "  rescan48 IDs also in alsu_expanded: $(comm -12 /tmp/r.txt /tmp/ex.txt | wc -l) / $(wc -l < /tmp/r.txt)"
echo "  rescan48 IDs also in alsu:          $(comm -12 /tmp/r.txt /tmp/al.txt | wc -l) / $(wc -l < /tmp/r.txt)"
echo "  -> are rescan48 IDs in alsu's PRE-imputation set instead?"
PRE=/staging/ALSU-analysis/winter2025/PLINK_301125_0312/ConvSK_raw
if [ -f "$PRE.fam" ]; then
  ids "$PRE" > /tmp/pre.txt
  echo "     alsu PRE-imputation (ConvSK_raw) ID examples: $(head -4 /tmp/pre.txt | tr '\n' ' ')"
  echo "     rescan48 IDs found there: $(comm -12 /tmp/r.txt /tmp/pre.txt | wc -l) / $(wc -l < /tmp/r.txt)"
else
  echo "     (pre-imputation fileset not found at $PRE)"
fi

echo
echo "=== 3. GSA MAFs: recompute with plink --freq, compare to what we stored ==="
python3 - <<'PY' > /tmp/maf_targets.txt
import json
d = json.load(open("/staging/data_catalog/gsa_panel_gwas2026_2.json"))
for s in d["snps"][:6]:
    if s.get("maf") is not None:
        print(f'{s["snp_id"]}\t{s["maf"]}')
PY
cut -f1 /tmp/maf_targets.txt > /tmp/snps.txt
$PLINK --bfile "$G2" --extract /tmp/snps.txt --freq --out /tmp/recheck >/dev/null 2>&1
printf "  %-24s %-10s %-10s %s\n" "SNP" "STORED" "PLINK" "VERDICT"
while IFS=$'\t' read -r snp stored; do
  got=$(awk -v s="$snp" 'NR>1 && $2==s {print $5}' /tmp/recheck.frq)
  if [ -z "$got" ]; then v="NOT FOUND"
  elif awk -v a="$stored" -v b="$got" 'BEGIN{exit !(a-b<1e-6 && b-a<1e-6)}'; then v="OK"
  else v="MISMATCH"; fi
  printf "  %-24s %-10s %-10s %s\n" "$snp" "$stored" "${got:-'-'}" "$v"
done < /tmp/maf_targets.txt
