# Browser-level test for the genotyping data catalog page.
#
# Renders the REAL page in headless Chrome (JS executed, data fetched) and
# asserts on the resulting DOM. This covers the gap that every data-level
# check missed: three separate bugs shipped where the numbers were correct
# but nothing rendered - "Samples (0)" on datasets that had samples, empty
# tables, stale cached counts.
#
# Usage:
#   powershell -File browser_test.ps1                      # test live site
#   powershell -File browser_test.ps1 -Url http://10.10.8.149:8090/
param(
  [string]$Url = "https://toki-bio.github.io/uzbek-variant-frequency-explorer/data-sources.html",
  [int]$WaitMs = 9000
)

$chrome = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { Write-Error "No Chrome/Edge found"; exit 2 }

# NOTE: avoid the names "profile" and "args" for these variables - both are
# PowerShell automatic variables, and assigning to the latter silently does
# nothing, which is how the first version of this script produced an empty DOM.
$profDir = Join-Path $env:TEMP ("catalog_bt_" + [guid]::NewGuid().ToString("N").Substring(0,8))
$dom     = Join-Path $env:TEMP "catalog_dom.html"
$errFile = Join-Path $env:TEMP "catalog_dom_err.txt"

# --virtual-time-budget lets fetches/timers settle before the DOM is dumped.
$chromeArgs = @(
  "--headless=new","--disable-gpu","--no-sandbox","--dump-dom",
  "--virtual-time-budget=$WaitMs",
  "--user-data-dir=$profDir",
  $Url
)
$proc = Start-Process -FilePath $chrome -ArgumentList $chromeArgs -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $dom -RedirectStandardError $errFile
$html = Get-Content $dom -Raw -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $profDir -ErrorAction SilentlyContinue

if (-not $html) { Write-Error "Browser produced no DOM"; exit 2 }
Write-Host ("rendered DOM: {0:N0} chars from {1}" -f $html.Length, $Url)

# --dump-dom emits the whole document including the inline <script>. Text
# searches must run against the visible body only, or they match the JS
# source - e.g. the literal 'No individually-tracked samples at this stage'
# inside a template string, or 'Could not load:' in the error handler, both
# of which are present in source even when nothing failed.
$body = [regex]::Replace($html, '<script[^>]*>.*?</script>', '', 'Singleline')
Write-Host ("body without script: {0:N0} chars" -f $body.Length)
Write-Host ""

$fails = 0; $passes = 0
function Check($name, $cond, $detail) {
  if ($cond) { Write-Host "[PASS] $name"; $script:passes++ }
  else { Write-Host "[FAIL] $name - $detail" -ForegroundColor Red; $script:fails++ }
}

# Count <tr> inside a given tbody id.
function RowCount($tbodyId) {
  $m = [regex]::Match($html, "<tbody id=`"$tbodyId`"[^>]*>(.*?)</tbody>", "Singleline")
  if (-not $m.Success) { return -1 }
  return ([regex]::Matches($m.Groups[1].Value, "<tr")).Count
}

# --- 1. The page actually rendered data, not just static scaffolding ---
# On success the JS sets loadState to display:none - the text stays in the
# DOM, so assert on the inline style rather than on absence of the string.
$loadDiv = [regex]::Match($body, '<div id="loadState"[^>]*>').Value
Check "loading banner hidden after load" ($loadDiv -match 'display:\s*none') "loadState still visible: $loadDiv"
Check "no visible load error" ($body -notmatch 'Could not load:') "page body reported a failed fetch"
Check "data generation timestamp shown" ($body -match 'data generated \d{4}-\d{2}-\d{2}') "genStamp missing or unknown"

# --- 2. Dataset table populated ---
$dsRows = RowCount "datasetBody"
Check "dataset table has rows" ($dsRows -ge 9) "found $dsRows rows (expected >= 9)"

# --- 3. Every dataset shows a real sample count, not 0/?/undefined ---
# Headline counts we expect to appear as <td class="num">N</td> in the table.
foreach ($n in @(1074, 1268, 87, 83, 48, 25, 16, 12)) {
  Check "sample count $n rendered" ($html -match ">$n<") "count $n not found in DOM"
}
Check "no 'undefined' rendered" ($body -notmatch 'undefined') "literal 'undefined' present in rendered body"
Check "no 'NaN' rendered" ($body -notmatch 'NaN') "literal 'NaN' present in rendered body"

# --- 4. Summary stats not all zero ---
$stats = [regex]::Matches($html, '<div class="n">(\d[\d,]*)</div>') | ForEach-Object { $_.Groups[1].Value }
Check "summary stats present and non-zero" (($stats.Count -ge 3) -and ($stats | Where-Object { $_ -ne "0" }).Count -ge 3) "stats: $($stats -join ', ')"

# --- 5. Focal panel + GSA coverage + samples tabs populated ---
Check "panel table has rows" ((RowCount "panelBody") -ge 1) "panelBody empty - focal panel did not render"
Check "GSA coverage table has rows" ((RowCount "gsaBody") -ge 5) "gsaBody has $(RowCount 'gsaBody') rows (expected 5 array datasets)"
Check "sample crosswalk table has rows" ((RowCount "sampleBody") -ge 1) "sampleBody empty"
Check "dataset overlap table has rows" ((RowCount "overlapBody") -ge 1) "overlapBody empty"

# --- 6. The specific regressions that shipped before ---
# NOTE: the "Samples (0)" regression lives in the detail drawer, which only
# renders on click and therefore cannot be asserted from a static page dump -
# checking for the string here only ever matched the JS source. That case is
# covered properly by detail_test.ps1, which drives openDatasetDetail() for
# every dataset in a real browser.
Check "external lookup links present" ($body -match 'gnomad\.broadinstitute\.org/variant/') "no gnomAD deep links in panel rows"
# toLocaleString() formats thousands per the VIEWER's locale - a Russian-locale
# browser renders 4313 as "4&nbsp;313", not "4,313". Keep the separator class
# permissive or this passes on one machine and fails on another.
Check "panel row cap note rendered" `
  ($body -match 'Showing first \d+ of [\d,.\s]+(&nbsp;)?[\d,.\s]*matching variants') `
  "panel row cap note missing"
Check "panel table capped at 250 rows" ((RowCount "panelBody") -eq 250) "panelBody has $(RowCount 'panelBody') rows, expected exactly 250"

Write-Host ""
Write-Host "=== $passes passed, $fails failed ==="
if ($fails -gt 0) { exit 1 } else { exit 0 }
