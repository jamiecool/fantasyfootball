p2 = open('patch2.py').read()

PLAN = r"""
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
    // a player whose board rank sits well before this pick is unlikely to last
    const reach = r && r.rank != null && (no - r.rank) <= -12;
    const val = r && r.rank != null && (no - r.rank) >= 12;
    const badge = !r ? '' : reach
      ? ` <span class="dn" title="board rank ${r.rank}">likely gone</span>`
      : val ? ` <span class="up" title="board rank ${r.rank}">value here</span>` : '';
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
    // earliest of my picks where he could still plausibly be on the board
    let slot = pl.ids.findIndex((v, i) => !v && p.rank != null && mine[i] >= p.rank);
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
"""

anchor = "\n/* ---- Perennial Push filter wiring ---- */"
assert anchor in p2
p2 = p2.replace(anchor, PLAN + anchor, 1)

# persist plans through the same pending payload as PBAFFL's
p2 = p2.replace("""sub('\\nfunction draw() {', JS + '\\nfunction draw() {', label='js-insert')""",
"""sub('\\nfunction draw() {', JS + '\\nfunction draw() {', label='js-insert')

# the snake planner rides the same autosave payload as everything else, so one
# "saved" indicator stays truthful for both leagues
sub(\"\"\"      {targets: [...targets], notes: notes, plans: plans,
       basedOn: SHARED.saved_at || ''}));\"\"\",
    \"\"\"      {targets: [...targets], notes: notes, plans: plans,
       xplans: (typeof xplans !== 'undefined' ? xplans : []),
       basedOn: SHARED.saved_at || ''}));\"\"\", label='stash-xplans')""")

# render it with the rest of the ppp surfaces
p2 = p2.replace("""    xBoard(); xLast(); xStr(); xAnl();""",
                """    xBoard(); xLast(); xDrawPlan(); xStr(); xAnl();""")

# stars shown in the planner need to refresh with the board
p2 = p2.replace("""if (LG === 'pbaffl') { boardTable(); drawPlan(); } else { xBoard(); }""",
                """if (LG === 'pbaffl') { boardTable(); drawPlan(); } else { xBoard(); xDrawPlan(); }""")

open('patch2.py', 'w').write(p2)
print('patch2: snake planner wired')
