#!/bin/bash
# Build every flavour of the catalog page from the lab's original + extensions.
set -euo pipefail
SRC=/staging/data_catalog
BUILD=$(date -u +%Y%m%d%H%M%S)
LAN_URL="http://10.10.8.149:8090"
PAT=$(cat /staging/data_catalog/private/leak_pattern.txt)   # names live ONLY in private/

echo "=== 1. patch the original into the master page (placeholders intact) ==="
python3 "$SRC/patch_original.py" "$SRC/orig_data_sources.html" "$SRC/catalog_extensions.js" "$SRC/page_master.html"

bash "$SRC/setup_share.sh" >/dev/null

echo
echo "=== 2. LAN copy: served at $LAN_URL/, live data, relative browse links ==="
sed "s|__BUILD_ID__|$BUILD|g; s|__SHARE_BASE__|share/|g; \
     s|catalog/catalog.json|catalog.json|g; s|catalog/panel_web.json|panel_web.json|g; s|catalog/samples.json|samples.json|g; \
     s|href=\"index.html\">&larr; Variant Explorer|href=\"https://toki-bio.github.io/uzbek-variant-frequency-explorer/\">\&larr; Variant Explorer (GitHub)|" \
  "$SRC/page_master.html" > "$SRC/index.html"

echo "=== 3. standalone single file: data inlined, absolute browse links ==="
sed "s|__BUILD_ID__|$BUILD|g; s|__SHARE_BASE__|$LAN_URL/share/|g; \
     s|href=\"index.html\">&larr; Variant Explorer|href=\"https://toki-bio.github.io/uzbek-variant-frequency-explorer/\">\&larr; Variant Explorer (GitHub)|" \
  "$SRC/page_master.html" > "$SRC/_standalone_src.html"
python3 "$SRC/build_artifact.py" "$SRC/_standalone_src.html" "$SRC/catalog.json" "$SRC/panel_web.json" "$SRC/samples.json" "$SRC/catalog_standalone.html"
python3 "$SRC/build_artifact.py" "$SRC/_standalone_src.html" "$SRC/catalog.json" "$SRC/panel_web.json" "$SRC/samples.json" "$SRC/artifact.html" --fragment
rm -f "$SRC/_standalone_src.html"
cp -f "$SRC/catalog_standalone.html" "$SRC/genotyping_catalog.html"   # same file, the name people will guess

echo "=== 3b. public copy for GitHub: no LAN links, fetches from catalog/ ==="
sed "s|__BUILD_ID__|$BUILD|g; s|__SHARE_BASE__||g" "$SRC/page_master.html" > "$SRC/data-sources.public.html"

echo
echo "=== 4. leak check ==="
for f in index.html catalog_standalone.html artifact.html data-sources.public.html; do
  grep -qE "$PAT" "$SRC/$f" && { echo "  LEAK: $f"; exit 1; } || echo "  clean: $f"
done
for u in "/" "/catalog.json" "/share/"; do printf "  %-14s HTTP %s\n" "$u" "$(curl -s -o /dev/null -w '%{http_code}' "$LAN_URL$u")"; done
echo "BUILD_ID=$BUILD"
