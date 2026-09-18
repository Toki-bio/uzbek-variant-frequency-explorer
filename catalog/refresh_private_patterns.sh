#!/bin/bash
# Regenerate the private leak pattern + extra-token seed from the pseudonym map.
# Run after anonymize.py build. Outputs stay in private/ (chmod 600).
set -euo pipefail
PRIV=/staging/data_catalog/private
python3 - "$PRIV" <<'PY'
import json, sys
from pathlib import Path
priv = Path(sys.argv[1]); m = json.load(open(priv / "name_map.json"))["tokens"]
toks = sorted(m, key=len, reverse=True)
(priv / "leak_pattern.txt").write_text("|".join(toks) + "\n", encoding="utf-8")
extra = [f"{t}={v}" for t, v in m.items() if not v.startswith(("CARDIO_OCT_",))]
(priv / "extra_tokens.txt").write_text("# names that are not sample ids (dataset id, title, path parts)\n" + "\n".join(extra) + "\n", encoding="utf-8")
print(f"  leak_pattern.txt: {len(toks)} tokens; extra_tokens.txt: {len(extra)}")
PY
chmod 600 "$PRIV"/leak_pattern.txt "$PRIV"/extra_tokens.txt
