import json, io, sys
src = open('report_v2.html', encoding='utf-8').read()
D2 = open('ppp/ppp_data.json', encoding='utf-8').read()

def sub(old, new, n=1, label=''):
    global src
    if src.count(old) < 1:
        raise SystemExit('ANCHOR NOT FOUND: ' + (label or old[:70]))
    src = src.replace(old, new, n)

# ---------- 1. title ----------
sub('<title>PBAFFL — draft data</title>',
    '<title>Draft data — PBAFFL &amp; Perennial Push</title>', label='title')

# ---------- 2. CSS additions ----------
sub("""  .filters{display:flex;gap:8px;align-items:center;margin-bottom:11px;flex-wrap:wrap}""",
"""  .filters{display:flex;gap:8px;align-items:center;margin-bottom:11px;flex-wrap:wrap}
  /* league switcher: the one control that changes what every other surface means,
     so it sits in the header and is styled as a commitment, not a filter */
  .lgwrap{display:flex;align-items:center;gap:7px;margin-left:auto}
  .lgwrap label{color:var(--muted);font-size:14.4px}
  #lgSel{font-weight:650;font-size:15.6px;border-color:var(--s1)}
  .lgnote{font-size:14.4px;color:var(--ink2);margin:2px 0 0;flex-basis:100%}
  .ruleset{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}
  .rule{border:1px solid var(--border);border-radius:10px;padding:14px 16px;background:var(--plane)}
  .rule h3{margin:0 0 6px;font-size:16.2px;font-weight:650;line-height:1.35}
  .rule .meta{display:flex;gap:8px;align-items:center;margin-bottom:7px;flex-wrap:wrap}
  .rule .why{color:var(--ink2);font-size:15px;margin:0 0 7px}
  .rule .n{color:var(--muted);font-size:13.8px}
  .area{border-radius:999px;padding:1px 9px;font-size:13.1px;font-weight:600;
        border:1px solid var(--border);color:var(--ink2)}
  .kpi{font-variant-numeric:tabular-nums}
  tr.arb td{background:color-mix(in srgb,var(--s1) 13%,transparent)}
  .stream td{color:var(--ink2)}
  /* snake pick labels read "13.148" -- wider than the auction planner's slot tags */
  #xplanPicks .slot .lab,#xplanRoster .slot .lab{width:76px;white-space:nowrap}
  #xplanPicks .slot .lab{font-variant-numeric:tabular-nums}""", label='css')

# ---------- 3. header ----------
sub("""<header>
  <h1>PBAFFL — draft data</h1>
  <span class="sub">2026 board &amp; nine seasons of league history</span>
  <button class="tab toggle" id="saveBtn" aria-selected="false" disabled>saved</button>
  <button class="tab" id="themeBtn" aria-selected="false">◐ theme</button>
</header>""",
"""<header>
  <h1 id="hTitle">PBAFFL — draft data</h1>
  <span class="sub" id="hSub">2026 board &amp; nine seasons of league history</span>
  <button class="tab toggle" id="saveBtn" aria-selected="false" disabled>saved</button>
  <button class="tab" id="themeBtn" aria-selected="false">◐ theme</button>
  <span class="lgwrap">
    <label for="lgSel">League</label>
    <select id="lgSel" aria-label="Choose which league's rules and data to view">
      <option value="pbaffl">PBAFFL — auction, half-PPR</option>
      <option value="ppp">Perennial Push — snake, superflex</option>
    </select>
  </span>
</header>""", label='header')

# ---------- 4. tabs ----------
sub("""<div class="tabs" role="tablist">
  <button class="tab" role="tab" aria-selected="true"  data-p="board">2026 board</button>
  <button class="tab" role="tab" aria-selected="false" data-p="last" id="lastTab">Past drafts</button>
  <button class="tab" role="tab" aria-selected="false" data-p="nfl">NFL stats</button>
  <button class="tab" role="tab" aria-selected="false" data-p="vegas">Vegas</button>
  <button class="tab" role="tab" aria-selected="false" data-p="plan">Draft plan</button>
  <button class="tab" role="tab" aria-selected="false" data-p="str">Strategy</button>
  <button class="tab" role="tab" aria-selected="false" data-p="anl">Analytics</button>
</div>""",
"""<div class="tabs" role="tablist">
  <button class="tab" role="tab" aria-selected="true"  data-lg="pbaffl" data-p="board">2026 board</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="pbaffl" data-p="last" id="lastTab">Past drafts</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="ppp" data-p="xboard">2026 board</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="ppp" data-p="xlast">Past drafts</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="both" data-p="nfl">NFL stats</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="both" data-p="vegas">Vegas</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="pbaffl" data-p="plan">Draft plan</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="pbaffl" data-p="str">Strategy</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="pbaffl" data-p="anl">Analytics</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="ppp" data-p="xplan">Draft plan</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="ppp" data-p="xstr">Strategy</button>
  <button class="tab" role="tab" aria-selected="false" data-lg="ppp" data-p="xanl">Analytics</button>
</div>""", label='tabs')

