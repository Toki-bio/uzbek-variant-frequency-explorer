#!/bin/bash
for c in node nodejs npm deno bun; do
  p=$(command -v "$c" 2>/dev/null)
  printf "%-8s %s\n" "$c" "${p:--}"
done
node --version 2>/dev/null || true
python3 - <<'PY'
import importlib.util as u
for m in ("playwright", "selenium", "html5lib", "bs4"):
    print(f"python:{m}", u.find_spec(m) is not None)
PY
