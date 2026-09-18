#!/usr/bin/env python3
"""Merge the hand-maintained registry (identity/dates - things no scanner
can infer) with live scan_wes.py / scan_gsa.py output (facts about what's
actually on disk right now) into one generated catalog.json.

This replaces hand-edited HTML data arrays: registry.json says WHAT a
dataset is and WHERE it lives; this script re-derives sample counts and
completion status from disk on every run, so the catalog can't drift from
reality the way data-sources.html did.

Usage: generate_catalog.py <registry.json> <output catalog.json>
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def run_scanner(script_name: str, root_path: str) -> dict:
    path = Path(root_path)
    if not path.exists():
        return {"error": f"path does not exist: {root_path}"}
    try:
        out = subprocess.run(
            ["python3", str(SCRIPT_DIR / script_name), root_path],
            capture_output=True, text=True, timeout=300, check=True,
        )
        return json.loads(out.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": f"scanner failed: {e.stderr.strip()[:500]}"}
    except subprocess.TimeoutExpired:
        return {"error": "scanner timed out after 300s"}
    except json.JSONDecodeError:
        return {"error": "scanner produced non-JSON output"}


def dir_size_bytes(path: str):
    """Real on-disk size via du. None if the path is missing. du -sb follows
    the same accounting the lab used for the original 'Size' column."""
    try:
        out = subprocess.run(["du", "-sb", path], capture_output=True, text=True, timeout=600, check=True)
        return int(out.stdout.split()[0])
    except Exception:
        return None


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <registry.json> <output catalog.json>", file=sys.stderr)
        sys.exit(1)

    registry = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    entries = []

    for ds in registry["datasets"]:
        entry = dict(ds)
        dtype = ds.get("type")

        # Some datasets (e.g. cardio_main: cases/controls/transplant run as
        # separate batches) have more than one real output directory - scan
        # each named sub-path and combine, rather than assuming one root
        # covers the whole cohort.
        extra_roots = {
            k: v.split(" (")[0].strip()  # strip trailing "(+ ...)" notes
            for k, v in ds.get("sub_paths", {}).items()
            if v and Path(v.split(" (")[0].strip()).exists()
        }

        if dtype in ("wes", "wgs"):
            scan = run_scanner("scan_wes.py", ds["root_path"])
            if extra_roots and "error" not in scan:
                sub_scans = {name: run_scanner("scan_wes.py", path) for name, path in extra_roots.items()}
                scan["sub_path_scans"] = sub_scans
                extra_samples = sum(
                    s.get("sample_count", 0) for s in sub_scans.values() if "error" not in s
                )
                scan["sample_count_including_sub_paths"] = scan.get("sample_count", 0) + extra_samples
        elif dtype == "gsa":
            # root_path may be the raw IDAT/GenomeStudio export, which will
            # never have PLINK output - scan processed_path instead when set.
            scan_path = ds.get("processed_path") or ds["root_path"]
            scan = run_scanner("scan_gsa.py", scan_path)
        elif dtype == "targeted_panel":
            # Externally delivered per-sample zips (VCF + QA report + coverage
            # flags); read by streaming, never extracted.
            scan = run_scanner("scan_panel_zip.py", ds["root_path"])
        else:
            scan = {"error": f"unknown type: {dtype}"}

        # Flags the scanner cannot know from the directory alone.
        if "error" not in scan:
            has = scan.setdefault("has", {})
            if extra_roots:
                has["sub_cohorts"] = True
                # A dataset's capabilities are the union of everything found in
                # its root AND its sub-paths. cardio_main's root is raw FASTQ;
                # all 25 samples, their VCFs and the pathogenic aggregation live
                # in cases/ and controls/ - without this OR it reported no
                # per-sample data at all.
                for sub in scan.get("sub_path_scans", {}).values():
                    for k, v in (sub.get("has") or {}).items():
                        if v:
                            has[k] = True
            # aux_paths: directories that describe the SAME samples (annotation
            # tables, pathogenic-variant aggregations, pangenome re-runs). They
            # contribute capability flags and a file inventory but are never
            # counted as samples - scanning them as sub_paths would double-count.
            aux = {}
            for name, path in (ds.get("aux_paths") or {}).items():
                path = path.split(" (")[0].strip()
                if Path(path).exists():
                    a = run_scanner("scan_wes.py", path)
                    if "error" not in a:
                        aux[name] = {"root_path": path,
                                     "file_count": sum(s["file_count"] for s in a.get("samples", {}).values())
                                                   + len(a.get("cohort_level_files", [])),
                                     "has": a.get("has", {})}
                        for k, v in (a.get("has") or {}).items():
                            if v:
                                has[k] = True
            if aux:
                scan["aux_path_scans"] = aux
            if dtype == "gsa" and ds.get("root_path") and ds.get("processed_path") \
               and ds["root_path"] != ds["processed_path"]:
                has["raw_reads"] = True   # raw IDAT export exists separately
        entry["live_scan"] = scan

        # On-disk size, derived. A directory that lies INSIDE another counted
        # directory is reported for information but NOT added to the total -
        # du of the parent already includes it. (cardio_main's cases/ and
        # controls/ sit under its root; alsu_expanded's processed dir sits
        # under its root. Adding those again overstated both by ~30%.)
        if "error" not in scan:
            root = ds.get("root_path")
            candidates = [("root", root), ("processed", ds.get("processed_path"))]
            candidates += list(extra_roots.items())
            candidates += [(f"aux:{n}", p.split(" (")[0].strip()) for n, p in (ds.get("aux_paths") or {}).items()]
            sizes, counted, total = {}, [], 0
            def under(p, parents):
                rp = Path(p).resolve()
                return any(rp == Path(q).resolve() or Path(q).resolve() in rp.parents for q in parents)
            for label, p in candidates:
                if not p or not Path(p).exists():
                    continue
                b = dir_size_bytes(p)
                if b is None:
                    continue
                sizes[label] = b
                if not under(p, counted):
                    total += b
                    counted.append(p)
            scan["size_bytes"] = sizes
            scan["size_total_bytes"] = total

        # Flag registry claims that disagree with what the scanner actually found,
        # instead of silently trusting either side.
        discrepancies = []
        if "error" in scan:
            discrepancies.append(f"scan failed: {scan['error']}")
        else:
            n_claimed = ds.get("n_claimed")
            n_found = scan.get("sample_count_including_sub_paths", scan.get("sample_count"))
            n_raw = scan.get("raw_fastq_samples_detected")
            if n_claimed is not None and n_found:
                if n_claimed != n_found:
                    discrepancies.append(f"registry claims n={n_claimed}, scanner found {n_found} processed samples")
            elif n_claimed is not None and n_raw:
                if n_claimed != n_raw:
                    discrepancies.append(f"registry claims n={n_claimed}, scanner found {n_raw} raw-FASTQ samples (not yet processed)")
        entry["discrepancies"] = discrepancies

        entries.append(entry)

    def sh(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            return ""
    # The original page had a hand-typed host row (host, IP, OS, DRAGEN, RAM,
    # free space, scanned date). Every one of those is derivable, so derive it.
    host = {
        "hostname": sh("hostname -s"),
        "ip_lan": sh("hostname -I | tr ' ' '\\n' | grep -E '^10\\.' | head -1"),
        "ip_tailscale": sh("hostname -I | tr ' ' '\\n' | grep -E '^100\\.' | head -1"),
        "os": sh(". /etc/os-release && echo \"$PRETTY_NAME\""),
        "dragen": sh("ls -1 /opt/dragen 2>/dev/null | grep -E '^[0-9]' | sort -V | tr '\\n' ' '").strip(),
        "ram_gb": sh("free -g | awk '/^Mem:/{print $2}'"),
        "staging_free": sh("df -h /staging | awk 'NR==2{print $4\" / \"$2}'"),
    }

    catalog = {
        "host": host,
        "generated_at": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_note": (
            "sample counts, file inventories, and status are LIVE - re-derived from "
            "disk on every generation run via scan_wes.py/scan_gsa.py. Only id/name/"
            "date/type/root_path/description/detail_url come from the hand-maintained "
            "registry.json."
        ),
        "datasets": entries,
    }
    Path(sys.argv[2]).write_text(json.dumps(catalog, indent=2, ensure_ascii=False), encoding="utf-8")
    n_err = sum(1 for e in entries if "error" in e["live_scan"])
    n_disc = sum(1 for e in entries if e["discrepancies"])
    print(f"Wrote {len(entries)} datasets to {sys.argv[2]} ({n_err} scan errors, {n_disc} discrepancies)")


if __name__ == "__main__":
    main()
