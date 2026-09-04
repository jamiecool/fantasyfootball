"""What does the FLEX slot do to relative positional value in a superflex league?

Perennial Push starts 1 QB / 2 RB / 3 WR / 1 TE / 1 SUPERFLEX / 1 FLEX / K / DEF.
Strip the FLEX and you have what most people mean by "a superflex league": the
same roster one starter shorter.

THE ONLY THING THE FLEX DOES IS DEEPEN DEMAND at RB/WR/TE. With 12 teams it adds
twelve more skill starters, which pushes each affected position's replacement
level further down its own curve. Value over replacement rises by exactly the
amount replacement falls -- for everyone at that position, elite and marginal
alike -- so the flex is a uniform transfer of value TOWARD the positions that can
fill it and away from the one that cannot.

Quarterback cannot fill it (a superflex slot already exists and is separate), so
QB is the position that pays for the flex.

Who actually fills the twelve flex spots is MEASURED, not assumed: take the best
available across RB25+/WR37+/TE13+ each season and count. That is the same method
as PPP-5, which found the split runs RB 45% / WR 53% / TE 2%.

Scored full PPR, this league's format, 2017-2025 nflverse.

Run:
    python analyze_ppp_flexvalue.py
"""
import os
import sqlite3

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
TEAMS = 12
BAR = "=" * 76

# starters per team WITHOUT the flex -- "a normal superflex league"
BASE = {"QB": 2, "RB": 2, "WR": 3, "TE": 1}      # QB 2 = the superflex slot
ELITE = 5

nfl = pd.read_sql(
    "SELECT season, player_key, player_name, position, games, points_ppr"
    " FROM final_ranks WHERE games > 0 AND position IN ('QB','RB','WR','TE')", con)
nfl["prank"] = (nfl.groupby(["season", "position"])["points_ppr"]
                .rank(ascending=False, method="first").astype(int))
SEASONS = sorted(nfl.season.unique())

# ---- who fills the flex, measured season by season ------------------------
fill = {"RB": 0, "WR": 0, "TE": 0}
for s in SEASONS:
    d = nfl[nfl.season == s]
    elig = pd.concat([d[(d.position == p) & (d.prank > BASE[p] * TEAMS)]
                      for p in ("RB", "WR", "TE")])
    for p, c in elig.nlargest(TEAMS, "points_ppr").position.value_counts().items():
        fill[p] += int(c)
n = sum(fill.values())
per_team = {p: fill[p] / len(SEASONS) / TEAMS for p in fill}

print(f"\n{BAR}\n  WHO ACTUALLY FILLS THE FLEX ({SEASONS[0]}-{SEASONS[-1]})\n{BAR}")
for p in ("RB", "WR", "TE"):
    print(f"  {p}: {fill[p]:>3} of {n} flex spots ({100*fill[p]/n:>4.1f}%)"
          f"  -> {per_team[p]:.2f} extra starters per team")

WITH = {p: BASE[p] + per_team.get(p, 0) for p in BASE}

print(f"\n\n{BAR}\n  WHAT THAT DOES TO REPLACEMENT LEVEL\n{BAR}")
print("  Replacement = the last player who starts league-wide at that position.\n")
print(f"{'pos':>5}{'no flex':>22}{'with flex':>22}{'replacement falls':>20}")


def repl(pos, per_team_n, season):
    d = nfl[(nfl.season == season) & (nfl.position == pos)].sort_values(
        "points_ppr", ascending=False)
    i = int(round(per_team_n * TEAMS)) - 1
    return d.points_ppr.iloc[i] if len(d) > i else None


drop = {}
for pos in ("QB", "RB", "WR", "TE"):
    a = [repl(pos, BASE[pos], s) for s in SEASONS]
    b = [repl(pos, WITH[pos], s) for s in SEASONS]
    a = [v for v in a if v is not None]
    b = [v for v in b if v is not None]
    ma, mb = sum(a)/len(a), sum(b)/len(b)
    drop[pos] = ma - mb
    print(f"{pos:>5}{f'{pos}{int(BASE[pos]*TEAMS)} = {ma:.1f}':>22}"
          f"{f'{pos}{int(round(WITH[pos]*TEAMS))} = {mb:.1f}':>22}{ma-mb:>19.1f}")

print("\n  A position's value over replacement rises by exactly the amount its")
print("  replacement level falls -- for every player at that position at once.")

print(f"\n\n{BAR}\n  THE RESULT: WHAT THE FLEX IS WORTH, BY POSITION\n{BAR}")
print("  Value over replacement for a top-5 player, with and without the flex.\n")
print(f"{'pos':>5}{'elite pts':>11}{'VOR no flex':>13}{'VOR with flex':>15}"
      f"{'gain':>8}{'gain %':>9}")
rows = []
for pos in ("QB", "RB", "WR", "TE"):
    el = []
    for s in SEASONS:
        d = nfl[(nfl.season == s) & (nfl.position == pos)]
        el.append(d.nlargest(ELITE, "points_ppr").points_ppr.mean())
    e = sum(el)/len(el)
    a = [repl(pos, BASE[pos], s) for s in SEASONS]
    ra = sum(v for v in a if v is not None)/len([v for v in a if v is not None])
    vor_a, vor_b = e - ra, e - (ra - drop[pos])
    rows.append((pos, e, vor_a, vor_b, vor_b - vor_a))
    print(f"{pos:>5}{e:>11.1f}{vor_a:>13.1f}{vor_b:>15.1f}"
          f"{vor_b-vor_a:>8.1f}{100*(vor_b-vor_a)/vor_a:>8.1f}%")

print("\n  RELATIVE standing -- each position's share of the total elite VOR,")
print("  which is what actually decides who gets drafted before whom:\n")
ta = sum(r[2] for r in rows)
tb = sum(r[3] for r in rows)
print(f"{'pos':>5}{'no flex':>12}{'with flex':>12}{'shift':>10}")
for pos, e, va, vb, g in rows:
    print(f"{pos:>5}{100*va/ta:>11.1f}%{100*vb/tb:>11.1f}%{100*vb/tb - 100*va/ta:>+9.1f}")
