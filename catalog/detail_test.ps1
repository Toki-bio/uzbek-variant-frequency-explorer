# Browser-level test of the DETAIL DRAWER - the part a static page dump
# cannot reach, because it only renders when a dataset row is clicked.
# This is exactly where the "Samples (0)" bug lived on every array dataset.
#
# Method: take the artifact build (identical render code, data inlined, no
# fetch), append a harness that calls openDatasetDetail() for every dataset
# and records what the drawer actually produced, then render it in headless
# Chrome and read the result out of the DOM.
param(
  [string]$Artifact = "C:\Users\user\AppData\Local\Temp\claude\C--Users-user\bdd48d28-aac8-473e-b394-24af66bbdb77\scratchpad\catalog_viewer_artifact.html"
)

$chrome = @(
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) { Write-Error "No Chrome/Edge found"; exit 2 }

$frag = Get-Content $Artifact -Raw
$harness = @'
<div id="HARNESS_RESULT" style="display:none"></div>
<script>
window.addEventListener('load', function(){
  var out = [];
  try {
    for (var i=0; i<CATALOG.datasets.length; i++) {
      var ds = CATALOG.datasets[i];
      openDatasetDetail(ds.id);
      var h = document.getElementById('detail').innerHTML;
      var m = h.match(/Samples \((\d+)\)/);
      var rows = (h.match(/<tr/g) || []).length;
      var empty = /No individually-tracked samples at this stage/.test(h) ? 'EMPTYMSG' : 'ok';
      out.push(ds.id + ':hdr=' + (m ? m[1] : 'NONE') + ',rows=' + rows + ',' + empty);
    }
  } catch (e) { out.push('EXCEPTION:' + e.message); }
  document.getElementById('HARNESS_RESULT').textContent = out.join(' ;; ');
});
</script>
'@

$page = "<!doctype html><html><head><meta charset=`"utf-8`"></head><body>" + $frag + $harness + "</body></html>"
$tmpPage = Join-Path $env:TEMP "catalog_detail_test.html"
[System.IO.File]::WriteAllText($tmpPage, $page, [System.Text.UTF8Encoding]::new($false))

$profDir = Join-Path $env:TEMP ("catalog_dt_" + [guid]::NewGuid().ToString("N").Substring(0,8))
$dom     = Join-Path $env:TEMP "catalog_detail_dom.html"
$errFile = Join-Path $env:TEMP "catalog_detail_err.txt"

Start-Process -FilePath $chrome -ArgumentList @(
  "--headless=new","--disable-gpu","--no-sandbox","--dump-dom",
  "--virtual-time-budget=15000","--user-data-dir=$profDir",
  "--allow-file-access-from-files",
  ("file:///" + $tmpPage.Replace('\','/'))
) -NoNewWindow -Wait -RedirectStandardOutput $dom -RedirectStandardError $errFile | Out-Null

$html = Get-Content $dom -Raw -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $profDir -ErrorAction SilentlyContinue
if (-not $html) { Write-Error "no DOM produced"; exit 2 }

$m = [regex]::Match($html, '<div id="HARNESS_RESULT"[^>]*>(.*?)</div>', 'Singleline')
if (-not $m.Success -or -not $m.Groups[1].Value.Trim()) {
  Write-Error "harness did not run (detail drawer never rendered)"; exit 2
}
$result = $m.Groups[1].Value.Trim()

$fails = 0; $passes = 0
foreach ($entry in ($result -split ' ;; ')) {
  if ($entry -match '^EXCEPTION:(.*)$') {
    Write-Host "[FAIL] openDatasetDetail threw: $($Matches[1])" -ForegroundColor Red
    $fails++; continue
  }
  if ($entry -match '^(?<id>[^:]+):hdr=(?<hdr>\w+),rows=(?<rows>\d+),(?<msg>\w+)$') {
    $id = $Matches.id; $hdr = $Matches.hdr; $rows = [int]$Matches.rows; $msg = $Matches.msg
    # pavel_wes_saidkarimova legitimately has 0 processed samples (raw FASTQ only)
    if ($id -eq 'pavel_wes_saidkarimova') {
      if ($hdr -eq '0') { Write-Host "[PASS] $id - correctly shows 0 (raw FASTQ only)"; $passes++ }
      else { Write-Host "[FAIL] $id - expected 0, got $hdr" -ForegroundColor Red; $fails++ }
      continue
    }
    if ($hdr -eq 'NONE' -or [int]$hdr -eq 0) {
      Write-Host "[FAIL] $id - detail drawer reports Samples($hdr)" -ForegroundColor Red; $fails++
    } elseif ($rows -lt 2) {
      Write-Host "[FAIL] $id - header says $hdr but drawer rendered $rows table rows" -ForegroundColor Red; $fails++
    } else {
      Write-Host "[PASS] $id - Samples($hdr), $rows rows rendered"; $passes++
    }
  } else {
    Write-Host "[FAIL] unparseable harness output: $entry" -ForegroundColor Red; $fails++
  }
}

Write-Host ""
Write-Host "=== detail drawer: $passes passed, $fails failed ==="
if ($fails -gt 0) { exit 1 } else { exit 0 }
