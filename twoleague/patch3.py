src = open('report_v3.html', encoding='utf-8').read()
def sub(old, new, label=''):
    global src
    if old not in src: raise SystemExit('ANCHOR NOT FOUND: ' + (label or old[:70]))
    src = src.replace(old, new, 1)

# ---------------- CSS ----------------
sub("""  #xplanPicks .slot .lab{font-variant-numeric:tabular-nums}""",
"""  #xplanPicks .slot .lab{font-variant-numeric:tabular-nums}
  /* post-draft rosters: one card per team, so a whole roster reads at a glance
     instead of being reassembled from a pick list */
  .rgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(408px,1fr));gap:14px}
  .rcard{border:1px solid var(--border);border-radius:10px;padding:12px 14px;background:var(--plane)}
  .rcard h3{margin:0;font-size:16.2px;font-weight:650;display:flex;align-items:baseline;gap:7px}
  .rcard h3 .pl{color:var(--muted);font-size:14.4px;font-weight:600;min-width:22px}
  .rcard .sub2{color:var(--ink2);font-size:14.4px;margin:2px 0 9px}
  .rcard table{font-size:14.4px}
  .rcard th,.rcard td{padding:2px 5px;white-space:nowrap}
  .rcard tbody tr:hover{background:var(--surface)}
  .rcard .sl{width:52px;color:var(--muted);font-size:12.4px;font-weight:650;letter-spacing:.02em;
       overflow:hidden;white-space:nowrap}
  /* fixed layout so the name column absorbs the slack and ellipses instead of
     pushing the finish column outside the card */
  .rcard table{width:100%;table-layout:fixed}
  .rcard td.nmcell{overflow:hidden;text-overflow:ellipsis}
  .rcard .bench td{opacity:.62}
  .rcard tr.empty td{opacity:.5}
  .rcard .divider td{padding:0;border-bottom:1px dashed var(--axis)}
  .segwrap{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
  .segwrap .btn{border:0;border-radius:0;border-right:1px solid var(--border)}
  .segwrap .btn:last-child{border-right:0}
  .segwrap .btn[aria-pressed=true]{background:var(--surface);color:var(--ink);font-weight:650;
       box-shadow:inset 0 -2px 0 var(--s1)}""", label='css')

# ---------------- Perennial Push markup ----------------
sub("""      <div class="filters">
        <select id="xseason" aria-label="Choose a season" style="font-weight:650"></select>
        <select id="xposf2" aria-label="Filter by position"><option value="">all positions</option></select>
      </div>""",
"""      <div class="filters">
        <select id="xseason" aria-label="Choose a season" style="font-weight:650"></select>
        <span class="segwrap" role="group" aria-label="Choose a view">
          <button class="btn" id="xvPicks" aria-pressed="true">pick by pick</button>
          <button class="btn" id="xvRost" aria-pressed="false">rosters</button>
        </span>
        <select id="xposf2" aria-label="Filter by position"><option value="">all positions</option></select>
      </div>""", label='ppp-toggle')

sub("""      <h2 style="margin-top:20px">Pick by pick</h2>
      <div class="legend" id="xdvLeg"></div>
      <div class="scroll" style="max-height:60vh"><table id="xlastT" aria-label="Every pick in the selected season"></table></div>""",
"""      <div id="xPickWrap">
        <h2 style="margin-top:20px">Pick by pick</h2>
        <div class="legend" id="xdvLeg"></div>
        <div class="scroll" style="max-height:60vh"><table id="xlastT" aria-label="Every pick in the selected season"></table></div>
      </div>
      <div id="xRostWrap" hidden>
        <h2 style="margin-top:20px">Post-draft rosters</h2>
        <p class="note">What every team walked out of the draft holding, slotted into this league's starting
          lineup — QB, two RB, three WR, TE, superflex, flex, K and D/ST — with everyone else on the bench.
          Slots are filled by full-season points, so this is the best lineup the draft could have fielded,
          not what was started week to week. Cards are ordered by where the team finished.</p>
        <div class="rgrid" id="xRosters"></div>
      </div>""", label='ppp-roster-markup')

# ---------------- PBAFFL markup ----------------
sub("""      <div class="filters">
        <select id="lseason" aria-label="Choose a season" style="font-weight:650"></select>
        <input type="search" id="lq" aria-label="Filter last season's picks by player" placeholder="filter players…">""",
"""      <div class="filters">
        <select id="lseason" aria-label="Choose a season" style="font-weight:650"></select>
        <span class="segwrap" role="group" aria-label="Choose a view">
          <button class="btn" id="lvPicks" aria-pressed="true">pick by pick</button>
          <button class="btn" id="lvRost" aria-pressed="false">rosters</button>
        </span>
        <input type="search" id="lq" aria-label="Filter last season's picks by player" placeholder="filter players…">""",
    label='pbaffl-toggle')

