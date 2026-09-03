"""RB or WR in the Perennial Push flex? -> in full PPR it is a non-decision.

PPP starts 2 RB, 3 WR, 1 TE and one FLEX across 12 teams, so the dedicated slots
consume 24 RB, 36 WR and 12 TE before the flex chooses anything. The question is
therefore never "is an elite back better than an elite receiver" -- it is about
RB25 against WR37, and how that holds as the pool thins.

Everything is scored under FULL PPR, which is this league's format. The answer is
sensitive to that: half-PPR moves it by ten points a season, which is why this
finding explicitly does NOT transfer to PBAFFL.

Run:
    python analyze_ppp_flex.py

Uses final_ranks and player_weeks (nflverse, 2017-2025) rather than PPP's own
draft data, because the question is about the NFL's supply of flex-quality
players, not about what this room happened to draft.
"""
import os
import sqlite3
import statistics as st

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
TEAMS = 12
# what the dedicated slots consume before the flex chooses anything
DEDICATED = {"RB": 2 * TEAMS, "WR": 3 * TEAMS, "TE": 1 * TEAMS}
# ...so the flex pool starts here, and runs DEPTH deep (one per team)
START = {p: n + 1 for p, n in DEDICATED.items()}
DEPTH = TEAMS
BAR = "=" * 74


def hdr(t):
    print(f"\n{BAR}\n  {t}\n{BAR}")


nfl = pd.read_sql(
    "SELECT season, player_key, player_name, position, games, points_ppr, receptions"
    " FROM final_ranks WHERE games > 0 AND position IN ('RB','WR','TE')", con)

# rank within position under FULL PPR, per season
nfl["prank"] = (nfl.groupby(["season", "position"])["points_ppr"]
                .rank(ascending=False, method="first").astype(int))
SEASONS = sorted(nfl.season.unique())

hdr(f"1. THE FLEX POOL: what is left once the dedicated slots are full "
    f"({SEASONS[0]}-{SEASONS[-1]})")
print("  Mean points of the first players available to the flex, by position.\n")
print(f"{'':>6}{'the flex-eligible player':>26}{'mean':>9}{'median':>9}{'p25':>8}{'p75':>8}")
pool = {}
for pos, start in (("RB", DEDICATED["RB"] + 1), ("WR", DEDICATED["WR"] + 1),
                   ("TE", DEDICATED["TE"] + 1)):
    for off, lab in ((0, "1st"), (5, "6th"), (11, "12th")):
        r = start + off
        v = nfl[(nfl.position == pos) & (nfl.prank == r)].points_ppr
        if off == 0:
            pool[pos] = []
        if len(v):
            tag = f"{pos}{r} ({lab} available)"
            print(f"{'':>6}{tag:>26}{v.mean():>9.1f}{v.median():>9.1f}"
                  f"{v.quantile(.25):>8.1f}{v.quantile(.75):>8.1f}")
    print()

hdr("2. IF YOU FILLED ALL TWELVE FLEX SPOTS WITH THE BEST AVAILABLE")
print("  Take the 12 highest scorers left after the dedicated slots, each season,")
print("  and count what position they were. This is the answer to the question as")
print("  asked: with a free choice, what does the flex actually end up being?\n")
print(f"{'season':>8}{'RB':>6}{'WR':>6}{'TE':>6}   {'mean pts of the twelve':>24}")
tot = {"RB": 0, "WR": 0, "TE": 0}
for s in SEASONS:
    d = nfl[nfl.season == s]
    elig = d[((d.position == "RB") & (d.prank > DEDICATED["RB"]))
             | ((d.position == "WR") & (d.prank > DEDICATED["WR"]))
             | ((d.position == "TE") & (d.prank > DEDICATED["TE"]))]
    top = elig.nlargest(12, "points_ppr")
    c = top.position.value_counts()
    for k in tot:
        tot[k] += int(c.get(k, 0))
    print(f"{s:>8}{c.get('RB',0):>6}{c.get('WR',0):>6}{c.get('TE',0):>6}"
          f"{top.points_ppr.mean():>28.1f}")
n = sum(tot.values())
print(f"\n{'TOTAL':>8}{tot['RB']:>6}{tot['WR']:>6}{tot['TE']:>6}"
      f"      -> RB {100*tot['RB']/n:.0f}%  WR {100*tot['WR']/n:.0f}%  TE {100*tot['TE']/n:.0f}%")

hdr("3. HEAD TO HEAD AT THE MARGIN: RB25+ against WR37+")
print("  Same rank offset into each pool, so it is like for like.\n")
print(f"{'offset':>8}{'RB':>10}{'WR':>10}{'WR - RB':>10}{'WR wins':>10}")
for off in range(0, 12):
    rb = nfl[(nfl.position == "RB") & (nfl.prank == DEDICATED["RB"] + 1 + off)]
    wr = nfl[(nfl.position == "WR") & (nfl.prank == DEDICATED["WR"] + 1 + off)]
    m = rb.merge(wr, on="season", suffixes=("_rb", "_wr"))
    if not len(m):
        continue
    wins = (m.points_ppr_wr > m.points_ppr_rb).mean() * 100
    print(f"{off + 1:>8}{m.points_ppr_rb.mean():>10.1f}{m.points_ppr_wr.mean():>10.1f}"
          f"{m.points_ppr_wr.mean() - m.points_ppr_rb.mean():>+10.1f}{wins:>9.0f}%")

