// explorer_logic.js - all JS for ALSU Variant Explorer
// Injected by build_html.py after PANEL= data constant

const DRAGEN_URL = 'http://127.0.0.1:8765';
let dragenOk = false, shownRows = [], dragSrc = null;

const SIG_ORDER = {Pathogenic:0,'Likely Pathogenic':1,'VUS/Conflicting':2,'Likely Benign':3,Benign:4,Unknown:5};
const SIG_CLASS = {Pathogenic:'bp','Likely Pathogenic':'blp','VUS/Conflicting':'bv','Likely Benign':'bbl',Benign:'bb',Unknown:'bu'};

function csig(s) {
  if (!s) return 'Unknown';
  const l = s.toLowerCase();
  if (l.includes('pathogenic') && l.includes('likely')) return 'Likely Pathogenic';
  if (l.includes('pathogenic')) return 'Pathogenic';
  if (l.includes('benign') && l.includes('likely')) return 'Likely Benign';
  if (l.includes('benign')) return 'Benign';
  if (l.includes('uncertain') || l.includes('conflict')) return 'VUS/Conflicting';
  return 'Unknown';
}

function pct(f) {
  if (f == null || isNaN(f)) return '—';
  if (f === 0) return '0%';
  if (f < 0.0001) return (f*100).toExponential(2) + '%';
  return (f*100).toFixed(4) + '%';
}
function bw(f) { return f > 0 ? Math.max(2, Math.min(80, Math.log10(f*100+0.001)/Math.log10(101)*80)) : 0; }
function dc(d) { return d == null || isNaN(d) ? 'dno' : d > 0.005 ? 'dup' : d < -0.005 ? 'ddn' : 'dno'; }
function ds(d) { if (d == null || isNaN(d)) return '—'; return (d >= 0 ? '+' : '') + (d*100).toFixed(3) + '%'; }
function r2c(r) { if (r == null || isNaN(r)) return 'r2n'; return r >= 0.8 ? 'r2g' : r >= 0.4 ? 'r2m' : 'r2b'; }

// ── Server health check ───────────────────────────────────────────────────────
async function checkServer(verbose) {
  const dot = document.getElementById('sdot'), lbl = document.getElementById('slbl');
  dot.className = 'dot chk'; lbl.textContent = 'Checking...';
  try {
    const r = await fetch(DRAGEN_URL + '/api/health', { signal: AbortSignal.timeout(3000) });
    const d = await r.json();
    dragenOk = true; dot.className = 'dot ok';
    lbl.textContent = 'DRAGEN ' + d.server_time.slice(11,16) + ' | ' + d.panel_variants + ' variants' +
      (d.full_table_loaded ? ' | full table ready' : ' | full table not loaded');
  } catch(e) {
    dragenOk = false; dot.className = 'dot err';
    lbl.textContent = 'DRAGEN offline — embedded data only';
    if (verbose) document.getElementById('st').innerHTML =
      '<b>To enable live UZB lookup:</b> (1) Start <code>uzb_freq_server.py</code> on DRAGEN, ' +
      '(2) add port to plink tunnel: <code>-L 8765:localhost:8765</code>';
  }
}

// ── External API calls ────────────────────────────────────────────────────────
async function apiGnomad(rsid) {
  if (!document.getElementById('cg').checked) return null;
  const q = `{variant(rsid:"${rsid}",dataset:gnomad_r4){chrom pos ref alt genome{ac an af populations{id af}}}}`;
  try {
    const r = await fetch('https://gnomad.broadinstitute.org/api', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q})
    });
    const d = await r.json(); let v = d?.data?.variant;
    if (Array.isArray(v)) v = v[0]; return v || null;
  } catch { return null; }
}

async function apiClinvar(rsid) {
  if (!document.getElementById('cc').checked) return null;
  try {
    const s = await fetch(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&term=${rsid}[rs]&retmode=json`);
    const sd = await s.json(); const ids = sd?.esearchresult?.idlist || [];
    if (!ids.length) return null;
    const r = await fetch(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=clinvar&id=${ids[0]}&retmode=json`);
    const d = await r.json(); const rec = d?.result?.[ids[0]];
    return rec ? {
      clinsig: rec.clinical_significance?.description || '',
      review: rec.clinical_significance?.review_status || '',
      conditions: (rec.trait_set||[]).map(t => t.trait_name).slice(0,3).join('; '),
      title: rec.title || '', var_id: ids[0], gene: rec.genes?.[0]?.symbol || ''
    } : null;
  } catch { return null; }
}

