#!/bin/bash
# Build a curated, browsable tree of dataset directories for the LAN server.
# Directory NAMES are the pseudonymised dataset ids (what the public catalog
# links to); symlink TARGETS are the real paths from the private registry.
# The server only ever exposes these directories, nothing else on /staging.
set -euo pipefail
SRC=/staging/data_catalog
PRIV=$SRC/private
SHARE=$SRC/share

rm -rf "$SHARE"; mkdir -p "$SHARE"
python3 - "$PRIV/registry.private.json" "$PRIV/name_map.json" "$SHARE" <<'PY'
import json, os, sys
from pathlib import Path
reg    = json.load(open(sys.argv[1]))
tokens = json.load(open(sys.argv[2]))["tokens"]
share  = Path(sys.argv[3])

def public_id(real_id):
    # Same substitution the anonymiser applies, so the id matches catalog.json.
    for real in sorted(tokens, key=len, reverse=True):
        real_id = real_id.replace(real, tokens[real])
    return real_id

for ds in reg["datasets"]:
    pid = public_id(ds["id"])
    links = {"raw": ds.get("root_path"), "processed": ds.get("processed_path")}
    for name, sub in (ds.get("sub_paths") or {}).items():
        links[name] = sub
    d = share / pid
    d.mkdir(exist_ok=True)
    for label, target in links.items():
        if not target:
            continue
        target = target.split(" (")[0].strip().rstrip("/")
        if not os.path.exists(target):
            print(f"  skip {pid}/{label}: target missing"); continue
        (d / label).symlink_to(target)
        # Print only the public id, never the real target, so this log is safe.
        print(f"  {pid}/{label}")
PY