hdr("4. WOULD HALF-PPR CHANGE THE ANSWER? (i.e. does this transfer to PBAFFL)")
nfl2 = pd.read_sql(
    "SELECT season, position, games, points, points_ppr FROM final_ranks"
    " WHERE games > 0 AND position IN ('RB','WR','TE')", con)
for scoring, col in (("full PPR", "points_ppr"), ("half-PPR", "points")):
    nfl2["r"] = (nfl2.groupby(["season", "position"])[col]
                 .rank(ascending=False, method="first").astype(int))
    rb = nfl2[(nfl2.position == "RB") & (nfl2.r.between(25, 36))][col].mean()
    wr = nfl2[(nfl2.position == "WR") & (nfl2.r.between(37, 48))][col].mean()
    te = nfl2[(nfl2.position == "TE") & (nfl2.r.between(13, 24))][col].mean()
    print(f"  {scoring:>9}:  flex-pool RB {rb:6.1f}   WR {wr:6.1f}   TE {te:6.1f}"
          f"   -> {'WR' if wr > rb else 'RB'} by {abs(wr-rb):.1f}")


fr = pd.read_sql(
    "SELECT season, player_key, position, games, points_ppr FROM final_ranks"
    " WHERE games > 0 AND position IN ('RB','WR','TE')", con)
fr["prank"] = (fr.groupby(["season", "position"])["points_ppr"]
               .rank(ascending=False, method="first").astype(int))
pool = fr[[(r.position in START and START[r.position] <= r.prank
            < START[r.position] + DEPTH) for r in fr.itertuples()]]

pw = pd.read_sql("SELECT season, player_key, position, week, points, rec"
                 " FROM player_weeks WHERE position IN ('RB','WR','TE')", con)
pw["ppr"] = pw["points"] + 0.5 * pw["rec"]          # half-PPR stored -> full PPR
w = pw.merge(pool[["season", "player_key", "prank"]], on=["season", "player_key"])
w = w[w.week <= 17]

print(f"{len(w):,} player-weeks from the flex pool, "
      f"{w.season.min()}-{w.season.max()}\n")
print(f"{'pos':>5}{'n weeks':>9}{'mean':>8}{'median':>8}{'p10':>7}{'p25':>7}"
      f"{'p75':>7}{'p90':>7}{'<5 pts':>9}{'20+ pts':>9}")
for pos in ("RB", "WR", "TE"):
    d = w[w.position == pos].ppr
    if not len(d):
        continue
    print(f"{pos:>5}{len(d):>9,}{d.mean():>8.1f}{d.median():>8.1f}"
          f"{d.quantile(.10):>7.1f}{d.quantile(.25):>7.1f}"
          f"{d.quantile(.75):>7.1f}{d.quantile(.90):>7.1f}"
          f"{(d < 5).mean()*100:>8.0f}%{(d >= 20).mean()*100:>8.0f}%")

print("\nSAME THING UNDER HALF-PPR, which is PBAFFL's scoring:")
print(f"{'pos':>5}{'mean':>8}{'median':>8}{'<5 pts':>9}{'20+ pts':>9}")
for pos in ("RB", "WR", "TE"):
    d = w[w.position == pos].points
    if len(d):
        print(f"{pos:>5}{d.mean():>8.1f}{d.median():>8.1f}"
              f"{(d < 5).mean()*100:>8.0f}%{(d >= 20).mean()*100:>8.0f}%")

print("\n\nTHE ZERO PROBLEM: how often does a flex player not play at all?")
print("A bye or an injury in your flex is a zero you cannot always cover.")
gp = (fr[[(r.position in START and START[r.position] <= r.prank
           < START[r.position] + DEPTH) for r in fr.itertuples()]]
      .groupby("position")["games"].agg(["mean", "count"]))
for pos in ("RB", "WR", "TE"):
    if pos in gp.index:
        print(f"  {pos}: {gp.loc[pos,'mean']:.1f} games played on average "
              f"(n={int(gp.loc[pos,'count'])} player-seasons)")

print("\n\nWEEK BY WEEK, WHICH POSITION WON THE FLEX?")
print("For each season-week, the best available RB against the best available WR")
print("from the pool -- i.e. if you had one of each on your bench, who to start.\n")
best = (w.groupby(["season", "week", "position"])["ppr"].max().unstack())
if "RB" in best and "WR" in best:
    b = best.dropna(subset=["RB", "WR"])
    print(f"  RB was the better start in {(b.RB > b.WR).mean()*100:.0f}% of "
          f"{len(b)} season-weeks")
    print(f"  mean margin when RB won: {(b.RB - b.WR)[b.RB > b.WR].mean():.1f} pts")
    print(f"  mean margin when WR won: {(b.WR - b.RB)[b.WR > b.RB].mean():.1f} pts")
    print(f"  overall mean difference (RB - WR): {(b.RB - b.WR).mean():+.2f} pts a week")
