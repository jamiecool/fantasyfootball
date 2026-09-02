"""What shapes a Perennial Push draft — the evidence behind the general draft plan.

PPP is the SECOND league: ESPN 623238770, snake, 18 rounds, full PPR, SUPERFLEX.
None of PBAFFL's auction findings transfer, and none of these transfer back.

Three questions, none of them about individual players:

  1. Does roster SHAPE predict how a team finished? (62 team-seasons, 2021-25)
  2. When does each position stop paying, and where is the quarterback window?
  3. Does full PPR actually make receivers more valuable, or just award everyone
     more points? -- the trap being that a bonus applied evenly to a position
     changes nothing about what a pick there is worth.

Run:
    python build_ppp_data.py && python analyze_ppp_shape.py

Reads cleandata/analysis/ppp_data.json (five seasons of PPP drafts) plus
final_ranks for the scoring-format question, which is about the NFL rather than
about this league and so uses all nine seasons on record.

SAMPLE SIZE IS THE WHOLE STORY HERE. 62 team-seasons is enough to see a large
effect and nowhere near enough to see a small one, so every split prints its n
and nothing under n=8 per side is reported at all. Read a null result as
UNPROVEN, not as proven absent -- the same discipline the PBAFFL findings audit
imposes in notes/findings/README.md.
"""
import json
import os
import sqlite3
import statistics as st
from collections import defaultdict

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "cleandata", "analysis", "ppp_data.json"),
                   encoding="utf-8"))
BAR = "=" * 74


def hdr(t):
    print(f"\n{BAR}\n  {t}\n{BAR}")


# ---------------------------------------------------------------------------
# team-seasons, with the shape of each team's draft
# ---------------------------------------------------------------------------
rows = []
for season, picks in D["draft"].items():
    teams = {t["id"]: t for t in D["teams"].get(season, [])}
    by_team = defaultdict(list)
    for p in picks:
        by_team[p["tm"]].append(p)
    for tid, ps in by_team.items():
        t = teams.get(tid)
        if not t or not ps:
            continue
        ps.sort(key=lambda x: x["o"])
        qbs = [p for p in ps if p["pos"] == "QB"]
        cnt = lambda pos, upto: sum(1 for p in ps if p["pos"] == pos and p["rd"] <= upto)
        rows.append(dict(
            season=season, fin=t["fin"], w=t["w"], haul=t.get("haul", 0),
            qb_n=len(qbs),
            qb2_rd=qbs[1]["rd"] if len(qbs) > 1 else 99,
            qb_by3=cnt("QB", 3), rb_by9=cnt("RB", 9), wr_by9=cnt("WR", 9),
            te_rd=min([p["rd"] for p in ps if p["pos"] == "TE"], default=99),
            kdef_early=sum(1 for p in ps if p["pos"] in ("K", "DEF") and p["rd"] < 13)))

hdr(f"1. DOES SHAPE PREDICT FINISH?   {len(rows)} team-seasons, "
    f"{D['seasons'][0]}-{D['seasons'][-1]}")
print("  Lower 'finish' is better (1 = won it). Splits with fewer than 8 on a")
print("  side are refused rather than reported.\n")


def split(field, thresh, lo_name, hi_name):
    lo = [r for r in rows if r[field] <= thresh]
    hi = [r for r in rows if r[field] > thresh]
    if min(len(lo), len(hi)) < 8:
        print(f"  {lo_name} vs {hi_name}: REFUSED, n={len(lo)}/{len(hi)}")
        return
    m = lambda g, k: st.mean(x[k] for x in g)
    dw, df = m(lo, "w") - m(hi, "w"), m(lo, "fin") - m(hi, "fin")
    flag = "  <-- LARGE" if abs(dw) >= 1.0 else ""
    print(f"  {lo_name:<32}{m(lo,'w'):>6.2f} w {m(lo,'fin'):>6.2f} fin  n={len(lo)}")
    print(f"  {hi_name:<32}{m(hi,'w'):>6.2f} w {m(hi,'fin'):>6.2f} fin  n={len(hi)}")
    print(f"  {'difference':<32}{dw:>+6.2f} w {df:>+6.2f} fin{flag}\n")


split("qb2_rd", 9, "QB2 by round 9", "QB2 round 10+ or never")
split("qb2_rd", 6, "QB2 by round 6", "QB2 round 7+")
split("qb_by3", 1, "0-1 QB in rounds 1-3", "2+ QB in rounds 1-3")
split("wr_by9", 3, "<=3 WR by round 9", "4+ WR by round 9")
split("kdef_early", 0, "no K/DEF before round 13", "1+ K/DEF before round 13")
split("te_rd", 6, "first TE in rounds 1-6", "first TE round 7+")

