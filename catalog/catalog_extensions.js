/* ===== additions to the original data-sources page =====
   Style matches the original: plain functions, var, string concatenation. */

var SHARE_BASE = "__SHARE_BASE__";   /* stamped at build: "share/" (LAN), absolute URL (standalone), "" (none) */
var BUILD = "__BUILD_ID__";
var CATALOG = null, PANEL = null, SAMPLES = null;

function shareLink(id, label){ return SHARE_BASE ? SHARE_BASE + id + '/' + label + '/' : null; }
function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function fmtGB(b){ if (b == null) return ''; var g = b / 1e9; return g >= 100 ? Math.round(g) + ' GB' : g >= 10 ? g.toFixed(1) + ' GB' : g >= 1 ? g.toFixed(2) + ' GB' : (b/1e6).toFixed(0) + ' MB'; }
function fmtN(n){ return n == null ? '' : String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

/* ---------- map catalog.json -> the original row shape ---------- */
function techOf(ds){ return ds.type === 'gsa' ? 'array' : ds.type === 'targeted_panel' ? 'panel' : ds.type; }

function headline(ds){
  var s = ds.live_scan || {};
  if (s.sample_count_including_sub_paths != null) return s.sample_count_including_sub_paths;
  if (s.sample_count != null) return s.sample_count;
  return 0;
}
function samplesLabel(ds){
  var s = ds.live_scan || {}, n = headline(ds);
  if (!n && s.raw_fastq_samples_detected) return s.raw_fastq_samples_detected + ' raw, unprocessed';
  var stage = s.inferred_stage || s.status || '';
  var tag = stage.indexOf('post_imputation') >= 0 ? 'post-QC, imputed'
          : stage === 'plink_fileset_present_no_full_qc' ? 'variant-QC only'
          : stage === 'complete' ? 'processed'
          : stage === 'partial' ? 'partially processed' : '';
  return fmtN(n) + (tag ? ' (' + tag + ')' : '');
}
function statusWord(ds){
  var s = ds.live_scan || {}; if (s.error) return 'error';
  var st = s.status || s.inferred_stage || '';
  if (st === 'complete' || st === 'post_imputation_qc_complete') return 'complete';
  if (st === 'partial' || st === 'plink_fileset_present_no_full_qc') return 'partial';
  return 'pending';
}
function statusHtml(d){
  var w = d.status, cls = w === 'complete' ? 'd-ok' : 'd-pend';
  var label = w === 'complete' ? 'Complete' : w === 'partial' ? 'Partial' : w === 'error' ? 'Scan error' : 'Pending';
  var note = d.live && d.live.status_note ? ' <span class="mini" title="' + esc(d.live.status_note) + '">*</span>' : '';
  return '<span class="dot ' + cls + '"></span>' + label + note;
}

function toRow(ds){
  var cur = ds.curated || {}, s = ds.live_scan || {};
  var tl = cur.tech_label || (ds.type === 'gsa' ? 'GSA' : ds.type === 'targeted_panel' ? (ds.panel || 'panel') : ds.type.toUpperCase());
  /* derived facts win where curated conflicts; both are shown in the expanded row */
  if (ds.type === 'targeted_panel') tl = (ds.panel || 'targeted panel');
  return {
    id: ds.id, date: ds.date, name: ds.name, desc: ds.description || '',
    n: headline(ds), nl: samplesLabel(ds),
    tech: techOf(ds), tl: tl,
    path: ds.root_path, gb: (s.size_total_bytes || 0) / 1e9, sl: fmtGB(s.size_total_bytes),
    status: statusWord(ds),
    kv: cur.kv || {}, tree: cur.tree || '', note: cur.note || '',
    exploreUrl: null,
    live: s, ds: ds
  };
}

/* ---------- data-aware sections for the expanded row ---------- */
function sec(title, hint, body){
  return '<div class="dp-sec gs"><h4>' + title + '<span class="derived">derived</span></h4>'
       + (hint ? '<div class="gs-hint">' + hint + '</div>' : '') + body + '</div>';
}
function tbl(head, rows){
  return '<table><tr>' + head.map(function(h){ return '<th>' + h + '</th>'; }).join('') + '</tr>'
       + rows.map(function(r){ return '<tr>' + r.map(function(c){ return '<td' + (typeof c === 'number' ? ' class="r"' : '') + '>' + c + '</td>'; }).join('') + '</tr>'; }).join('')
       + '</table>';
}

function gatedSections(d){
  var ds = d.ds, s = d.live, has = s.has || {}, out = '';

  /* curated vs derived conflicts, if the registry flagged any */
  var cf = (ds.curated || {}).conflicts || {};
  Object.keys(cf).forEach(function(k){ out += '<div class="conflict"><b>' + esc(k) + ':</b> ' + esc(cf[k]) + '</div>'; });

  /* what exists - the capability summary */
  var caps = [
    ['per_sample','per-sample records'], ['raw_reads','raw data'], ['allele_freqs','allele frequencies'],
    ['panel_variants','panel variant calls'], ['panel_coverage','array coverage of panel'],
    ['sample_qc','sample QC'], ['imputation','imputation'], ['popgen','population genetics'],
    ['sub_cohorts','sub-cohorts'], ['clinical_reports','clinical reports'], ['coverage_flags','coverage metrics']
  ].filter(function(c){ return has[c[0]]; }).map(function(c){ return '<span class="chip">' + c[1] + '</span>'; });
  out += sec('What this dataset contains', 'Each chip corresponds to files actually found on disk. Sections below appear only for what exists.', caps.join('') || '<span class="mini">nothing processed yet</span>');

  /* size breakdown */
  var sz = s.size_bytes || {};
  if (Object.keys(sz).length) {
    out += sec('Size on disk', 'du -sb per directory; nested directories are not added twice.',
      tbl(['Directory','Size'], Object.keys(sz).map(function(k){ return [k, fmtGB(sz[k])]; })
        .concat([['<b>total</b>', '<b>' + fmtGB(s.size_total_bytes) + '</b>']])));
  }

  /* sub-cohorts */
  if (has.sub_cohorts && s.sub_path_scans) {
    out += sec('Sub-cohorts', 'Counted separately; the headline sample count is their sum.',
      tbl(['Cohort','Samples','Status','Path'], Object.keys(s.sub_path_scans).map(function(k){
        var sub = s.sub_path_scans[k]; return [k, sub.sample_count || 0, sub.status || '', '<span class="mini">' + esc(sub.root_path) + '</span>']; })));
  }
  if (s.aux_path_scans) {
    out += sec('Related directories', 'Describe the same samples (annotations, re-runs). Not counted as samples.',
      tbl(['Directory','Files','Path'], Object.keys(s.aux_path_scans).map(function(k){
        var a = s.aux_path_scans[k]; return [k, a.file_count || 0, '<span class="mini">' + esc(a.root_path) + '</span>']; })));
  }

  /* per-sample */
  if (has.per_sample) {
    var rows = [];
    Object.keys(s.samples || {}).forEach(function(sid){ rows.push([sid, null, s.samples[sid]]); });
    Object.keys(s.sub_path_scans || {}).forEach(function(k){ Object.keys(s.sub_path_scans[k].samples || {}).forEach(function(sid){ rows.push([sid, k, s.sub_path_scans[k].samples[sid]]); }); });
    var LIMIT = 40, shown = rows.slice(0, LIMIT), hasSub = rows.some(function(r){ return r[1]; });
    var isPanelZip = shown.some(function(r){ return r[2].convention === 'external_panel_zip'; });
    var head = ['Sample'].concat(hasSub ? ['Cohort'] : []).concat(isPanelZip ? ['Variants','Low-cov regions','Report'] : ['Files','Convention']).concat(['Status']);
    out += sec('Samples (' + rows.length + ')', rows.length > LIMIT ? 'Showing first ' + LIMIT + '. Full list: catalog.json.' : '',
      tbl(head, shown.map(function(r){
        var sid = r[0], sub = r[1], i = r[2];
        var cells = [ '<span style="font-family:monospace">' + esc(sid) + '</span>' ];
        if (hasSub) cells.push(sub || '');
        if (isPanelZip) cells.push(i.variants != null ? i.variants : '', i.flagged_low_coverage_regions != null ? i.flagged_low_coverage_regions : '', i.qa_report_pdf ? 'PDF' : '');
        else cells.push(i.file_count != null ? i.file_count : '—', esc(i.convention || ''));
        cells.push(i.complete ? '<span class="dot d-ok"></span>ok' : '<span class="dot d-pend"></span>incomplete');
        return cells; })));
  } else if (s.raw_fastq_samples_detected) {
    out += sec('Samples', '', '<span class="mini">' + s.raw_fastq_samples_detected + ' raw FASTQ sample(s) present; nothing has been run through a pipeline yet.</span>');
  }

  /* array-specific */
  if (ds.type === 'gsa' && s.best_fileset) {
    var stage = (s.inferred_stage || '').replace(/_/g, ' ');
    out += sec('Array processing', '',
      tbl(['Fileset','Stage','Sample QC files'], [[ '<span class="mini">' + esc(s.best_fileset) + '</span>', stage, s.qc_side_files_found || 0 ]]));
  }
  if (has.panel_coverage && PANEL && PANEL.gsa_coverage && PANEL.gsa_coverage[ds.id]) {
    var cov = PANEL.gsa_coverage[ds.id];
    var genes = cov.genes_covered || [];
    out += sec('Cardiomyopathy panel coverage on this array', cov.panel_snps_on_chip + ' SNPs on the chip fall inside the 26 panel genes' + (cov.snps_with_maf ? '; ' + cov.snps_with_maf + ' with a real allele frequency' : '') + '.',
      genes.map(function(g){ return '<span class="chip">' + esc(g) + '</span>'; }).join(''));
  }

  /* sequencing-specific */
  if (has.panel_variants && PANEL) {
    var mine = PANEL.variants.filter(function(v){ return v.datasets[ds.id] || (ds.id === 'cardio_main' && (v.datasets.cardio_main_cases || v.datasets.cardio_main_controls || v.datasets.cardio_main_transplant)); });
    var shared = mine.filter(function(v){ return Object.keys(v.datasets).length > 1; });
    var build = (PANEL.dataset_builds || {})[ds.id];
    out += sec('Cardiomyopathy panel variants', mine.length + ' variants called in the 26 panel genes' + (shared.length ? '; ' + shared.length + ' also seen in another cohort' : '') + '.'
      + (build ? ' Native build ' + build.source_build + ', lifted to ' + build.lifted_to + ' (' + (build.positions_unmapped_by_liftover || 0) + ' unmapped).' : ''),
      '<a href="#" onclick="showView(\'panel\');document.getElementById(\'pnQ\').value=\'\';return false;" class="mini">open the focal-panel view →</a>');
  }
  if (has.clinical_reports) {
    var files = (s.cohort_level_files || []).filter(function(f){ return /pathogenic|report/i.test(f); });
    Object.keys(s.aux_path_scans || {}).forEach(function(k){ if (/annot/.test(k)) files.push(k + '/'); });
    out += sec('Clinical reports', '', files.map(function(f){ return '<span class="chip">' + esc(f) + '</span>'; }).join('') || '<span class="mini">per-sample reports present</span>');
  }
  if (has.popgen && ds.detail_url) {
    out += sec('Population genetics', '', '<a href="' + esc(ds.detail_url) + '" target="_blank" rel="noopener">' + esc(ds.detail_note || ds.detail_url) + ' →</a>');
  }
  if (s.status_note) out += '<div class="conflict">' + esc(s.status_note) + '</div>';
  if (ds.status_note) out += '<div class="conflict">' + esc(ds.status_note) + '</div>';

  /* browse */
  if (SHARE_BASE) {
    var links = [['raw data', shareLink(ds.id, 'raw')]];
    if (ds.processed_path) links.push(['processed', shareLink(ds.id, 'processed')]);
    Object.keys(ds.sub_paths || {}).forEach(function(k){ links.push([k, shareLink(ds.id, k)]); });
    out += sec('Browse on DRAGEN', 'Directory listings served over the local network.',
      '<div class="browse">' + links.map(function(l){ return '<a href="' + l[1] + '" target="_blank" rel="noopener">' + esc(l[0]) + ' →</a>'; }).join('') + '</div>');
  }
  return out;
}

/* ---------- tabs ---------- */
function showView(v){
  document.querySelectorAll('.vtab').forEach(function(t){ t.classList.toggle('active', t.getAttribute('data-view') === v); });
  document.querySelectorAll('.vview').forEach(function(x){ x.classList.toggle('active', x.id === 'vv-' + v); });
}
document.querySelectorAll('.vtab').forEach(function(t){ t.addEventListener('click', function(){ showView(t.getAttribute('data-view')); }); });

/* ---------- focal panel view ---------- */
function renderPanelView(){
  var host = document.getElementById('vv-panel'); if (!PANEL) { host.innerHTML = '<span class="mini">panel data not loaded</span>'; return; }
  var genes = []; PANEL.variants.forEach(function(v){ if (genes.indexOf(v.gene) < 0) genes.push(v.gene); }); genes.sort();
  var dsIds = []; PANEL.variants.forEach(function(v){ Object.keys(v.datasets).forEach(function(k){ if (dsIds.indexOf(k) < 0) dsIds.push(k); }); }); dsIds.sort();
  var cross = PANEL.variants.filter(function(v){ return Object.keys(v.datasets).length > 1; }).length;
  host.innerHTML =
    '<div class="mini" style="margin:6px 0 10px">' + esc(PANEL.panel) + '. Carrier counts come from <code>bcftools</code> against real indexed VCFs (and from lifted GRCh37 VCFs for the external panel). Only cohorts that have variant calls appear here.</div>'
    + '<div class="stat-row"><div><b>' + fmtN(PANEL.variants.length) + '</b><span>variants</span></div><div><b>' + fmtN(cross) + '</b><span>in ≥2 cohorts</span></div><div><b>' + dsIds.length + '</b><span>cohorts with calls</span></div></div>'
    + '<div class="sub-toolbar"><input id="pnQ" placeholder="gene, position…" oninput="renderPanelRows()">'
    + '<select id="pnGene" onchange="renderPanelRows()"><option value="">All genes</option>' + genes.map(function(g){ return '<option>' + esc(g) + '</option>'; }).join('') + '</select>'
    + '<select id="pnCross" onchange="renderPanelRows()"><option value="">All variants</option><option value="yes">Seen in ≥2 cohorts</option></select></div>'
    + '<div class="bigtbl"><table><thead><tr><th>Gene</th><th>Position (GRCh38)</th><th>Ref → Alt</th><th>Cohorts</th><th>Carriers by cohort</th><th>Lookup</th></tr></thead><tbody id="pnBody"></tbody></table></div>'
    + '<div class="mini" id="pnMore" style="margin-top:6px"></div>';
  renderPanelRows();
}
function renderPanelRows(){
  var q = (document.getElementById('pnQ').value || '').toLowerCase(), g = document.getElementById('pnGene').value, x = document.getElementById('pnCross').value;
  var list = PANEL.variants.filter(function(v){
    if (g && v.gene !== g) return false;
    if (x && Object.keys(v.datasets).length < 2) return false;
    if (q && (v.gene + ' ' + v.pos + ' ' + v.ref + ' ' + v.alt).toLowerCase().indexOf(q) < 0) return false;
    return true; });
  list.sort(function(a,b){ return Object.keys(b.datasets).length - Object.keys(a.datasets).length || a.pos - b.pos; });
  var LIMIT = 250, total = list.length; list = list.slice(0, LIMIT);
  var body = document.getElementById('pnBody'); body.innerHTML = '';
  list.forEach(function(v){
    var chr = String(v.chrom).replace(/^chr/, '');
    var cells = Object.keys(v.datasets).map(function(k){ var d = v.datasets[k]; var pct = d.carrier_frequency == null ? '?' : (d.carrier_frequency*100).toFixed(0) + '%';
      return '<span class="chip" title="' + esc((d.carriers||[]).map(function(c){ return c.sample + ':' + c.genotype; }).join(', ') + (d.carriers_truncated ? ' (+' + d.carriers_truncated + ' more)' : '')) + '">' + esc(k) + ' ' + d.carrier_count + '/' + d.cohort_size + ' (' + pct + ')</span>'; }).join('');
    var tr = document.createElement('tr');
    tr.innerHTML = '<td><b>' + esc(v.gene) + '</b></td><td style="font-family:monospace">' + esc(v.chrom) + ':' + fmtN(v.pos) + '</td><td style="font-family:monospace">' + esc(v.ref) + ' → ' + esc(v.alt) + '</td><td class="r">' + Object.keys(v.datasets).length + '</td><td>' + cells + '</td>'
      + '<td class="mini" style="white-space:nowrap"><a href="https://gnomad.broadinstitute.org/variant/' + chr + '-' + v.pos + '-' + encodeURIComponent(v.ref) + '-' + encodeURIComponent(v.alt) + '?dataset=gnomad_r4" target="_blank" rel="noopener">gnomAD</a> · <a href="https://www.ncbi.nlm.nih.gov/clinvar/?term=' + chr + '%5Bchr%5D+AND+' + v.pos + '%5Bchrpos38%5D" target="_blank" rel="noopener">ClinVar</a> · <a href="https://www.ncbi.nlm.nih.gov/snp/?term=' + chr + '%3A' + v.pos + '" target="_blank" rel="noopener">dbSNP</a></td>';
    body.appendChild(tr);
  });
  document.getElementById('pnMore').textContent = total > LIMIT ? 'Showing first ' + LIMIT + ' of ' + fmtN(total) + ' — narrow by gene or cross-cohort filter.' : fmtN(total) + ' variant' + (total === 1 ? '' : 's') + '.';
}

/* ---------- samples across runs view ---------- */
function renderSamplesView(){
  var host = document.getElementById('vv-samples'); if (!SAMPLES) { host.innerHTML = '<span class="mini">sample crosswalk not loaded</span>'; return; }
  var ov = SAMPLES.pairwise_overlap || {}, keys = Object.keys(ov);
  var dsNames = Object.keys(SAMPLES.dataset_sample_counts || {}).sort();
  host.innerHTML =
    '<div class="mini" style="margin:6px 0 10px">' + esc(SAMPLES.method_note) + '</div>'
    + '<div class="stat-row"><div><b>' + fmtN(Object.keys(SAMPLES.samples).length) + '</b><span>distinct samples</span></div><div><b>' + fmtN(SAMPLES.samples_in_multiple_datasets) + '</b><span>in ≥2 datasets</span></div></div>'
    + '<h4 style="margin:10px 0 4px">Dataset overlap</h4><div class="bigtbl"><table><thead><tr><th>Pair</th><th>Shared</th><th>% of smaller</th><th>Examples</th></tr></thead><tbody>'
    + keys.map(function(k){ var o = ov[k]; return '<tr><td><b>' + esc(k) + '</b></td><td class="r">' + o.shared_sample_count + '</td><td class="r">' + o.pct_of_smaller + '%</td><td style="font-family:monospace" class="mini">' + esc(o.examples.join(', ')) + '</td></tr>'; }).join('')
    + '</tbody></table></div>'
    + '<h4 style="margin:14px 0 4px">Per-sample run history</h4>'
    + '<div class="sub-toolbar"><input id="smQ" placeholder="sample id…" oninput="renderSampleRows()">'
    + '<select id="smMulti" onchange="renderSampleRows()"><option value="multi">Only samples in ≥2 datasets</option><option value="">All samples</option></select>'
    + '<select id="smDs" onchange="renderSampleRows()"><option value="">Any dataset</option>' + dsNames.map(function(d){ return '<option>' + esc(d) + '</option>'; }).join('') + '</select></div>'
    + '<div class="bigtbl"><table><thead><tr><th>Sample</th><th>Runs</th><th>Appears in</th></tr></thead><tbody id="smBody"></tbody></table></div><div class="mini" id="smMore" style="margin-top:6px"></div>';
  renderSampleRows();
}
function renderSampleRows(){
  var q = (document.getElementById('smQ').value || '').toLowerCase(), multi = document.getElementById('smMulti').value === 'multi', dsf = document.getElementById('smDs').value;
  var rows = Object.keys(SAMPLES.samples).filter(function(sid){ var d = SAMPLES.samples[sid].datasets, n = Object.keys(d).length;
    if (multi && n < 2) return false; if (dsf && !(dsf in d)) return false; if (q && sid.indexOf(q) < 0) return false; return true; });
  rows.sort(function(a,b){ return Object.keys(SAMPLES.samples[b].datasets).length - Object.keys(SAMPLES.samples[a].datasets).length || (a < b ? -1 : 1); });
  var LIMIT = 300, total = rows.length; rows = rows.slice(0, LIMIT);
  var body = document.getElementById('smBody'); body.innerHTML = '';
  rows.forEach(function(sid){ var d = SAMPLES.samples[sid].datasets; var tr = document.createElement('tr');
    tr.innerHTML = '<td style="font-family:monospace">' + esc(sid) + '</td><td class="r">' + Object.keys(d).length + '</td><td>' + Object.keys(d).map(function(k){ return '<span class="chip" title="' + esc(d[k].join(', ')) + '">' + esc(k) + '</span>'; }).join('') + '</td>';
    body.appendChild(tr); });
  document.getElementById('smMore').textContent = total > LIMIT ? 'Showing first ' + LIMIT + ' of ' + fmtN(total) + ' — narrow the filter.' : (total ? '' : 'No samples match.');
}

/* ---------- loader ---------- */
function onCatalogLoaded(catalog, panel, samples, failed){
  var L = document.getElementById('loadState');
  if (failed.length) { L.style.borderColor = '#dc2626'; L.innerHTML = '<b style="color:#dc2626">Could not load: ' + failed.map(function(f){ return esc(f.label); }).join(', ') + '</b><br>' + failed.map(function(f){ return '<span class="mini">' + esc(f.url) + ' — ' + esc(f.err) + '</span>'; }).join('<br>'); }
  if (panel) PANEL = panel;
  if (samples) SAMPLES = samples;
  if (catalog) {
    CATALOG = catalog;
    var h = CATALOG.host || {};
    document.getElementById('mh-host').textContent = h.hostname || '—';
    document.getElementById('mh-ip').textContent = [h.ip_lan, h.ip_tailscale].filter(Boolean).join(' / ') || '—';
    document.getElementById('mh-os').textContent = h.os || '—';
    document.getElementById('mh-dragen').textContent = h.dragen || '—';
    document.getElementById('mh-ram').textContent = h.ram_gb ? h.ram_gb + ' GB' : '—';
    document.getElementById('mh-free').textContent = h.staging_free || '—';
    var g = CATALOG.generated_at ? new Date(CATALOG.generated_at) : null;
    document.getElementById('mh-gen').textContent = g ? g.toISOString().slice(0,16).replace('T',' ') + ' UTC' : '—';
    DATA = CATALOG.datasets.map(toRow);
    vis = DATA.slice();
    applyFilters();
  }
  if (panel) renderPanelView();
  if (samples) renderSamplesView();
  if (!failed.length) L.style.display = 'none';
}
/* BOOTSTRAP-START (build_artifact.py replaces this block with inlined data) */
function grab(url, label){
  return fetch(url).then(function(r){ if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function(j){ return {ok:true, label:label, url:url, j:j}; })
    .catch(function(e){ return {ok:false, label:label, url:url, err:String(e.message || e)}; });
}
Promise.all([
  grab('catalog/catalog.json?v=' + BUILD, 'datasets'),
  grab('catalog/panel_web.json?v=' + BUILD, 'focal panel'),
  grab('catalog/samples.json?v=' + BUILD, 'samples')
]).then(function(res){
  onCatalogLoaded(res[0].ok ? res[0].j : null, res[1].ok ? res[1].j : null, res[2].ok ? res[2].j : null,
                  res.filter(function(r){ return !r.ok; }));
});
/* BOOTSTRAP-END */