async function api1KG(rsid, targetAlt) {
  if (!document.getElementById('c1').checked) return null;
  try {
    const r = await fetch(`https://rest.ensembl.org/variation/human/${rsid}?pops=1`, {
      headers: {'Content-Type': 'application/json', 'Accept': 'application/json'}
    });
    const d = await r.json(); if (!d?.populations) return null;
    const SP = new Set(['AFR','AMR','EAS','EUR','SAS']); const out = {};
    d.populations.forEach(p => {
      const pop = p.population?.replace('1000GENOMES:phase_3:','').toUpperCase();
      if (!SP.has(pop)) return;
      // Pick target ALT allele; otherwise pick minor allele (lower freq = pathogenic allele)
      if (!out[pop] || (targetAlt && p.allele === targetAlt) ||
          (!targetAlt && p.frequency < (out[pop]?.f ?? 1)))
        out[pop] = { f: p.frequency, a: p.allele };
    });
    return out;
  } catch { return null; }
}

async function apiDragen(rsid) {
  if (!dragenOk || !document.getElementById('cd').checked) return null;
  try {
    const r = await fetch(DRAGEN_URL + '/api/uzb?rsid=' + rsid, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

// ── Build table row pair (main + expand) ──────────────────────────────────────
function mkRow(d, ex) {
  ex = ex || {};
  const gn = ex.gn || null, cv = ex.cv || null, kg = ex.kg || null, dr = ex.dr || null;

  const gene     = d.gene || cv?.gene || '';
  const rsid     = d.rsID || '';
  const clinsig  = d.clinvar_sig || cv?.clinsig || '';
  const sc       = csig(clinsig);
  const cpic     = d.cpic_level && d.cpic_level !== 'N/A' ? d.cpic_level : '';
  const cpic_drug = d.cpic_drug && d.cpic_drug !== 'N/A' ? d.cpic_drug.split(';')[0].trim() : '';
  const star     = d.star_allele && d.star_allele !== 'N/A' ? d.star_allele : '';
  const is_proxy = d.allele_type_flag === 'INDEL_PROXY';
  const r2       = d.R2 != null ? d.R2 : null;

  // gnomAD populations (all ALT allele freq)
  const gPops = {};
  if (gn?.genome?.populations) gn.genome.populations.forEach(p => gPops[p.id.toUpperCase()] = p.af);

  // UZB AF: prefer live DRAGEN if available for non-panel rsIDs
  let uzb_af = d.UZB_AF_final, live_tag = false;
  if (dr?.data && dr.source === 'full_table') { uzb_af = dr.data.UZB_AF; live_tag = true; }

  const nfe   = gPops['NFE'] ?? gPops['EUR'] ?? d.gnomad_NFE;
  const sas   = gPops['SAS'] ?? d.gnomad_SAS;
  const delta = uzb_af != null && nfe != null ? uzb_af - nfe : (d.delta_final_NFE ?? null);
  const matched = d.source && d.source !== 'NOT_FOUND';

  // ── Main row ──
  const tr = document.createElement('tr');
  tr.className = 'dr'; tr.setAttribute('draggable', 'true');
  tr.innerHTML =
    '<td><span class="dh">&#8286;</span></td>' +
    '<td><input type="checkbox" class="rcb" onchange="onSel()"></td>' +
    '<td style="font-size:10px;color:#6b7280">' + (d.panel || '') + '</td>' +
    '<td><strong>' + (gene || '&mdash;') + '</strong>' + (star ? ' <span style="font-size:10px;color:#7c3aed">' + star + '</span>' : '') + '</td>' +
    '<td class="mn"><a href="https://www.ncbi.nlm.nih.gov/snp/' + rsid + '" target="_blank" onclick="event.stopPropagation()">' + rsid + '</a></td>' +
    '<td>' + (clinsig ? '<span class="bdg ' + SIG_CLASS[sc] + '">' + clinsig + '</span>' : '<span style="color:#d1d5db">&mdash;</span>') + '</td>' +
    '<td>' + (uzb_af != null
      ? '<span class="fbi" style="width:' + bw(uzb_af) + 'px;background:#16a34a"></span>' + pct(uzb_af) + (live_tag ? '<span class="live-b">LIVE</span>' : '')
      : (matched ? '<span style="color:#9ca3af;font-size:11px">low conf</span>' : '<span style="color:#e5e7eb">&mdash;</span>')) + '</td>' +
    '<td class="mn ' + dc(delta) + '" style="font-size:11px;font-weight:600">' + ds(delta) + '</td>' +
    '<td>' + (nfe != null ? '<span class="fbi" style="width:' + bw(nfe) + 'px;background:#2563eb"></span>' + pct(nfe) : '&mdash;') + '</td>' +
    '<td>' + (sas != null ? pct(sas) : '&mdash;') + '</td>' +
    '<td class="mn ' + r2c(r2) + '">' + (r2 != null ? r2.toFixed(3) : '&mdash;') + '</td>' +
    '<td>' + (cpic ? '<span class="cpic-b">CPIC ' + cpic + '</span>' : '') +
      (cpic_drug ? ' <span style="font-size:10px;color:#6b7280">' + cpic_drug + '</span>' : '') + '</td>' +
    '<td>' + (is_proxy ? '<span class="bdg bpr">PROXY</span>' : '') + '</td>';

  // ── Expand row ──
  const exp = document.createElement('tr'); exp.className = 'er';
  const etd = document.createElement('td'); etd.colSpan = 13;
  const ec  = document.createElement('div'); ec.className = 'ec';

  let warn = '';
  if (is_proxy) warn =
    '<div class="wb"><strong>&#9888; Indel Proxy Warning</strong>' +
    'The panel entry for <b>' + rsid + '</b> is an indel (<b>' + (d.hgvs_c || '?') + '</b>), ' +
    'but the matched imputed variant (' + (d.ref||'?') + '&gt;' + (d.alt||'?') + ') is a SNP. ' +
    'The UZB frequency shown reflects a nearby tagging SNP &mdash; NOT the indel. ' +
    'Do not use for clinical interpretation without direct sequencing.</div>';

  const freqs = [
    ['UZB (imputed)',  uzb_af, '#16a34a'],
    ['gnomAD global',  gn?.genome?.af ?? d.gnomad_global, '#2563eb'],
    ['gnomAD NFE/EUR', nfe, '#2563eb'],
    ['gnomAD SAS',     sas, '#9333ea'],
    ['gnomAD EAS',     gPops['EAS'] ?? d.gnomad_EAS, '#db2777'],
    ['gnomAD AFR',     gPops['AFR'] ?? d.gnomad_AFR, '#d97706'],
    ['gnomAD AMR',     gPops['AMR'] ?? d.gnomad_AMR, '#0891b2'],
    ['gnomAD ASJ',     d.gnomad_ASJ, '#6366f1'],
    ['gnomAD FIN',     d.gnomad_FIN, '#06b6d4'],
    ['gnomAD MID',     gPops['MID'] ?? d.gnomad_MID, '#8b5cf6'],
  ];
  if (kg) Object.entries(kg).forEach(([p, v]) => freqs.push(['1KG ' + p, v.f, '#78716c']));

  const fh = freqs.filter(([, f]) => f != null && !isNaN(f)).map(([l, f, c]) => {
    const dd = uzb_af != null ? uzb_af - f : null;
    return '<div class="fr">' +
      '<span class="flb">' + l + '</span>' +
      '<div class="fbw"><div class="fb2" style="width:' + bw(f) + '%;background:' + c + '"></div></div>' +
      '<span class="fv">' + pct(f) + '</span>' +
      (dd != null ? '<span class="fd ' + dc(dd) + '">' + ds(dd) + '</span>' : '') +
      '</div>';
  }).join('');

  const meta = [
    d.hgvs_c   ? '<div class="mi"><b>HGVS c.:</b> ' + d.hgvs_c + '</div>' : '',
    d.hgvs_p   ? '<div class="mi"><b>HGVS p.:</b> ' + d.hgvs_p + '</div>' : '',
    d.moi      ? '<div class="mi"><b>Inheritance:</b> ' + d.moi + '</div>' : '',
    d.pheno    ? '<div class="mi"><b>Phenotype:</b> ' + d.pheno + '</div>' : '',
    (d.clinvar_id && d.clinvar_id !== 'None') ?
      '<div class="mi"><b>ClinVar:</b> <a href="https://www.ncbi.nlm.nih.gov/clinvar/variation/' + d.clinvar_id + '" target="_blank" onclick="event.stopPropagation()">' + d.clinvar_id + '</a> (' + (d.clinvar_stars||'?') + ' stars)</div>' : '',
    cv?.conditions ? '<div class="mi"><b>API conditions:</b> ' + cv.conditions + '</div>' : '',
    d.cpic_drug && d.cpic_drug !== 'N/A' ? '<div class="mi"><b>CPIC drugs:</b> ' + d.cpic_drug + '</div>' : '',
    d.notes && d.notes !== 'nan' ? '<div class="mi"><b>Notes:</b> <span style="color:#6b7280">' + d.notes.substring(0, 160) + '</span></div>' : '',
    '<div class="mi"><b>R&#178;:</b> <span class="' + r2c(r2) + '">' + (r2 != null ? r2.toFixed(4) : '&mdash;') + '</span> &nbsp; ' +
      '<b>Conf:</b> ' + (d.confidence || '&mdash;') + ' &nbsp; <b>Source:</b> ' + (d.source || '&mdash;') + '</div>',
    '<div class="mi"><b>Allele flag:</b> ' + (d.allele_type_flag || '&mdash;') + ' &nbsp; <b>Match:</b> ' + (d.match_method || '&mdash;') + '</div>',
    (dr?.data?.UZB_N) ? '<div class="mi"><b>UZB N (alleles typed):</b> ' + dr.data.UZB_N + '</div>' : '',
  ].filter(Boolean).join('');

  const links = [
    '<a class="el" href="https://gnomad.broadinstitute.org/variant/' + rsid + '" target="_blank" onclick="event.stopPropagation()">gnomAD</a>',
    '<a class="el" href="https://www.ncbi.nlm.nih.gov/snp/' + rsid + '" target="_blank" onclick="event.stopPropagation()">dbSNP</a>',
    (d.clinvar_id && d.clinvar_id !== 'None') ? '<a class="el" href="https://www.ncbi.nlm.nih.gov/clinvar/variation/' + d.clinvar_id + '" target="_blank" onclick="event.stopPropagation()">ClinVar</a>' : '',
    '<a class="el" href="https://www.ensembl.org/Homo_sapiens/Variation/Population?v=' + rsid + '" target="_blank" onclick="event.stopPropagation()">1000G</a>',
    '<a class="el" href="https://varsome.com/variant/hg38/' + rsid + '" target="_blank" onclick="event.stopPropagation()">VarSome</a>',
    cpic ? '<a class="el" href="https://cpicpgx.org/" target="_blank" onclick="event.stopPropagation()">CPIC</a>' : '',
  ].filter(Boolean).join('');

  ec.innerHTML = warn +
    '<div class="eg">' +
    '<div class="es"><h4>All Population Frequencies (ALT allele)</h4>' + (fh || '<span style="color:#9ca3af;font-size:12px">No data</span>') + '</div>' +
    '<div class="es"><h4>Variant Details</h4>' + meta + '</div>' +
    '</div><div class="lr">' + links + '</div>';

  etd.appendChild(ec); exp.appendChild(etd);

  tr.addEventListener('click', e => {
    if (e.target.closest('a') || e.target.tagName === 'INPUT' || e.target.closest('.dh')) return;
    ec.classList.toggle('open');
    // Lazy-fetch external data on first expand
    if (ec.classList.contains('open') && !tr.dataset.enriched) {
      tr.dataset.enriched = '1';
      enrichRow(tr, d, ec, { gn, cv, kg, dr });
    }
  });

  // Drag & drop reorder
  tr.addEventListener('dragstart', e => { dragSrc = tr; tr.classList.add('dragging'); e.dataTransfer.effectAllowed = 'move'; });
  tr.addEventListener('dragend',   () => { tr.classList.remove('dragging'); document.querySelectorAll('.drag-over').forEach(x => x.classList.remove('drag-over')); });
  tr.addEventListener('dragover',  e => { e.preventDefault(); if (tr !== dragSrc) tr.classList.add('drag-over'); });
  tr.addEventListener('dragleave', () => tr.classList.remove('drag-over'));
  tr.addEventListener('drop', e => {
    e.preventDefault(); tr.classList.remove('drag-over');
    if (!dragSrc || dragSrc === tr) return;
    const tb = document.getElementById('tb'), rows = [...tb.children];
    const si = rows.indexOf(dragSrc), se = rows[si+1], di = rows.indexOf(tr), de = rows[di+1];
    if (di > si) { tb.insertBefore(se, de?.nextSibling || null); tb.insertBefore(dragSrc, se); }
    else { tb.insertBefore(dragSrc, tr); tb.insertBefore(se, dragSrc.nextSibling); }
  });

  return { tr, exp, data: { rsID: d.rsID, gene, panel: d.panel, sc, chr_pos: d.chr_pos, UZB_AF_final: uzb_af, delta_final_NFE: delta, R2: r2, clinvar_sig: clinsig } };
}

// Lazy API enrichment on expand
async function enrichRow(tr, d, ec, existing) {
  const rsid = d.rsID;
  const spinner = document.createElement('div');
  spinner.style = 'font-size:11px;color:#6b7280;margin-top:6px';
  spinner.textContent = 'Fetching live data...';
  ec.appendChild(spinner);

  const [r1, r2, r3, r4] = await Promise.allSettled([
    existing.gn ? Promise.resolve(existing.gn) : apiGnomad(rsid),
    existing.cv ? Promise.resolve(existing.cv) : apiClinvar(rsid),
    existing.kg ? Promise.resolve(existing.kg) : api1KG(rsid, d.alt),
    existing.dr ? Promise.resolve(existing.dr) : apiDragen(rsid),
  ]);
  const ex = {
    gn: r1.status === 'fulfilled' ? r1.value : null,
    cv: r2.status === 'fulfilled' ? r2.value : null,
    kg: r3.status === 'fulfilled' ? r3.value : null,
    dr: r4.status === 'fulfilled' ? r4.value : null,
  };

  // Rebuild expand content with enriched data
  const merged = { ...d };
  if (ex.cv) { merged.gene = ex.cv.gene || merged.gene; merged.clinvar_sig = ex.cv.clinsig; }
  if (ex.dr?.data && ex.dr.source !== 'not_found') {
    const dd = ex.dr.data;
    merged.UZB_AF_final = dd.UZB_AF; merged.R2 = dd.R2;
    merged.confidence = dd.confidence; merged.source = dd.source;
  }
  const { tr: newTr } = mkRow(merged, ex);
  const newExp = newTr.nextSibling;
  // Replace existing expand content
  ec.innerHTML = newExp ? newExp.querySelector('.ec').innerHTML : ec.innerHTML;
  ec.classList.add('open');
  spinner.remove();
  // Update main row cells (UZB AF may have changed)
  if (ex.dr?.data?.UZB_AF != null) {
    const cells = tr.querySelectorAll('td');
    if (cells[6]) cells[6].innerHTML = '<span class="fbi" style="width:' + bw(ex.dr.data.UZB_AF) + 'px;background:#16a34a"></span>' + pct(ex.dr.data.UZB_AF) + '<span class="live-b">LIVE</span>';
  }
}

// ── Filter ────────────────────────────────────────────────────────────────────
function applyFilter() {
  const pan = document.getElementById('fp').value;
  const sig = document.getElementById('fs').value;
  const mat = document.getElementById('fm').value;
  const filtered = PANEL.filter(d => {
    if (pan && d.panel !== pan) return false;
    if (sig && !(d.clinvar_sig || '').includes(sig)) return false;
    if (mat === 'matched' && d.source === 'NOT_FOUND') return false;
    if (mat === 'snp_ok' && d.allele_type_flag !== 'SNP_OK') return false;
    if (mat === 'hi_r2' && (d.R2 == null || d.R2 < 0.8)) return false;
    return true;
  });
  document.getElementById('tb').innerHTML = ''; shownRows = [];
  filtered.forEach(d => {
    const v = mkRow(d, {});
    shownRows.push(v);
    document.getElementById('tb').appendChild(v.tr);
    document.getElementById('tb').appendChild(v.exp);
  });
  document.getElementById('st').textContent =
    `Showing ${filtered.length} of ${PANEL.length} variants. Click row to expand (fetches live data). Use search to query any rsID.`;
}

// ── Search / add arbitrary rsID ───────────────────────────────────────────────
async function addQuery() {
  const raw = document.getElementById('ri').value.trim();
  if (!raw) return;
  const rsids = raw.split(/[\s,;]+/).map(s => s.trim()).filter(s => s.startsWith('rs'));
  if (!rsids.length) { document.getElementById('st').textContent = 'Enter valid rsIDs (starting with rs...)'; return; }
  const btn = document.querySelector('.btn-p'); btn.disabled = true;
  document.getElementById('st').innerHTML = `Querying <span class="hi">${rsids.join(', ')}</span>...`;
  for (const rsid of rsids) {
    const base = PANEL.find(d => d.rsID === rsid) || { rsID: rsid, gene: '', panel: 'Query', clinvar_sig: '', source: '', allele_type_flag: '' };
    const [r1, r2, r3, r4] = await Promise.allSettled([apiGnomad(rsid), apiClinvar(rsid), api1KG(rsid, base.alt), apiDragen(rsid)]);
    const ex = { gn: r1.value, cv: r2.value, kg: r3.value, dr: r4.value };
    const merged = { ...base };
    if (ex.cv) { merged.gene = ex.cv.gene || merged.gene; merged.clinvar_sig = ex.cv.clinsig; }
    if (ex.dr?.data && ex.dr.source !== 'not_found') {
      merged.UZB_AF_final = ex.dr.data.UZB_AF; merged.R2 = ex.dr.data.R2;
      merged.confidence = ex.dr.data.confidence; merged.source = ex.dr.data.source;
    }
    const v = mkRow(merged, ex);
    shownRows.push(v);
    document.getElementById('tb').appendChild(v.tr);
    document.getElementById('tb').appendChild(v.exp);
  }
  document.getElementById('st').textContent = 'Done.';
  document.getElementById('ri').value = ''; btn.disabled = false;
}

// ── Sort ──────────────────────────────────────────────────────────────────────
function sortBy(col) {
  const sd = document.getElementById('sdir');
  if (document.getElementById('scol').value === col) sd.value = sd.value === 'asc' ? 'desc' : 'asc';
  document.getElementById('scol').value = col; applySort();
}
function applySort() {
  const col = document.getElementById('scol').value, dir = document.getElementById('sdir').value;
  const tb = document.getElementById('tb'), rows = [...tb.children];
  const pairs = []; for (let i = 0; i < rows.length; i += 2) pairs.push([rows[i], rows[i+1]]);
  pairs.sort((a, b) => {
    const va = shownRows.find(v => v.tr === a[0])?.data;
    const vb = shownRows.find(v => v.tr === b[0])?.data;
    if (!va || !vb) return 0;
    let aa, bb;
    if      (col === 'gene')   { aa = va.gene || ''; bb = vb.gene || ''; }
    else if (col === 'panel')  { aa = va.panel || ''; bb = vb.panel || ''; }
    else if (col === 'rsid')   { aa = va.rsID || ''; bb = vb.rsID || ''; }
    else if (col === 'chr')    { aa = parseInt(va.chr_pos?.split(':')?.[1]) || 0; bb = parseInt(vb.chr_pos?.split(':')?.[1]) || 0; }
    else if (col === 'clinsig'){ aa = SIG_ORDER[csig(va.clinvar_sig)] ?? 9; bb = SIG_ORDER[csig(vb.clinvar_sig)] ?? 9; }
    else if (col === 'uzb')    { aa = va.UZB_AF_final ?? -1; bb = vb.UZB_AF_final ?? -1; }
    else if (col === 'delta')  { aa = va.delta_final_NFE ?? -99; bb = vb.delta_final_NFE ?? -99; }
    else if (col === 'r2')     { aa = va.R2 ?? -1; bb = vb.R2 ?? -1; }
    else return 0;
    const c = typeof aa === 'string' ? aa.localeCompare(bb) : aa - bb;
    return dir === 'asc' ? c : -c;
  });
  pairs.forEach(([m, e]) => { tb.appendChild(m); tb.appendChild(e); });
}

// ── Selection ─────────────────────────────────────────────────────────────────
function onSel() {
  const n = [...document.querySelectorAll('.rcb')].filter(c => c.checked).length;
  document.getElementById('sc2').textContent = n ? n + ' selected' : '';
  document.getElementById('bdel').style.display = n ? '' : 'none';
  document.querySelectorAll('.dr').forEach(tr => tr.classList.toggle('sel', !!tr.querySelector('.rcb')?.checked));
}
function selAll()  { document.querySelectorAll('.rcb').forEach(c => c.checked = true);  onSel(); }
function selNone() { document.querySelectorAll('.rcb').forEach(c => c.checked = false); onSel(); }
function toggleAll(cb) { document.querySelectorAll('.rcb').forEach(c => c.checked = cb.checked); onSel(); }
function deleteSel() {
  document.querySelectorAll('.dr').forEach(tr => {
    if (tr.querySelector('.rcb')?.checked) {
      const n = tr.nextSibling; tr.remove();
      if (n?.classList.contains('er')) n.remove();
    }
  });
  shownRows = shownRows.filter(v => v.tr.isConnected); onSel();
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.querySelectorAll('.cp').forEach(p =>
  p.querySelector('input').addEventListener('change', function() { p.classList.toggle('on', this.checked); })
);
window.addEventListener('load', () => { checkServer(false); applyFilter(); });