sub("""      <div class="scroll"><table id="lastT" aria-label="Last season — every pick"></table></div>
    </div>""",
"""      <div class="scroll" id="lPickWrap"><table id="lastT" aria-label="Last season — every pick"></table></div>
      <div id="lRostWrap" hidden>
        <p class="note">What every roster looked like coming out of the auction, slotted into this league's
          starting lineup — QB, two RB, three WR, TE, K and D/ST — with everyone else on the bench. Slots are
          filled by full-season points, so this is the best lineup the draft could have fielded, not what was
          started week to week. Cards are ordered by where the team finished.</p>
        <div class="rgrid" id="lRosters"></div>
      </div>
    </div>""", label='pbaffl-roster-markup')

# ---------------- JS ----------------
JS = r"""
/* ---------- post-draft roster views ----------
   A pick list answers "what happened at 4.07"; it does not answer "what did that
   team end up with", which is the question you actually ask when reading an old
   draft. Same rows, regrouped by team and ordered the way the team built it. */
function rosterCard(head, sub, rows) {
  return `<div class="rcard">
    <h3>${head}</h3>
    <div class="sub2">${sub}</div>
    <table><tbody>${rows}</tbody></table></div>`;
}
/* Fill a starting lineup from a drafted roster, best season first. Required slots
   take priority, then superflex, then flex -- so a spare QB lands in superflex
   rather than crowding out the flex a running back needs. */
function fillLineup(list, need, posKey, ptsKey) {
  const order = Object.keys(need);
  const left = Object.assign({}, need);
  const starters = [], bench = [];
  list.slice().sort((a, b) => (b[ptsKey] || 0) - (a[ptsKey] || 0)).forEach(r => {
    const pos = r[posKey];
    if (left[pos] > 0) { left[pos]--; starters.push([pos, r]); }
    else if (left.SUPERFLEX > 0 && ['QB', 'RB', 'WR', 'TE'].includes(pos)) { left.SUPERFLEX--; starters.push(['SUPERFLEX', r]); }
    else if (left.FLEX > 0 && ['RB', 'WR', 'TE'].includes(pos)) { left.FLEX--; starters.push(['FLEX', r]); }
    else bench.push(r);
  });
  // present starters in lineup order, not in the order they were filled
  starters.sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]));
  const empty = order.filter(k => left[k] > 0).flatMap(k => Array(left[k]).fill(k));
  return {starters, bench, empty};
}
const SLOTLBL = {SUPERFLEX: 'SFLEX'};                 // full word overruns the column
const slotLabel = s => s ? `<span title="${s === 'SUPERFLEX' ? 'superflex — QB, RB, WR or TE' : s}">${SLOTLBL[s] || s}</span>` : '';
function posCounts(list, key) {
  const c = {};
  list.forEach(r => { const p = r[key]; c[p] = (c[p] || 0) + 1; });
  return ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'].filter(p => c[p]).map(p => c[p] + ' ' + p).join(' · ');
}

function xRosters() {
  const yr = xState.season || document.getElementById('xseason').value;
  const teams = (D2.teams[yr] || []).slice().sort((a, b) => (a.fin || 99) - (b.fin || 99));
  const picks = D2.draft[yr] || [];
  const host = document.getElementById('xRosters');
  host.innerHTML = teams.map(t => {
    const mine = picks.filter(p => p.tm === t.id).sort((a, b) => a.o - b.o);
    const L = fillLineup(mine, {QB: 1, RB: 2, WR: 3, TE: 1, SUPERFLEX: 1, FLEX: 1, K: 1, DEF: 1}, 'pos', 'act');
    const line = (slot, p, cls) => `<tr class="${cls}">
      <td class="l sl">${slotLabel(slot)}</td>
      <td class="l" style="color:var(--muted);width:44px">${p ? p.rd + '.' + String(p.pk).padStart(2, '0') : ''}</td>
      <td class="l" style="width:44px">${p ? `<span class="pos" style="background:var(${POSC[p.pos] || '--muted'})">${p.pos}</span>` : ''}</td>
      <td class="l nmcell">${p ? esc(p.n) : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="width:52px">${p && p.act != null ? xFmt(p.act) : ''}</td>
      <td class="l" style="width:44px;color:var(--ink2)">${p ? (p.fin || '') : ''}</td></tr>`;
    const rows = L.starters.map(([s, p]) => line(s, p, '')).join('') +
      L.empty.map(s => line(s, null, 'empty')).join('') +
      (L.bench.length ? '<tr class="divider"><td colspan="6"></td></tr>' : '') +
      L.bench.map(p => line('', p, 'bench')).join('');
    const head = `<span class="pl">${t.fin || '—'}</span>${esc(t.name)}`;
    const sub = `${esc(t.own)} &middot; ${t.w}-${t.l} &middot; ${Math.round(t.pf)} pts for<br>` +
      `<span style="color:var(--muted)">${Math.round(L.starters.reduce((a, s) => a + (s[1].act || 0), 0))} pts from the lineup &middot; ` +
      `${Math.round(t.haul)} drafted &middot; ${posCounts(mine, 'pos')}</span>`;
    return rosterCard(head, sub, rows);
  }).join('');
}

function lRosters() {
  const rows = D.draft[lSeason] || [];
  const meta = {};
  (D.draft_teams[lSeason] || []).forEach(t => meta[t.franchise] = t);
  const names = [...new Set(rows.map(r => r.franchise))]
    .sort((a, b) => ((meta[a] && meta[a].rank) || 99) - ((meta[b] && meta[b].rank) || 99));
  document.getElementById('lRosters').innerHTML = names.map(fr => {
    const mine = rows.filter(r => r.franchise === fr).sort((a, b) => b.price - a.price);
    const t = meta[fr] || {};
    const L = fillLineup(mine, Object.assign({}, D.starters), 'position', 'points');
    const line = (slot, r, cls) => `<tr class="${cls}">
      <td class="l sl">${slotLabel(slot)}</td>
      <td class="l" style="width:40px;font-weight:650">${r ? '$' + r.price : ''}</td>
      <td class="l" style="width:44px">${r ? `<span class="pos" style="background:var(${POSC[r.position] || '--muted'})">${r.position}</span>` : ''}</td>
      <td class="l nmcell">${r ? esc(r.player_name) : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="width:52px">${r && r.points != null ? Math.round(r.points) : ''}</td>
      <td class="l" style="width:44px;color:var(--ink2)">${r ? (r.finish || '') : ''}</td></tr>`;
    const body = L.starters.map(([s, r]) => line(s, r, '')).join('') +
      L.empty.map(s => line(s, null, 'empty')).join('') +
      (L.bench.length ? '<tr class="divider"><td colspan="6"></td></tr>' : '') +
      L.bench.map(r => line('', r, 'bench')).join('');
    const head = `<span class="pl">${t.rank || '—'}</span>${esc(fr)}`;
    const sub = (t.wins !== undefined && t.wins !== '' ? `${t.wins}-${t.losses} &middot; ` : '') +
      `${t.points_for ? Math.round(t.points_for) + ' pts for' : ''}<br>` +
      `<span style="color:var(--muted)">${Math.round(L.starters.reduce((a, s) => a + (s[1].points || 0), 0))} pts from the lineup &middot; ` +
      `$${t.spend || 0} spent &middot; ${posCounts(mine, 'position')}</span>`;
    return rosterCard(head, sub, body);
  }).join('');
}

function setView(which, pickWrap, rostWrap, bPicks, bRost, render) {
  const rost = which === 'rosters';
  document.getElementById(pickWrap).hidden = rost;
  document.getElementById(rostWrap).hidden = !rost;
  document.getElementById(bPicks).setAttribute('aria-pressed', String(!rost));
  document.getElementById(bRost).setAttribute('aria-pressed', String(rost));
  if (rost) render();
}
(function viewWire() {
  const g = id => document.getElementById(id);
  if (g('xvPicks')) {
    g('xvPicks').onclick = () => { xState.view = 'picks'; setView('picks', 'xPickWrap', 'xRostWrap', 'xvPicks', 'xvRost', xRosters); };
    g('xvRost').onclick = () => { xState.view = 'rosters'; setView('rosters', 'xPickWrap', 'xRostWrap', 'xvPicks', 'xvRost', xRosters); };
  }
  if (g('lvPicks')) {
    g('lvPicks').onclick = () => { lView = 'picks'; setView('picks', 'lPickWrap', 'lRostWrap', 'lvPicks', 'lvRost', lRosters); };
    g('lvRost').onclick = () => { lView = 'rosters'; setView('rosters', 'lPickWrap', 'lRostWrap', 'lvPicks', 'lvRost', lRosters); };
  }
})();
"""
sub('\nfunction draw() {', JS + '\nfunction draw() {', label='js')

# state + keep the active sub-view in step when the season changes
sub("""let xState = {q: '', pos: '', tgt: false, arb: false, hideStream: true, season: null, pos2: ''};""",
    """let xState = {q: '', pos: '', tgt: false, arb: false, hideStream: true, season: null, pos2: '', view: 'picks'};
let lView = 'picks';""", label='state')

sub("""  document.getElementById('xdvLeg').innerHTML =""",
    """  if (xState.view === 'rosters') xRosters();
  document.getElementById('xdvLeg').innerHTML =""", label='xlast-hook')

sub("""function drawLast() {
  document.getElementById('lastH').textContent = lSeason + ' draft — every pick';
  lastTiles(); lastTeamTable(); lastTable();
}""",
"""function drawLast() {
  document.getElementById('lastH').textContent = lSeason + ' draft — every pick';
  lastTiles(); lastTeamTable(); lastTable();
  if (lView === 'rosters') lRosters();
}""", label='drawLast-hook')

open('report_v3.html', 'w', encoding='utf-8').write(src)
print('patch3 ok — bytes', len(src))