print("  QBs rostered:")
for k in sorted({r["qb_n"] for r in rows}):
    g = [r for r in rows if r["qb_n"] == k]
    if len(g) >= 5:
        print(f"    {k} QBs   {st.mean(x['w'] for x in g):>5.2f} w "
              f"{st.mean(x['fin'] for x in g):>5.2f} fin   n={len(g)}")

print("\n  Top-3 finishers against the bottom of the table:")
top = [r for r in rows if r["fin"] <= 3]
bot = [r for r in rows if r["fin"] >= 10]
print(f"    {'':<26}{'top 3':>10}{'10th+':>10}")
for lab, k in (("QB2 taken in round", "qb2_rd"), ("QBs rostered", "qb_n"),
               ("RB by round 9", "rb_by9"), ("WR by round 9", "wr_by9"),
               ("K/DEF before round 13", "kdef_early"), ("drafted points", "haul")):
    f = lambda g: st.mean(min(x[k], 18) if k == "qb2_rd" else x[k] for x in g)
    print(f"    {lab:<26}{f(top):>10.2f}{f(bot):>10.2f}")
print(f"    {'n':<26}{len(top):>10}{len(bot):>10}")

# ---------------------------------------------------------------------------
hdr("2. WHERE EACH POSITION STOPS PAYING, AND THE QUARTERBACK WINDOW")
print("  Startable = finished inside the league-wide starter count at his position.\n")
print(f"  {'pos':>5}" + "".join(f"{b:>9}" for b in D["bands"]))
for row in D["posband"]:
    print(f"  {row['pos']:>5}" + "".join(
        f"{(str(c['st']) + '%' if c['st'] is not None else '-'):>9}" for c in row["cells"]))
print(f"\n  {'':>5}" + "".join(f"{b:>9}" for b in D["bands"]) + "   (picks)")
for row in D["posband"]:
    print(f"  {row['pos']:>5}" + "".join(f"{c['n']:>9}" for c in row["cells"]))

print("\n  QB against the RB/WR/TE taken in the same rounds:")
print(f"  {'band':>8}{'QB':>9}{'skill':>9}{'edge':>9}{'QB n':>7}")
for q in D["qbedge"]:
    print(f"  {q['band']:>8}{q['qb']:>9}{q['flex']:>9}{q['edge']:>+9}{q['qbn']:>7}")

print("\n  Cumulative QBs gone by end of round (24 start weekly):")
print("   " + "  ".join(f"r{i+1}:{v}" for i, v in enumerate(D["qbcum"][:12])))

# ---------------------------------------------------------------------------
hdr("3. DOES FULL PPR WIDEN THE SPREAD, OR JUST RAISE THE LEVEL?")
print("  A bonus applied evenly to every player at a position changes NOTHING about")
print("  what a pick there is worth. Only a widening of elite-minus-replacement does.")
print("  This is a fact about NFL scoring, not about this league, so it runs over all")
print("  nine seasons on record and is checked across windows for stability.\n")

con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
nfl = pd.read_sql("SELECT season, position, games, points, points_ppr, receptions"
                  " FROM final_ranks WHERE games > 0", con)
REPL = {p: int(round(D["need"][p] * 12)) for p in ("QB", "RB", "WR", "TE")}
ELITE = 5

for lo, hi in ((2017, 2025), (2020, 2025), (2023, 2025)):
    d = nfl[(nfl.season >= lo) & (nfl.season <= hi)]
    print(f"  {lo}-{hi} ({d.season.nunique()} seasons)"
          f"   {'half':>10}{'full':>8}{'widens':>9}{'rec gap':>9}")
    for pos, n in REPL.items():
        sh, sf, rg = [], [], []
        for s, g in d[d.position == pos].groupby("season"):
            gh = g.sort_values("points", ascending=False)
            gf = g.sort_values("points_ppr", ascending=False)
            if len(gh) < n:
                continue
            sh.append(gh.points.head(ELITE).mean() - gh.points.iloc[n - 1])
            sf.append(gf.points_ppr.head(ELITE).mean() - gf.points_ppr.iloc[n - 1])
            rg.append(gf.receptions.head(ELITE).mean() - gf.receptions.iloc[n - 1])
        a, b = st.mean(sh), st.mean(sf)
        print(f"    {pos:<3} (repl {pos}{n:<3})        {a:>10.1f}{b:>8.1f}"
              f"{b - a:>+9.1f}{st.mean(rg):>9.1f}")
    print()

print("  Read: full PPR widens the receiver spread roughly twice as hard as the")
print("  running back one and does nothing at all for quarterbacks, because the gap")
print("  in catches between an elite WR and a replacement WR is about twice the gap")
print("  at RB. Stable on 3, 6 and 9 seasons, so it is not a window artefact.")