# ---------- 5. new panels before </main> ----------
PANELS = """
  <!-- ================= Perennial Push (snake, superflex) ================= -->
  <section class="panel" id="p-xboard" hidden>
    <div class="card">
      <h2>The 2026 board — ranked for superflex</h2>
      <p class="note">Value over replacement under this league's own rules: full PPR, 12 teams,
        and a superflex slot that puts 24 quarterbacks in starting lineups every week.
        <b>Proj</b> is ESPN's raw projection; <b>Exp</b> deflates it by how far that position's
        projections have actually overshot here across five seasons; <b>VOR</b> measures Exp against
        the points the last startable player at the position really scored — not what ESPN projected
        he would. <b>#</b> is the overall pick, <b>Rd.Pk</b> the same pick in an 18-round snake, and
        <b>ESPN rd</b> where ESPN's one-QB board puts him. No dollar figures — this is a snake draft.</p>
      <div class="row" id="xbTiles"></div>
      <div class="legend" id="xbLeg"></div>
      <div class="filters">
        <input type="search" id="xq" aria-label="Filter the board by player" placeholder="filter players…">
        <select id="xposf" aria-label="Filter the board by position"><option value="">all positions</option></select>
        <button class="btn" id="xtgtOnly" aria-pressed="false">☆ targets only</button>
        <button class="btn" id="xarbOnly" aria-pressed="false">↑ cheaper than ESPN</button>
        <button class="btn" id="xstream" aria-pressed="true">hide K / D-ST</button>
      </div>
      <div class="scroll" style="max-height:74vh"><table id="xboardT"
        aria-label="2026 board ranked by value over replacement for a superflex league"></table></div>
    </div>
  </section>

  <section class="panel" id="p-xlast" hidden>
    <div class="card">
      <h2 id="xlastH">Every pick</h2>
      <p class="note">Five seasons of this league's drafts, with what each pick actually scored
        under these rules and how that compares with the average return of its round.</p>
      <div class="filters">
        <select id="xseason" aria-label="Choose a season" style="font-weight:650"></select>
        <select id="xposf2" aria-label="Filter by position"><option value="">all positions</option></select>
      </div>
      <div class="row" id="xlTiles"></div>
      <div class="scroll" style="max-height:38vh"><table id="xteamT" aria-label="Team draft summary"></table></div>
      <h2 style="margin-top:20px">Pick by pick</h2>
      <div class="legend" id="xdvLeg"></div>
      <div class="scroll" style="max-height:60vh"><table id="xlastT" aria-label="Every pick in the selected season"></table></div>
    </div>
  </section>

  <section class="panel" id="p-xplan" hidden>
    <div class="planbar">
      <select id="xplanSel" aria-label="Choose a draft plan"></select>
      <button class="btn" id="xplanNew">+ new</button>
      <button class="btn" id="xplanCopy">duplicate</button>
      <button class="btn" id="xplanDel">delete</button>
      <label class="chk" style="margin-left:6px">draft slot
        <select id="xslot" aria-label="Your position in the draft order"></select></label>
      <span class="spacer"></span>
      <span id="xplanMeter" class="meter"></span>
    </div>
    <div class="plangrid">
      <div class="card">
        <input id="xplanName" class="nameEdit" spellcheck="false" aria-label="plan name" placeholder="name this plan">
        <p class="note">Your eighteen picks, snaking from the slot above. <b>Exp</b> is the player's
          expected points under this league's scoring. A pick is flagged when the board ranks a player
          well ahead of where you would be taking him — he is unlikely to still be there.</p>
        <div id="xplanPicks"></div>
        <div id="xplanRoster" style="margin-top:14px"></div>
      </div>
      <div class="card">
        <h2>Add players</h2>
        <p class="note">Adding a player drops him into your earliest pick where the board says he could
          realistically still be available.</p>
        <div class="filters">
          <input type="search" id="xpq" aria-label="Search players to add to the plan" placeholder="search…">
          <select id="xppos" aria-label="Filter the player pool by position"><option value="">all pos</option></select>
          <label class="chk"><input type="checkbox" id="xphide" checked> hide picked</label>
          <label class="chk"><input type="checkbox" id="xptgt"> ★ targets only</label>
        </div>
        <div class="scroll" style="max-height:62vh"><table id="xplanPool" aria-label="Players available to add to the plan"></table></div>
      </div>
    </div>
    <div class="card">
      <h2>Compare</h2>
      <div class="scroll" style="max-height:none"><table id="xplanCmp" aria-label="Draft plan comparison"></table></div>
    </div>
  </section>

  <section class="panel" id="p-xstr" hidden>
    <div class="card">
      <h2>What five seasons of this league say</h2>
      <p class="note">Every rule below is derived from Perennial Push's own drafts, 2021–2025,
        scored under its own rules. None of PBAFFL's auction findings carry over — different
        draft format, different scoring, different roster.</p>
      <div class="ruleset" id="xRules"></div>
    </div>
  </section>

  <section class="panel" id="p-xanl" hidden>
    <div class="card">
      <h2>The quarterback gap</h2>
      <p class="note">Mean points returned by quarterbacks against the running backs, receivers and
        tight ends taken in the same rounds. In a superflex league the middle rounds are where the
        room stops paying for quarterbacks and the value does not.</p>
      <div class="legend" id="xQbLeg"></div>
      <div id="xQbChart"></div>
    </div>
    <div class="card">
      <h2>What a round is worth</h2>
      <p class="note">Average points returned per pick by round, with the share of picks that finished
        as a startable player at their position.</p>
      <div id="xRdChart"></div>
    </div>
    <div class="card">
      <h2>When each position stops paying</h2>
      <p class="note">Share of picks that finished startable, by position and round band.
        Faint lines are bands with fewer than 25 picks.</p>
      <div class="legend" id="xPosLeg"></div>
      <div id="xPosChart"></div>
    </div>
    <div class="card">
      <h2>What the room actually drafts, by round</h2>
      <div class="scroll" style="max-height:52vh"><table id="xCountT" aria-label="Positions drafted by round"></table></div>
    </div>
  </section>
</main>"""
sub('</main>', PANELS, label='panels')

# ---------- 6. data blob ----------
sub("\nconst POSC = {QB:'--s1'", "\nconst D2 = " + D2 + ";\nconst POSC = {QB:'--s1'", label='data')

open('report_v3.html','w',encoding='utf-8').write(src)
print('patch1 ok — bytes', len(src))
