# Testing

Three layers, deliberately separate, because each of the bugs that shipped
here was invisible to the layer above it.

## 1. Data checks — `verify_catalog.py`

```bash
python3 catalog/verify_catalog.py catalog/catalog.json catalog/panel_summary.json
```

Re-derives every number by a *different* method than the scanner used, so
agreement is evidence rather than a tautology: GSA counts via `wc -l` on the
`.fam` plus PLINK's own log line, sequencing counts via shell glob on a
required file type, every claimed path `stat`-ed, panel carrier arithmetic
recomputed. **58 checks.**

This is still this project's code checking this project's code. For an
outside check, see below.

## 2. Independent checks — standard tools only

```bash
bash catalog/independent_check.sh        # dataset counts, panel BED vs NCBI GTF
bash catalog/verify_remaining.sh         # crosswalk overlaps, GSA MAFs
bash catalog/verify_panel_independent.sh # panel carrier counts, recounted from VCFs
bash catalog/check_build.sh              # which genome build each fileset is really in
```

No project code is involved in the recount — only `wc`, `ls`, `grep`, `cut`,
`awk`, `comm`, `bcftools`, `plink`, `zcat`. Run them and compare the output to
the page yourself.

`check_build.sh` is worth singling out: it determines each fileset's genome
build *empirically*, by counting variants in each gene's hg38 window versus
its hg19 window, rather than trusting documentation. It caught a real error —
ALSU panel coverage had been computed against hg19-lifted coordinates while
the data is GRCh38.

## 3. Browser checks — real rendered DOM

```powershell
powershell -File catalog/browser_test.ps1     # live site
powershell -File catalog/browser_test.ps1 -Url http://10.10.8.149:8090/
powershell -File catalog/detail_test.ps1      # detail drawer
```

Renders the page in headless Chrome/Edge with JS executed and data fetched,
then asserts on the resulting DOM. **22 + 9 checks.** No install needed —
uses the Chrome or Edge already on the machine.

`detail_test.ps1` covers what a static dump cannot: the detail drawer only
renders on click, so it takes the artifact build (identical render code, data
inlined), appends a harness that calls `openDatasetDetail()` for every
dataset, and reads back what the drawer actually produced.

### Why this layer exists

Every rendering bug that reached the user passed all data checks:

| Bug | Data checks said | Reality on screen |
|---|---|---|
| GSA sample counts absent from scanner output | green | `?` / nothing in the `n` column |
| `cardio_main` samples live in sub-paths, detail view read only top level | green | `Samples (0)` on a 25-sample dataset |
| `scan_gsa.py` emitted no per-sample records at all | **53/53 green** | `Samples (0)` on all five array datasets |
| stale `catalog.json` served from cache (`max-age=600`) | green | corrected counts still rendering as old values |

The third is the instructive one. After the second bug I added a check
asserting each dataset's headline count is backed by that many reachable
per-sample records — then scoped it `if ds["type"] in ("wes","wgs")`, which
excluded precisely the five datasets where it was broken. A check that
exempts the failing cases is worse than no check, because it manufactures
confidence. It is now unscoped.

## Notes for whoever maintains these

- `.fam` delimiting is **not** consistent: ALSU's are space-separated,
  rescan48's are tab-separated. Use `awk '{print $2}'` or Python's
  `line.split()`, never `cut -f2`.
- `--dump-dom` emits the whole document including `<script>`. Strip it before
  any text assertion, or you match the JS source instead of the page.
- `toLocaleString()` formats per the *viewer's* locale — a Russian-locale
  browser renders `4313` as `4&nbsp;313`. Keep separator matching permissive.
- Don't name PowerShell variables `profile` or `args`; both are automatic,
  and assigning to the latter silently does nothing.
