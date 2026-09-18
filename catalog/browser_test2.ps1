# Browser-level test for the data-aware catalog page (built on the lab's
# original data-sources layout). Renders the real page in headless Chrome,
# JS executed, data fetched, then asserts on the DOM.
param(
  [string]$Url = "http://10.10.8.149:8090/",
  [int]$WaitMs = 12000
)
$chrome = @("C:\Program Files\Google\Chrome\Application\chrome.exe","C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { Write-Error "No Chrome/Edge"; exit 2 }
$profDir = Join-Path $env:TEMP ("cat2_" + [guid]::NewGuid().ToString("N").Substring(0,8))
$dom = Join-Path $env:TEMP "cat2_dom.html"
Start-Process -FilePath $chrome -ArgumentList @("--headless=new","--disable-gpu","--no-sandbox","--dump-dom","--virtual-time-budget=$WaitMs","--user-data-dir=$profDir","--allow-file-access-from-files",$Url) -NoNewWindow -Wait -RedirectStandardOutput $dom -RedirectStandardError (Join-Path $env:TEMP "cat2_err.txt") | Out-Null
$html = Get-Content $dom -Raw -ErrorAction SilentlyContinue
if (-not $html) { Write-Error "no DOM"; exit 2 }
$body = [regex]::Replace($html, '<script[^>]*>.*?</script>', '', 'Singleline')
Write-Host ("rendered {0:N0} chars from {1}" -f $html.Length, $Url); Write-Host ""

$fails = 0; $passes = 0
function Check($n, $c, $d) { if ($c) { Write-Host "[PASS] $n"; $script:passes++ } else { Write-Host "[FAIL] $n - $d" -ForegroundColor Red; $script:fails++ } }
function Rows($id) { $m = [regex]::Match($body, "<tbody id=`"$id`"[^>]*>(.*?)</tbody>", 'Singleline'); if (-not $m.Success) { return -1 }; return ([regex]::Matches($m.Groups[1].Value, '<tr')).Count }

# --- load & host row ---
$ls = [regex]::Match($body, '<div id="loadState"[^>]*>').Value
Check "loading banner hidden" ($ls -match 'display:\s*none') "loadState visible: $ls"
Check "no load error" ($body -notmatch 'Could not load:') "fetch failed"
foreach ($id in 'mh-host','mh-ip','mh-os','mh-dragen','mh-ram','mh-free','mh-gen') {
  $v = [regex]::Match($body, "id=`"$id`">([^<]*)<").Groups[1].Value
  Check "host row $id filled" (($v -ne '') -and ($v -ne '…') -and ($v -ne '—')) "value='$v'"
}

# --- original table populated (data rows are class drow; detail rows follow each) ---
$drows = ([regex]::Matches($body, 'class="drow"')).Count
Check "dataset rows rendered (9)" ($drows -eq 9) "found $drows"
foreach ($n in '1,074','1,268','87','83','48','25','16','12') { Check "samples label '$n' present" ($body -match [regex]::Escape($n)) "missing" }
Check "size column populated" (([regex]::Matches($body, 'class="r size-v">[^<]*GB')).Count -ge 8) "GB values missing"
Check "no 'undefined'" ($body -cnotmatch 'undefined') "literal undefined"
# -cnotmatch: PowerShell -match is case-insensitive and 'NaN' matches 'domi**nan**t' in curated notes
Check "no 'NaN'" ($body -cnotmatch 'NaN') "literal NaN"
Check "targeted panel badge" ($body -match 'b-panel') "cardio_oct not shown as panel"

# --- data-awareness: sections gated on has ---
$dp = @{}
foreach ($m in [regex]::Matches($body, '<div class="dp" id="dp-([^"]+)">(.*?)</div></td>', 'Singleline')) { $dp[$m.Groups[1].Value] = $m.Groups[2].Value }
Check "expanded panels rendered for all 9" ($dp.Count -eq 9) "found $($dp.Count)"
function Has($id, $title) { return ($dp[$id] -match ('<h4>' + [regex]::Escape($title))) }
Check "alsu: array coverage section present"        (Has 'alsu' 'Cardiomyopathy panel coverage') ""
Check "alsu: NO clinical reports section"           (-not (Has 'alsu' 'Clinical reports')) "shown for a GSA dataset"
Check "alsu: NO panel variant calls section"        (-not (Has 'alsu' 'Cardiomyopathy panel variants')) "shown for an array dataset"
Check "cardio_wes: panel variants section present"  (Has 'cardio_wes_v350432671' 'Cardiomyopathy panel variants') ""
Check "cardio_wes: clinical reports present"        (Has 'cardio_wes_v350432671' 'Clinical reports') ""
Check "cardio_wes: NO array coverage section"       (-not (Has 'cardio_wes_v350432671' 'Cardiomyopathy panel coverage')) "shown for a WES dataset"
Check "cardio_main: sub-cohorts section present"    (Has 'cardio_main' 'Sub-cohorts') ""
Check "cardio_main: related directories present"    (Has 'cardio_main' 'Related directories') ""
Check "cardio_oct: panel variants (lifted) present" (Has 'cardio_oct' 'Cardiomyopathy panel variants') ""
Check "cardio_oct: curated/derived conflict shown"  ($dp['cardio_oct'] -match 'class="conflict"') "WGS-vs-panel conflict not surfaced"
Check "pavel: raw-only message, no sample table"    (($dp['pavel_wes_single'] -match 'nothing has been run through a pipeline') -and ($dp['pavel_wes_single'] -notmatch '<h4>Samples \(')) ""
Check "gwas2026_2: NO imputation chip"              ($dp['gwas2026_2'] -notmatch '>imputation<') "imputation shown for unimputed batch"
Check "alsu_expanded: imputation chip present"      ($dp['alsu_expanded'] -match '>imputation<') ""
Check "curated Details section kept (alsu kv)"      ($dp['alsu'] -match 'kv-k">Build') "original kv list missing"
Check "curated File structure kept"                 ($dp['alsu'] -match 'class="ftree"') "original tree missing"
Check "Notes textarea kept"                         ($dp['alsu'] -match '<textarea class="nt"') "original notes missing"
Check "size breakdown section present"              (Has 'cardio_main' 'Size on disk') ""

# --- extra views ---
# match the tab class exactly - 'vtab' is also a prefix of the container 'vtabs'
Check "tab bar present" (([regex]::Matches($body, 'class="vtab( active)?"')).Count -eq 3) ""
Check "focal panel view has rows" ((Rows 'pnBody') -ge 1) "pnBody rows=$(Rows 'pnBody')"
Check "focal panel capped at 250" ((Rows 'pnBody') -eq 250) "rows=$(Rows 'pnBody')"
Check "cardio_oct appears in panel cohorts" ($body -match '>cardio_oct \d+/12') "no cardio_oct carrier chips"
Check "samples view has rows" ((Rows 'smBody') -ge 1) "smBody rows=$(Rows 'smBody')"
Check "gnomAD links present" ($body -match 'gnomad\.broadinstitute\.org/variant/') ""
Check "browse links present" ($body -match 'class="plink"') "no share links on paths"

Write-Host ""; Write-Host "=== $passes passed, $fails failed ==="
if ($fails) { exit 1 } else { exit 0 }
