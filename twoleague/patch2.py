src = open('report_v3.html', encoding='utf-8').read()
def sub(old, new, label=''):
    global src
    if old not in src: raise SystemExit('ANCHOR NOT FOUND: ' + (label or old[:60]))
    src = src.replace(old, new, 1)

JS = r"""
/* ================= league switching =================
   PBAFFL is an auction league; Perennial Push is an 18-round snake with a
   superflex slot. They do not share a vocabulary -- dollars mean nothing in a
   snake, and "never pay up for a QB" is exactly backwards under superflex -- so
   the switch swaps the whole tab set and every panel rather than re-labelling
   one. NFL stats and Vegas are league-agnostic and stay put in both modes. */
const LG_META = {
  pbaffl: {title: 'PBAFFL — draft data',
           sub: '2026 board &amp; nine seasons of league history'},
  ppp:    {title: 'Perennial Push for Penultimacy',
           sub: '2026 superflex board &amp; five seasons of league history'}
};
let LG = 'pbaffl';
try { const s = localStorage.getItem('pbaffl_league_v1');
      if (s === 'pbaffl' || s === 'ppp') LG = s; } catch (e) {}

function applyLeague(redraw) {
  document.getElementById('hTitle').textContent = LG_META[LG].title;
  document.getElementById('hSub').innerHTML = LG_META[LG].sub;
  document.getElementById('lgSel').value = LG;
  const tabs = [...document.querySelectorAll('.tab[data-p]')];
  tabs.forEach(t => { t.hidden = !(t.dataset.lg === LG || t.dataset.lg === 'both'); });
  // keep the current tab if this league has it, otherwise fall back to its board
  const cur = tabs.find(t => t.getAttribute('aria-selected') === 'true' && !t.hidden);
  const pick = cur || tabs.find(t => !t.hidden);
  tabs.forEach(t => t.setAttribute('aria-selected', String(t === pick)));
  document.querySelectorAll('.panel').forEach(p => p.hidden = p.id !== 'p-' + pick.dataset.p);
  if (redraw) draw();
}
document.getElementById('lgSel').onchange = e => {
  LG = e.target.value;
  try { localStorage.setItem('pbaffl_league_v1', LG); } catch (err) {}
  applyLeague(true);
};

/* ================= Perennial Push renderers ================= */
const xPOS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];
const xSTREAM = p => p.pos === 'K' || p.pos === 'DEF';
let xState = {q: '', pos: '', tgt: false, arb: false, hideStream: true, season: null, pos2: ''};
const xKey = p => 'x' + p.pid;                        // namespaced so PBAFFL stars never collide
const xFmt = v => v == null ? '' : (Math.round(v * 10) / 10).toFixed(1);
const xRdPk = p => p.rd == null ? '—' : p.rd + '.' + String(p.pk).padStart(2, '0');

function xTiles() {
  const r = D2.replacement, b = D2.board;
  const arb = b.filter(p => p.gap != null && p.gap >= 24).length;
  const t = [
    ['18', 'rounds, snake', 'full PPR, superflex'],
    ['24', 'QBs start every week', '2 per team, 12 teams'],
    [D2.qbTop3, 'QBs inside rounds 1–3', 'the room takes ' + D2.qbcum[2] + ' by then'],
    [xFmt(r.QB), 'replacement QB, realized', 'vs ' + xFmt(r.RB) + ' RB / ' + xFmt(r.WR) + ' WR'],
    [arb, 'players 2+ rounds cheaper', "than ESPN's one-QB board"]
  ];
  document.getElementById('xbTiles').innerHTML = t.map(([v, k, s]) =>
    `<div class="tile"><div class="v kpi">${v}</div><div class="k">${k}` +
    (s ? `<br><span style="color:var(--muted)">${s}</span>` : '') + `</div></div>`).join('');
}

function xBoard() {
  xTiles();
  const sel = document.getElementById('xposf');
  if (sel.options.length === 1)
    xPOS.forEach(p => sel.add(new Option(p, p)));
  let rows = D2.board.slice();
  if (xState.hideStream) rows = rows.filter(p => !xSTREAM(p));
  if (xState.pos) rows = rows.filter(p => p.pos === xState.pos);
  if (xState.q) { const q = xState.q.toLowerCase(); rows = rows.filter(p => p.n.toLowerCase().includes(q)); }
  if (xState.tgt) rows = rows.filter(p => targets.has(xKey(p)));
  if (xState.arb) rows = rows.filter(p => p.gap != null && p.gap >= 24);
  const head = `<thead><tr>
    <th class="l">#</th><th class="l">Rd.Pk</th><th class="l">Player</th><th class="l">Pos</th><th class="l">Team</th>
    <th>Proj</th><th>Exp</th><th>VOR</th><th>ESPN rd</th><th>Move</th><th></th></tr></thead>`;
  const body = rows.map(p => {
    const gapRd = p.gap == null ? null : Math.round(p.gap / 12 * 10) / 10;
    const cls = (p.gap != null && p.gap >= 24) ? ' class="arb"' : (xSTREAM(p) ? ' class="stream"' : '');
    const mv = gapRd == null ? '—'
      : gapRd >= 0.8 ? `<span class="up">${gapRd.toFixed(1)} rd earlier</span>`
      : gapRd <= -0.8 ? `<span class="dn">${Math.abs(gapRd).toFixed(1)} rd later</span>`
      : '<span style="color:var(--muted)">—</span>';
    return `<tr${cls}>
      <td class="l kpi" style="color:var(--muted)">${p.rank == null ? '—' : p.rank}</td>
      <td class="l" style="font-weight:650">${xRdPk(p)}</td>
      <td class="l">${p.n}</td>
      <td class="l"><span class="pos" style="background:var(${POSC[p.pos] || '--muted'})">${p.pos}${p.prank}</span></td>
      <td class="l" style="color:var(--ink2)">${p.tm}</td>
      <td style="color:var(--ink2)">${xFmt(p.prj)}</td>
      <td>${xFmt(p.exp)}</td>
      <td>${p.vor == null ? '<span style="color:var(--muted)">stream</span>' : (p.vor > 0 ? '+' : '') + xFmt(p.vor)}</td>
      <td>${p.espn == null ? '—' : Math.floor((p.espn - 1) / 12) + 1}</td>
      <td>${mv}</td>
      <td class="l">${starHtml(xKey(p))}</td></tr>`;
  }).join('');
  const t = document.getElementById('xboardT');
  t.innerHTML = head + '<tbody>' + (body || '<tr><td colspan="11" class="l" style="color:var(--muted)">no players match these filters</td></tr>') + '</tbody>';
  bindStars(t);
  document.getElementById('xbLeg').innerHTML =
    '<span><i style="background:color-mix(in srgb,var(--s1) 40%,transparent)"></i>2+ rounds cheaper than ESPN has him</span>' +
    xPOS.map(p => `<span><i style="background:var(${POSC[p]})"></i>${p}</span>`).join('') +
    `<span style="color:var(--muted)">Exp = projection × ${D2.ratio[ 'QB' ]}–${D2.ratio['DEF']} deflator by position; ` +
    `VOR = Exp above the points the last startable player at that position really scored</span>`;
}

function xLast() {
  const sel = document.getElementById('xseason');
  if (!sel.options.length) {
    D2.seasons.slice().reverse().forEach(s => sel.add(new Option(s, s)));
    xState.season = String(D2.seasons[D2.seasons.length - 1]);
    sel.value = xState.season;
  }
  const yr = xState.season || sel.value;
  const p2 = document.getElementById('xposf2');
  if (p2.options.length === 1) xPOS.forEach(p => p2.add(new Option(p, p)));
  const teams = (D2.teams[yr] || []).slice().sort((a, b) => a.fin - b.fin);
  const picks = (D2.draft[yr] || []);
  const tname = {}; teams.forEach(t => tname[t.id] = t);

  document.getElementById('xlastH').textContent = yr + ' draft';
  const nT = teams.length;
  const scored = picks.filter(p => p.act != null);
  const meanH = teams.length ? teams.reduce((a, t) => a + (t.haul || 0), 0) / teams.length : 0;
  document.getElementById('xlTiles').innerHTML = [
    [nT, 'teams'], [picks.length, 'picks'],
    [Math.round(meanH), 'mean points drafted'],
    [scored.length ? Math.round(scored.reduce((a, p) => a + p.st, 0) / scored.length * 100) + '%' : '—', 'picks that finished startable']
  ].map(([v, k]) => `<div class="tile"><div class="v kpi">${v}</div><div class="k">${k}</div></div>`).join('');

  document.getElementById('xteamT').innerHTML =
    `<thead><tr><th class="l">Finish</th><th class="l">Team</th><th class="l">Manager</th>
      <th>W-L</th><th>Points for</th><th>Drafted pts</th><th>Startables</th></tr></thead><tbody>` +
    teams.map(t => `<tr>
      <td class="l" style="font-weight:650">${t.fin || '—'}</td>
      <td class="l">${t.name}</td><td class="l" style="color:var(--ink2)">${t.own}</td>
      <td>${t.w}-${t.l}</td><td>${xFmt(t.pf)}</td><td>${xFmt(t.haul)}</td><td>${t.startables}</td></tr>`).join('') +
    '</tbody>';

  let rows = picks;
  if (xState.pos2) rows = rows.filter(p => p.pos === xState.pos2);
  const shade = v => v == null ? 'd0'
    : v >= 90 ? 'd3' : v >= 45 ? 'd2' : v >= 15 ? 'd1'
    : v <= -90 ? 'dm3' : v <= -45 ? 'dm2' : v <= -15 ? 'dm1' : 'd0';
  document.getElementById('xlastT').innerHTML =
    `<thead><tr><th class="l">Pick</th><th class="l">Player</th><th class="l">Pos</th>
      <th class="l">Drafted by</th><th>Points</th><th>Proj</th><th class="l">Finished</th>
      <th>vs round</th></tr></thead><tbody>` +
    rows.map(p => `<tr>
      <td class="l" style="font-weight:650">${p.rd}.${String(p.pk).padStart(2, '0')}</td>
      <td class="l">${p.n}</td>
      <td class="l"><span class="pos" style="background:var(${POSC[p.pos] || '--muted'})">${p.pos}</span></td>
      <td class="l" style="color:var(--ink2)">${tname[p.tm] ? tname[p.tm].ab : p.tm}</td>
      <td>${p.act == null ? '—' : xFmt(p.act)}</td>
      <td>${p.prj ? xFmt(p.prj) : '<span style="color:var(--muted)">—</span>'}</td>
      <td class="l fin">${p.fin || ''}${p.st ? '' : p.fin ? ' <span style="color:var(--muted)">(bench)</span>' : ''}</td>
      <td class="${shade(p.vor)}">${p.vor == null ? '—' : (p.vor > 0 ? '+' : '') + xFmt(p.vor)}</td></tr>`).join('') +
    '</tbody>';
  document.getElementById('xdvLeg').innerHTML =
    '<span><i style="background:var(--div-pos)"></i>beat the average return of its round</span>' +
    '<span><i style="background:var(--div-neg)"></i>fell short of it</span>' +
    '<span style="color:var(--muted)">shading repeats the number beside it; 2023 projections were not retained by ESPN</span>';
}

function xStr() {
  document.getElementById('xRules').innerHTML = D2.rules.map(r => `
    <div class="rule">
      <div class="meta"><span class="pill ${r.conf}">${r.conf}</span><span class="area">${r.area}</span></div>
      <h3>${r.rule}</h3>
      <p class="why">${r.why}</p>
      <div class="n">${r.n}</div>
    </div>`).join('');
}

function xQbChart() {
  const rows = D2.qbedge, W = 860, H = 280, m = {t: 14, r: 16, b: 46, l: 52};
  const max = Math.max(...rows.flatMap(r => [r.qb, r.flex])) * 1.08;
  const gw = (W - m.l - m.r) / rows.length, bw = (gw - 26) / 2;
  const Y = v => H - m.b - v / max * (H - m.t - m.b);
  const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%'});
  for (let v = 0; v <= max; v += 50) {
    svg.append(el('line', {x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: cv('--grid'), 'stroke-width': 1}));
    const t = el('text', {x: m.l - 8, y: Y(v) + 4, fill: cv('--muted'), 'font-size': 14, 'text-anchor': 'end'});
    t.textContent = v; svg.append(t);
  }
  rows.forEach((r, i) => {
    [['qb', r.qb, r.qbn, cv('--s1'), 'QB'], ['flex', r.flex, r.flexn, cv('--muted'), 'RB / WR / TE']]
      .forEach(([k, v, n, fill], j) => {
        const x = m.l + i * gw + 13 + j * bw;
        const g = el('g');
        g.append(el('rect', {x, y: Y(v), width: bw - 4, height: Math.max(2, H - m.b - Y(v)), rx: 3, fill}));
        g.addEventListener('mousemove', e => showTip(e,
          `<b>Rounds ${r.band}</b><br>${j ? 'RB / WR / TE' : 'QB'}: ${v} pts<br>n=${n}`));
        g.addEventListener('mouseleave', hideTip);
        svg.append(g);
      });
    const lb = el('text', {x: m.l + i * gw + gw / 2, y: H - 26, fill: cv('--ink2'), 'font-size': 14.5, 'text-anchor': 'middle'});
    lb.textContent = 'Rd ' + r.band; svg.append(lb);
    const ed = el('text', {x: m.l + i * gw + gw / 2, y: H - 8, 'font-size': 14, 'text-anchor': 'middle',
      fill: r.edge > 0 ? cv('--div-pos') : cv('--div-neg'), 'font-weight': 650});
    ed.textContent = (r.edge > 0 ? '+' : '') + r.edge; svg.append(ed);
  });
  document.getElementById('xQbChart').replaceChildren(svg);
  document.getElementById('xQbLeg').innerHTML =
    `<span><i style="background:var(--s1)"></i>quarterbacks</span>` +
    `<span><i style="background:var(--muted)"></i>running backs, receivers, tight ends</span>` +
    `<span style="color:var(--muted)">figure under each band is the QB advantage in points</span>`;
}

function xRdChart() {
  const rows = D2.rdstat, W = 860, H = 270, m = {t: 14, r: 44, b: 34, l: 46};
  const max = Math.max(...rows.map(r => r.mean)) * 1.08;
  const bw = (W - m.l - m.r) / rows.length;
  const Y = v => H - m.b - v / max * (H - m.t - m.b);
  const Ys = v => H - m.b - v / 100 * (H - m.t - m.b);
  const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%'});
  for (let v = 0; v <= max; v += 50) {
    svg.append(el('line', {x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: cv('--grid'), 'stroke-width': 1}));
    const t = el('text', {x: m.l - 8, y: Y(v) + 4, fill: cv('--muted'), 'font-size': 14, 'text-anchor': 'end'});
    t.textContent = v; svg.append(t);
  }
  rows.forEach((r, i) => {
    const x = m.l + i * bw + 3, g = el('g');
    g.append(el('rect', {x, y: Y(r.mean), width: bw - 6, height: Math.max(2, H - m.b - Y(r.mean)), rx: 3, fill: cv('--s1')}));
    g.addEventListener('mousemove', e => showTip(e,
      `<b>Round ${r.rd}</b><br>${r.mean} pts mean<br>${r.med} median<br>${r.st}% startable<br>n=${r.n}`));
    g.addEventListener('mouseleave', hideTip);
    svg.append(g);
    const lb = el('text', {x: x + (bw - 6) / 2, y: H - 12, fill: cv('--ink2'), 'font-size': 13.5, 'text-anchor': 'middle'});
    lb.textContent = r.rd; svg.append(lb);
  });
  const pts = rows.map((r, i) => `${m.l + i * bw + bw / 2},${Ys(r.st)}`).join(' ');
  svg.append(el('polyline', {points: pts, fill: 'none', stroke: cv('--s2'), 'stroke-width': 2, 'stroke-linejoin': 'round'}));
  const rl = el('text', {x: W - m.r + 6, y: Ys(rows[0].st) + 4, fill: cv('--s2'), 'font-size': 13.5});
  rl.textContent = 'startable %'; svg.append(rl);
  document.getElementById('xRdChart').replaceChildren(svg);
}

function xPosChart() {
  const bands = D2.bands, W = 860, H = 280, m = {t: 14, r: 16, b: 34, l: 46};
  const gw = (W - m.l - m.r) / (bands.length - 1);
  const Y = v => H - m.b - v / 100 * (H - m.t - m.b);
  const svg = el('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%'});
  for (let v = 0; v <= 100; v += 25) {
    svg.append(el('line', {x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), stroke: cv('--grid'), 'stroke-width': 1}));
    const t = el('text', {x: m.l - 8, y: Y(v) + 4, fill: cv('--muted'), 'font-size': 14, 'text-anchor': 'end'});
    t.textContent = v + '%'; svg.append(t);
  }
  bands.forEach((b, i) => {
    const t = el('text', {x: m.l + i * gw, y: H - 12, fill: cv('--ink2'), 'font-size': 14.5, 'text-anchor': 'middle'});
    t.textContent = 'Rd ' + b; svg.append(t);
  });
  D2.posband.forEach(row => {
    const pts = [];
    row.cells.forEach((c, i) => { if (c.st != null) pts.push([m.l + i * gw, Y(c.st), c, i]); });
    if (pts.length > 1)
      svg.append(el('polyline', {points: pts.map(p => p[0] + ',' + p[1]).join(' '), fill: 'none',
        stroke: cv(POSC[row.pos]), 'stroke-width': 2, 'stroke-linejoin': 'round'}));
    pts.forEach(([x, y, c]) => {
      const g = el('g');
      g.append(el('circle', {cx: x, cy: y, r: c.n < 25 ? 3 : 4.5, fill: cv(POSC[row.pos]), opacity: c.n < 25 ? .45 : 1}));
      g.addEventListener('mousemove', e => showTip(e,
        `<b>${row.pos}, rounds ${c.band}</b><br>${c.st}% startable<br>mean ${c.mean} pts<br>n=${c.n}${c.n < 25 ? ' — thin' : ''}`));
      g.addEventListener('mouseleave', hideTip);
      svg.append(g);
    });
  });
  document.getElementById('xPosChart').replaceChildren(svg);
  document.getElementById('xPosLeg').innerHTML = xPOS.map(p =>
    `<span><i style="background:var(${POSC[p]})"></i>${p}</span>`).join('') +
    '<span style="color:var(--muted)">faded points = fewer than 25 picks</span>';
}

function xCountTable() {
  document.getElementById('xCountT').innerHTML =
    `<thead><tr><th class="l">Round</th>${xPOS.map(p => `<th>${p}</th>`).join('')}<th>Total</th></tr></thead><tbody>` +
    D2.poscount.map(r => {
      const tot = xPOS.reduce((a, p) => a + r[p], 0);
      return `<tr><td class="l" style="font-weight:650">${r.rd}</td>` +
        xPOS.map(p => {
          const share = tot ? r[p] / tot : 0;
          const bg = share > 0 ? `background:color-mix(in srgb,var(${POSC[p]}) ${Math.round(share * 62)}%,transparent)` : '';
          return `<td style="${bg}">${r[p] || ''}</td>`;
        }).join('') + `<td style="color:var(--ink2)">${tot}</td></tr>`;
    }).join('') + '</tbody>';
}

function xAnl() { xQbChart(); xRdChart(); xPosChart(); xCountTable(); }

/* ---------- Perennial Push: snake draft plan ----------
   The auction planner budgets dollars; a snake planner budgets picks. The
   constraint here is not what you can afford but who is still on the board when
   your turn comes round, so the unit of the plan is your own eighteen picks. */
const XTEAMS = 12, XRDS = 18;
const XNEED = {QB: 1, RB: 2, WR: 3, TE: 1, SUPERFLEX: 1, FLEX: 1, K: 1, DEF: 1};
const XSTART = Object.values(XNEED).reduce((a, b) => a + b, 0);   // 11
const XBENCH = XRDS - XSTART;                                     // 7
const xById = {};
D2.board.forEach(p => xById[p.pid] = p);

// snake: odd rounds run 1..12, even rounds run back 12..1
const xPickNo = (slot, rd) => (rd - 1) * XTEAMS + (rd % 2 ? slot : XTEAMS + 1 - slot);
const xMyPicks = slot => Array.from({length: XRDS}, (_, i) => xPickNo(slot, i + 1));

let xplans = [], xactive = 0;
function xLoadPlans() {
  const p = loadPending();
  if (p && Array.isArray(p.xplans) && p.xplans.length) { xplans = p.xplans; return; }
  xplans = [{name: 'Plan A', slot: 6, ids: Array(XRDS).fill(null)}];
}
xLoadPlans();
const xCur = () => xplans[Math.min(xactive, xplans.length - 1)];
function xSavePlans() { stashPending(); }

function xPlanStats(pl) {
  const rows = pl.ids.map(id => id ? xById[id] : null);
  const filled = rows.filter(Boolean);
  // fill starting slots best-first, then bench
  const need = Object.assign({}, XNEED);
  const starters = [], bench = [];
  filled.slice().sort((a, b) => (b.vor == null ? -1e9 : b.vor) - (a.vor == null ? -1e9 : a.vor))
    .forEach(r => {
      if (need[r.pos] > 0) { need[r.pos]--; starters.push([r.pos, r]); }
      else if (r.pos === 'QB' && need.SUPERFLEX > 0) { need.SUPERFLEX--; starters.push(['SUPERFLEX', r]); }
      else if (['RB', 'WR', 'TE'].includes(r.pos) && need.FLEX > 0) { need.FLEX--; starters.push(['FLEX', r]); }
      else if (['RB', 'WR', 'TE'].includes(r.pos) && need.SUPERFLEX > 0) { need.SUPERFLEX--; starters.push(['SUPERFLEX', r]); }
      else bench.push(r);
    });
  const missing = Object.keys(need).filter(k => need[k] > 0).map(k => [k, need[k]]);
  return {rows, filled, starters, bench, missing,
    exp: Math.round(starters.reduce((a, s) => a + (s[1].exp || 0), 0)),
    legal: missing.length === 0};
}

function xPlanBar() {
  const sel = document.getElementById('xplanSel');
  sel.innerHTML = xplans.map((p, i) =>
    `<option value="${i}"${i === xactive ? ' selected' : ''}>${esc(p.name)}</option>`).join('');
  const sl = document.getElementById('xslot');
  if (!sl.options.length)
    for (let i = 1; i <= XTEAMS; i++) sl.add(new Option(i, i));
  sl.value = xCur().slot;
  const s = xPlanStats(xCur());
  document.getElementById('xplanMeter').innerHTML =
    `<b>${s.filled.length}</b> / ${XRDS} picks &middot; <b>${s.exp}</b> projected starting points &middot; ` +
    (s.legal ? '<span class="up">lineup complete</span>'
             : `<span class="dn">need ${s.missing.map(m => m[1] + ' ' + m[0]).join(', ')}</span>`);
  const nm = document.getElementById('xplanName');
  if (document.activeElement !== nm) nm.value = xCur().name;
}

function xPlanPicks() {
  const pl = xCur(), mine = xMyPicks(pl.slot);
  let html = '';
  mine.forEach((no, i) => {
    const rd = i + 1, r = pl.ids[i] ? xById[pl.ids[i]] : null;
    // A player ranked well ahead of the pick you are holding will not still be
    // sitting there; one ranked well behind it means you are taking him early.
    const gone  = r && r.rank != null && (no - r.rank) >= 12;
    const reach = r && r.rank != null && (no - r.rank) <= -12;
    const badge = !r ? '' : gone
      ? ` <span class="dn" title="board rank ${r.rank}, pick ${no}">unlikely to last</span>`
      : reach ? ` <span class="up" title="board rank ${r.rank}, pick ${no}">reach — could wait</span>` : '';
    html += `<div class="slot${r ? '' : ' empty'}">
      <span class="lab">${rd}.${String(no).padStart(3, ' ')}</span>
      <span class="nm">${r ? starHtml(xKey(r)) + esc(r.n) +
        ` <span style="color:var(--muted)">${r.pos}${r.prank} &middot; ${r.tm}</span>` + badge
        : '&mdash;'}</span>
      <span class="pr">${r ? xFmt(r.exp) : ''}</span>
      ${r ? `<button class="btn mini" data-xdrop="${i}" aria-label="remove">&times;</button>` : ''}
    </div>`;
  });
  const host = document.getElementById('xplanPicks');
  host.innerHTML = html;
  bindStars(host);
  host.querySelectorAll('[data-xdrop]').forEach(b => b.onclick = () => {
    xCur().ids[+b.dataset.xdrop] = null; xSavePlans(); xDrawPlan();
  });
}

function xPlanRoster() {
  const s = xPlanStats(xCur());
  const order = ['QB', 'RB', 'WR', 'TE', 'SUPERFLEX', 'FLEX', 'K', 'DEF'];
  const pool = s.starters.slice();
  let html = '<div class="slot" style="border:0"><span class="lab">LINEUP</span><span class="nm" style="color:var(--muted)">' +
    s.exp + ' projected points from your eleven starters</span></div>';
  order.forEach(pos => {
    for (let i = 0; i < XNEED[pos]; i++) {
      const idx = pool.findIndex(x => x[0] === pos);
      const r = idx >= 0 ? pool.splice(idx, 1)[0][1] : null;
      html += `<div class="slot start${r ? '' : ' empty'}">
        <span class="lab" style="width:74px">${pos}</span>
        <span class="nm">${r ? esc(r.n) + ` <span style="color:var(--muted)">${r.pos}${r.prank}</span>` : '&mdash;'}</span>
        <span class="pr">${r ? xFmt(r.exp) : ''}</span></div>`;
    }
  });
  html += `<div class="slot" style="border:0;padding-top:8px"><span class="lab">BENCH</span><span class="nm"></span></div>`;
  for (let i = 0; i < XBENCH; i++) {
    const r = s.bench[i];
    html += `<div class="slot bench${r ? '' : ' empty'}"><span class="lab" style="width:74px"></span>
      <span class="nm">${r ? esc(r.n) + ` <span style="color:var(--muted)">${r.pos}${r.prank}</span>` : '&mdash;'}</span>
      <span class="pr">${r ? xFmt(r.exp) : ''}</span></div>`;
  }
  document.getElementById('xplanRoster').innerHTML = html;
}

function xPlanPool() {
  const q = document.getElementById('xpq').value.toLowerCase();
  const pf = document.getElementById('xppos').value;
  const hide = document.getElementById('xphide').checked;
  const tgt = document.getElementById('xptgt').checked;
  const sel = document.getElementById('xppos');
  if (sel.options.length === 1) xPOS.forEach(p => sel.add(new Option(p, p)));
  const taken = new Set(xCur().ids.filter(Boolean));
  const rows = D2.board.filter(r =>
    (!q || r.n.toLowerCase().includes(q)) && (!pf || r.pos === pf) &&
    (!hide || !taken.has(r.pid)) && (!tgt || targets.has(xKey(r)))).slice(0, 300);
  const t = document.getElementById('xplanPool');
  t.innerHTML = '<thead><tr><th class="l" style="cursor:default">#</th><th class="l">player</th>' +
    '<th class="l">pos</th><th>Exp</th><th>VOR</th><th></th></tr></thead><tbody>' +
    rows.map(r => `<tr>
      <td class="l" style="color:var(--muted)">${r.rank == null ? '—' : r.rank}</td>
      <td class="l">${starHtml(xKey(r))}${esc(r.n)}
        <span style="color:var(--muted)">${r.tm}</span></td>
      <td class="l"><span class="pos" style="background:var(${POSC[r.pos] || '--muted'})">${r.pos}${r.prank}</span></td>
      <td>${xFmt(r.exp)}</td>
      <td>${r.vor == null ? '<span style="color:var(--muted)">stream</span>' : (r.vor > 0 ? '+' : '') + xFmt(r.vor)}</td>
      <td><button class="btn mini" data-xadd="${r.pid}">add</button></td></tr>`).join('') +
    '</tbody>';
  bindStars(t);
  t.querySelectorAll('[data-xadd]').forEach(b => b.onclick = () => {
    const pid = b.dataset.xadd, p = xById[pid], pl = xCur();
    if (pl.ids.includes(pid)) return;
    const mine = xMyPicks(pl.slot);
    let slot;
    if (p.rank == null) {
      // kickers and defences carry no board rank and cost nothing to wait on:
      // five seasons say never before round 13, so that is where they land
      slot = pl.ids.findIndex((v, i) => !v && i >= 12);
    } else {
      // earliest of my picks where he could still plausibly be on the board
      slot = pl.ids.findIndex((v, i) => !v && mine[i] >= p.rank);
    }
    if (slot < 0) slot = pl.ids.findIndex(v => !v);
    if (slot < 0) return;                        // all eighteen picks used
    pl.ids[slot] = pid;
    xSavePlans(); xDrawPlan();
  });
}

function xPlanCompare() {
  const cols = xplans.map(xPlanStats);
  const posRow = pos => xplans.map((p, i) =>
    `<td>${cols[i].filled.filter(r => r.pos === pos).length || ''}</td>`).join('');
  document.getElementById('xplanCmp').innerHTML =
    '<thead><tr><th class="l">&nbsp;</th>' + xplans.map(p => `<th class="l">${esc(p.name)}</th>`).join('') +
    '</tr></thead><tbody>' +
    '<tr><td class="l">draft slot</td>' + xplans.map(p => `<td>${p.slot}</td>`).join('') + '</tr>' +
    '<tr><td class="l">picks used</td>' + cols.map(c => `<td>${c.filled.length}/${XRDS}</td>`).join('') + '</tr>' +
    '<tr><td class="l">projected starting points</td>' + cols.map(c => `<td><b>${c.exp}</b></td>`).join('') + '</tr>' +
    '<tr><td class="l">lineup</td>' + cols.map(c => `<td>${c.legal
      ? '<span class="up">complete</span>'
      : '<span class="dn">' + c.missing.map(m => m[1] + ' ' + m[0]).join(', ') + '</span>'}</td>`).join('') + '</tr>' +
    xPOS.map(pos => `<tr><td class="l">${pos}</td>${posRow(pos)}</tr>`).join('') +
    '</tbody>';
}

function xDrawPlan() { xPlanBar(); xPlanPicks(); xPlanRoster(); xPlanPool(); xPlanCompare(); }

(function xPlanWire() {
  const on = (id, ev, fn) => { const n = document.getElementById(id); if (n) n.addEventListener(ev, fn); };
  on('xplanSel', 'change', e => { xactive = +e.target.value; xDrawPlan(); });
  on('xslot', 'change', e => { xCur().slot = +e.target.value; xSavePlans(); xDrawPlan(); });
  on('xplanName', 'input', e => { xCur().name = e.target.value || 'untitled'; xSavePlans(); xPlanCompare(); });
  on('xplanNew', 'click', () => {
    xplans.push({name: 'Plan ' + String.fromCharCode(65 + xplans.length), slot: xCur().slot,
      ids: Array(XRDS).fill(null)});
    xactive = xplans.length - 1; xSavePlans(); xDrawPlan();
  });
  on('xplanCopy', 'click', () => {
    const c = JSON.parse(JSON.stringify(xCur()));
    c.name = c.name + ' copy'; xplans.push(c); xactive = xplans.length - 1; xSavePlans(); xDrawPlan();
  });
  on('xplanDel', 'click', () => {
    if (xplans.length < 2) return;               // never leave the planner empty
    xplans.splice(xactive, 1); xactive = 0; xSavePlans(); xDrawPlan();
  });
  ['xpq', 'xppos', 'xphide', 'xptgt'].forEach(id => on(id, id === 'xpq' ? 'input' : 'change', xPlanPool));
})();

/* ---- Perennial Push filter wiring ---- */
(function xWire() {
  const on = (id, ev, fn) => { const n = document.getElementById(id); if (n) n.addEventListener(ev, fn); };
  on('xq', 'input', e => { xState.q = e.target.value; xBoard(); });
  on('xposf', 'change', e => { xState.pos = e.target.value; xBoard(); });
  on('xposf2', 'change', e => { xState.pos2 = e.target.value; xLast(); });
  on('xseason', 'change', e => { xState.season = e.target.value; xLast(); });
  const tog = (id, key, fn) => on(id, 'click', e => {
    xState[key] = !xState[key];
    e.target.setAttribute('aria-pressed', String(xState[key]));
    fn();
  });
  tog('xtgtOnly', 'tgt', () => xBoard());
  tog('xarbOnly', 'arb', () => xBoard());
  on('xstream', 'click', e => {
    xState.hideStream = !xState.hideStream;
    e.target.setAttribute('aria-pressed', String(xState.hideStream));
    e.target.textContent = xState.hideStream ? 'hide K / D-ST' : 'show K / D-ST';
    xBoard();
  });
})();
"""

