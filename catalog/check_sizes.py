#!/usr/bin/env python3
"""Compare derived (du) sizes with the lab's hand-curated sizes.
Reads the curated originals from private/, keyed by the pseudonymised id via
the private map, so no real id appears in this file."""
import json
cat = json.load(open("/staging/data_catalog/catalog.json"))
priv = "/staging/data_catalog/private"
tokens = json.load(open(f"{priv}/name_map.json"))["tokens"]
cur = {c["id"]: c for c in json.load(open(f"{priv}/curated_original.json"))}
# original id -> pseudonymised id, using the same substitution the anonymiser applies
def pub(real):
    for t in sorted(tokens, key=len, reverse=True):
        real = real.replace(t, tokens[t])
    return real
cur_by_pub = {pub(k): v for k, v in cur.items()}

print(f"  {'dataset':<24} {'du (derived)':>14}  {'curated gb':>10}  note")
for ds in cat["datasets"]:
    s = ds["live_scan"].get("size_bytes", {}); tot = ds["live_scan"].get("size_total_bytes")
    c = cur_by_pub.get(ds["id"]); gb_cur = c.get("gb") if c else None
    parts = " + ".join(f"{k}={v/1e9:.1f}G" for k, v in s.items())
    flag = ""
    if tot is not None and gb_cur:
        r = (tot/1e9)/gb_cur; flag = "" if 0.7 <= r <= 1.4 else "  <-- differs from curated"
    print(f"  {ds['id']:<24} {'' if tot is None else f'{tot/1e9:>12.1f} G'}  {'' if gb_cur is None else f'{gb_cur:>8} G'}  {parts}{flag}")
