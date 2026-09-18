#!/usr/bin/env python3
"""Repair UTF-8 double/triple-encoding in the curated text.

The text was written as UTF-8, read back by Windows as cp1252, and written
again as UTF-8 - in some fields twice over. Two things the naive fix misses:
  - cp1252 leaves 0x81 0x8D 0x8F 0x90 0x9D undefined; Windows passes those
    bytes through as C1 control characters, so the mangled text contains
    e.g. '\x9d'. Python's strict cp1252 codec refuses to encode them, so a
    lenient encoder maps U+0080..U+009F straight back to their byte values.
  - Each mis-decode adds a layer. Repair is applied iteratively until no
    mojibake marker remains (bounded), so single- and double-mangled
    strings both come back.
Every change is counted and sampled; refuses to write if any marker survives.
"""
import json, sys
from pathlib import Path

MARKERS = ("Ã", "â€", "â‚", "Â", "Ð", "Ñ")   # Ð/Ñ = mangled Cyrillic lead bytes

def lenient_cp1252(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        try:
            out += ch.encode("cp1252")
        except UnicodeEncodeError:
            o = ord(ch)
            if 0x80 <= o <= 0x9F:
                out.append(o)          # Windows C1 pass-through
            else:
                raise
    return bytes(out)

def one_pass(s: str):
    try:
        return lenient_cp1252(s).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return None

def repair(s: str) -> str:
    cur = s
    for _ in range(4):
        if not any(m in cur for m in MARKERS):
            return cur
        nxt = one_pass(cur)
        if nxt is None or nxt == cur:
            return cur
        cur = nxt
    return cur

def walk(o, stats):
    if isinstance(o, str):
        r = repair(o)
        if r != o:
            stats["changed"] += 1
            if len(stats["samples"]) < 4:
                stats["samples"].append((o[:70], r[:70]))
        return r
    if isinstance(o, list):  return [walk(v, stats) for v in o]
    if isinstance(o, dict):  return {k: walk(v, stats) for k, v in o.items()}
    return o

for p in map(Path, sys.argv[1:]):
    data = json.loads(p.read_text(encoding="utf-8"))
    stats = {"changed": 0, "samples": []}
    fixed = walk(data, stats)
    dump = json.dumps(fixed, ensure_ascii=False)
    leftover = [m for m in ("Ã", "â€", "â‚") if m in dump]   # Ð/Ñ are legitimate Cyrillic once repaired
    print(f"{p.name}: {stats['changed']} strings repaired, markers left: {leftover or 'none'}")
    for a, b in stats["samples"]:
        print(f"   {a!r}\n-> {b!r}")
    if leftover:
        sys.exit("ABORT: mojibake survived - not writing")
    p.write_text(json.dumps(fixed, indent=2, ensure_ascii=False), encoding="utf-8")