sub('\nfunction draw() {', JS + '\nfunction draw() {', label='js-insert')

# the snake planner rides the same autosave payload as everything else, so one
# "saved" indicator stays truthful for both leagues
sub("""      {targets: [...targets], notes: notes, plans: plans,
       basedOn: SHARED.saved_at || ''}));""",
    """      {targets: [...targets], notes: notes, plans: plans,
       xplans: (typeof xplans !== 'undefined' ? xplans : []),
       basedOn: SHARED.saved_at || ''}));""", label='stash-xplans')

# draw(): render only the active league's surfaces
sub("""function draw() {
  markSaveState();
  if (dirty && !saving) scheduleSave();     // covers anything recovered on load
  boardTable(); drawLast(); drawPlan(); drawStrategy(); drawNFL(); drawVegas();
  tierChart(); startableChart(); posShare(); scatter(); deadZones();
}
draw();""",
"""function draw() {
  markSaveState();
  if (dirty && !saving) scheduleSave();     // covers anything recovered on load
  if (LG === 'pbaffl') {
    boardTable(); drawLast(); drawPlan(); drawStrategy();
    tierChart(); startableChart(); posShare(); scatter(); deadZones();
  } else {
    xBoard(); xLast(); xDrawPlan(); xStr(); xAnl();
  }
  drawNFL(); drawVegas();                   // league-agnostic in both modes
}
applyLeague(false);
draw();""", label='draw')

# stars must refresh whichever board is on screen
sub("""    // redraw only the surfaces that show stars, so a click stays instant
    boardTable(); drawPlan();""",
"""    // redraw only the surfaces that show stars, so a click stays instant
    if (LG === 'pbaffl') { boardTable(); drawPlan(); } else { xBoard(); xDrawPlan(); }""", label='stars')

# ESPN's raw rank runs past 400; the board holds ~210 skill players. Show ESPN's
# position inside the same pool so the two columns are comparable.
sub("<td>${p.espn == null ? '—' : Math.floor((p.espn - 1) / 12) + 1}</td>",
    "<td>${p.espnRank == null ? '—' : Math.floor((p.espnRank - 1) / 12) + 1}</td>", label='espnRank')

open('report_v3.html', 'w', encoding='utf-8').write(src)
print('patch2 ok — bytes', len(src))
