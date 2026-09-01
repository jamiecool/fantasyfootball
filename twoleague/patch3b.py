p3 = open('patch3.py').read()

# ---- note copy ----
p3 = p3.replace("""        <p class="note">What every team walked out of the draft holding. Players who finished the season
          startable at their position sit above the dashed line, each group in the order the team took them.
          Cards are ordered by where the team finished.</p>""",
"""        <p class="note">What every team walked out of the draft holding, slotted into this league's starting
          lineup — QB, two RB, three WR, TE, superflex, flex, K and D/ST — with everyone else on the bench.
          Slots are filled by full-season points, so this is the best lineup the draft could have fielded,
          not what was started week to week. Cards are ordered by where the team finished.</p>""")

p3 = p3.replace("""        <p class="note">What every roster looked like coming out of the auction. Players who finished the
          season startable at their position sit above the dashed line, each group most expensive first.
          Cards are ordered by where the team finished.</p>""",
"""        <p class="note">What every roster looked like coming out of the auction, slotted into this league's
          starting lineup — QB, two RB, three WR, TE, K and D/ST — with everyone else on the bench. Slots are
          filled by full-season points, so this is the best lineup the draft could have fielded, not what was
          started week to week. Cards are ordered by where the team finished.</p>""")

# ---- shared lineup filler ----
p3 = p3.replace("""function posCounts(list, key) {""",
"""/* Fill a starting lineup from a drafted roster, best season first. Required slots
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
function posCounts(list, key) {""")

# ---- PPP card ----
p3 = p3.replace("""    const mine = picks.filter(p => p.tm === t.id).sort((a, b) => a.o - b.o);
    const starters = mine.filter(p => p.st), bench = mine.filter(p => !p.st);
    const line = (p, cls) => `<tr class="${cls}">
      <td class="l" style="color:var(--muted);width:46px">${p.rd}.${String(p.pk).padStart(2, '0')}</td>
      <td class="l"><span class="pos" style="background:var(${POSC[p.pos] || '--muted'})">${p.pos}</span></td>
      <td class="l">${esc(p.n)}</td>
      <td style="width:52px">${p.act == null ? '—' : xFmt(p.act)}</td>
      <td class="l" style="width:44px;color:var(--ink2)">${p.fin || ''}</td></tr>`;
    const rows = starters.map(p => line(p, '')).join('') +
      (starters.length && bench.length ? '<tr class="divider"><td colspan="5"></td></tr>' : '') +
      bench.map(p => line(p, 'bench')).join('');""",
"""    const mine = picks.filter(p => p.tm === t.id).sort((a, b) => a.o - b.o);
    const L = fillLineup(mine, {QB: 1, RB: 2, WR: 3, TE: 1, SUPERFLEX: 1, FLEX: 1, K: 1, DEF: 1}, 'pos', 'act');
    const line = (slot, p, cls) => `<tr class="${cls}">
      <td class="l sl">${slot}</td>
      <td class="l" style="color:var(--muted);width:44px">${p ? p.rd + '.' + String(p.pk).padStart(2, '0') : ''}</td>
      <td class="l">${p ? `<span class="pos" style="background:var(${POSC[p.pos] || '--muted'})">${p.pos}</span>` : ''}</td>
      <td class="l">${p ? esc(p.n) : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="width:52px">${p && p.act != null ? xFmt(p.act) : ''}</td>
      <td class="l" style="width:44px;color:var(--ink2)">${p ? (p.fin || '') : ''}</td></tr>`;
    const rows = L.starters.map(([s, p]) => line(s, p, '')).join('') +
      L.empty.map(s => line(s, null, 'empty')).join('') +
      (L.bench.length ? '<tr class="divider"><td colspan="6"></td></tr>' : '') +
      L.bench.map(p => line('', p, 'bench')).join('');""")

p3 = p3.replace("""      `<span style="color:var(--muted)">${t.startables}/${mine.length} startable &middot; ${Math.round(t.haul)} drafted pts &middot; ${posCounts(mine, 'pos')}</span>`;""",
"""      `<span style="color:var(--muted)">${Math.round(L.starters.reduce((a, s) => a + (s[1].act || 0), 0))} pts from the lineup &middot; ` +
      `${Math.round(t.haul)} drafted &middot; ${posCounts(mine, 'pos')}</span>`;""")

# ---- PBAFFL card ----
p3 = p3.replace("""    const starters = mine.filter(r => r.startable), bench = mine.filter(r => !r.startable);
    const line = (r, cls) => `<tr class="${cls}">
      <td class="l" style="width:44px;font-weight:650">$${r.price}</td>
      <td class="l"><span class="pos" style="background:var(${POSC[r.position] || '--muted'})">${r.position}</span></td>
      <td class="l">${esc(r.player_name)}</td>
      <td style="width:52px">${r.points == null ? '—' : Math.round(r.points)}</td>
      <td class="l" style="width:44px;color:var(--ink2)">${r.finish || ''}</td></tr>`;
    const body = starters.map(r => line(r, '')).join('') +
      (starters.length && bench.length ? '<tr class="divider"><td colspan="5"></td></tr>' : '') +
      bench.map(r => line(r, 'bench')).join('');""",
"""    const L = fillLineup(mine, Object.assign({}, D.starters), 'position', 'points');
    const line = (slot, r, cls) => `<tr class="${cls}">
      <td class="l sl">${slot}</td>
      <td class="l" style="width:40px;font-weight:650">${r ? '$' + r.price : ''}</td>
      <td class="l">${r ? `<span class="pos" style="background:var(${POSC[r.position] || '--muted'})">${r.position}</span>` : ''}</td>
      <td class="l">${r ? esc(r.player_name) : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="width:52px">${r && r.points != null ? Math.round(r.points) : ''}</td>
      <td class="l" style="width:44px;color:var(--ink2)">${r ? (r.finish || '') : ''}</td></tr>`;
    const body = L.starters.map(([s, r]) => line(s, r, '')).join('') +
      L.empty.map(s => line(s, null, 'empty')).join('') +
      (L.bench.length ? '<tr class="divider"><td colspan="6"></td></tr>' : '') +
      L.bench.map(r => line('', r, 'bench')).join('');""")

p3 = p3.replace("""      `<span style="color:var(--muted)">${t.starters || 0}/${mine.length} startable &middot; $${t.spend || 0} spent &middot; ${posCounts(mine, 'position')}</span>`;""",
"""      `<span style="color:var(--muted)">${Math.round(L.starters.reduce((a, s) => a + (s[1].points || 0), 0))} pts from the lineup &middot; ` +
      `$${t.spend || 0} spent &middot; ${posCounts(mine, 'position')}</span>`;""")

# ---- CSS for the slot column ----
p3 = p3.replace("""  .rcard .bench td{opacity:.62}""",
"""  .rcard .sl{width:64px;color:var(--muted);font-size:12.8px;font-weight:650;letter-spacing:.02em}
  .rcard .bench td{opacity:.62}
  .rcard tr.empty td{opacity:.5}""")

open('patch3.py', 'w').write(p3)
print('patch3 reorganized around lineup slots')
