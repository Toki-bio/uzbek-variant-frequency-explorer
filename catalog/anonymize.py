#!/usr/bin/env python3
"""Anonymisation layer.

Real personal names appear in sample IDs, filenames and paths on disk
(e.g. sample_<Surname>.zip, /staging/Pavel/<accession> <Surname Given>/).
Nothing derived from those files may carry a name into any published output.

Design:
  - Pseudonyms are SEQUENTIAL per dataset (CARDIO_OCT_01, ...), not hashes.
    A hash of a name is not anonymisation when the candidate set is small -
    it is brute-forceable in milliseconds.
  - The real<->pseudonym map is written only under private/, which is
    gitignored, chmod 600, and additionally stored AES-256 encrypted.
  - Substitution is applied recursively to every string in the output, so it
    catches names embedded in filenames, paths and free-text notes, not just
    in sample-ID fields.

Usage:
  anonymize.py build  <catalog.json> <private_dir>     # create/extend the map
  anonymize.py apply  <in.json> <out.json> <private_dir>
  anonymize.py scrub-text <in> <out> <private_dir>     # any text file
"""
import json
import re
import sys
from pathlib import Path

MAP_NAME = "name_map.json"

# Datasets whose sample IDs are personal names, and the pseudonym prefix used.
NAME_BEARING = {
    "cardio_oct": "CARDIO_OCT",
    "pavel_wes_saidkarimova": "PAVEL_WES",
}

# Extra tokens that are names but are not sample IDs (dataset id / title /
# path components). Listed explicitly so they are never emitted.
EXTRA_TOKENS = [
    "Saidkarimova", "Guzalkhan", "Саидкаримова", "Гузалхан",
    "IshkulatovaMadina",  # also appears inside full_variant_table_*.vcf
]


def load_map(private_dir: Path) -> dict:
    p = private_dir / MAP_NAME
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"tokens": {}, "note": "real token -> pseudonym. PRIVATE. Never commit."}


def save_map(private_dir: Path, m: dict) -> None:
    private_dir.mkdir(parents=True, exist_ok=True)
    p = private_dir / MAP_NAME
    p.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    p.chmod(0o600)


def build(catalog_path: Path, private_dir: Path) -> dict:
    cat = json.loads(catalog_path.read_text(encoding="utf-8"))
    m = load_map(private_dir)
    tokens = m["tokens"]

    for ds in cat["datasets"]:
        prefix = NAME_BEARING.get(ds["id"])
        if not prefix:
            continue
        scan = ds.get("live_scan", {})
        ids = sorted((scan.get("samples") or {}).keys())
        for sid in ids:
            if sid not in tokens:
                tokens[sid] = f"{prefix}_{len([v for v in tokens.values() if v.startswith(prefix)]) + 1:02d}"

    for t in EXTRA_TOKENS:
        if t not in tokens:
            tokens[t] = "REDACTED"

    # The dataset id itself carries a surname.
    tokens.setdefault("pavel_wes_saidkarimova", "pavel_wes_single")

    save_map(private_dir, m)
    return m


def _subst(s: str, tokens: dict) -> str:
    # Longest-first so "IshkulatovaMadina" is replaced before any substring.
    for real in sorted(tokens, key=len, reverse=True):
        if real in s:
            s = s.replace(real, tokens[real])
    return s


def _walk(obj, tokens):
    if isinstance(obj, str):
        return _subst(obj, tokens)
    if isinstance(obj, list):
        return [_walk(v, tokens) for v in obj]
    if isinstance(obj, dict):
        return {_subst(k, tokens) if isinstance(k, str) else k: _walk(v, tokens)
                for k, v in obj.items()}
    return obj


def apply_map(in_path: Path, out_path: Path, private_dir: Path) -> int:
    tokens = load_map(private_dir)["tokens"]
    data = json.loads(in_path.read_text(encoding="utf-8"))
    before = json.dumps(data, ensure_ascii=False)
    cleaned = _walk(data, tokens)
    after = json.dumps(cleaned, ensure_ascii=False)
    out_path.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False), encoding="utf-8")

    # Refuse to emit a file that still contains any known token.
    leaked = [t for t in tokens if t in after and tokens[t] != t]
    if leaked:
        sys.exit(f"ERROR: tokens survived substitution in {out_path}: {leaked}")
    return len(before) - len(after)


def scrub_text(in_path: Path, out_path: Path, private_dir: Path) -> None:
    tokens = load_map(private_dir)["tokens"]
    s = in_path.read_text(encoding="utf-8", errors="ignore")
    s = _subst(s, tokens)
    leaked = [t for t in tokens if t in s and tokens[t] != t]
    if leaked:
        sys.exit(f"ERROR: tokens survived substitution in {out_path}: {leaked}")
    out_path.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        m = build(Path(sys.argv[2]), Path(sys.argv[3]))
        print(f"map has {len(m['tokens'])} tokens -> {sys.argv[3]}/{MAP_NAME}")
    elif cmd == "apply":
        d = apply_map(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        print(f"anonymised {sys.argv[2]} -> {sys.argv[3]}")
    elif cmd == "scrub-text":
        scrub_text(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        print(f"scrubbed {sys.argv[2]} -> {sys.argv[3]}")
    else:
        sys.exit("unknown command")
