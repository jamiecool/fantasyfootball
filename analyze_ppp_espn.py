"""How closely does Perennial Push draft to ESPN's order, within each position?

WHAT THIS USES, AND WHAT IT IS NOT. ESPN's published default RANK LIST for a past
preseason is not in this repo and is not retrievable now -- ESPN serves the
current season's ranks, and both board snapshots on disk are 2026. What IS on
disk is ESPN's preseason PROJECTION for every drafted player, carried in the
draft files, and those are demonstrably preseason rather than retro-fitted:
actual points come in at 0.81-0.91 of projection every season, where anything
fitted after the fact would sit at 1.00.

So players are ranked within position by ESPN's projected points and compared to
the order the room actually took them. That is ESPN's opinion of who is better at
each position, which is what a within-position question needs -- but it is a
SUBSTITUTE for the rank list, not the rank list. Swapping in the real one would
be a refinement, not a correction.

WITHIN POSITION IS THE ONLY FAIR COMPARISON. This league is superflex and ESPN's
default board is built for one quarterback, so comparing overall order would
mostly re-measure that known mismatch (PPP-3) rather than the room's judgement.

2023 is excluded: ESPN did not retain those projections and only 37 of 216 picks
carry one.

Run:
    python analyze_ppp_espn.py
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "rawdata", "ppp")
SEASONS = [2021, 2022, 2024, 2025]
POS = ["QB", "RB", "WR", "TE"]
BAR = "=" * 76

rows = []
for y in SEASONS:
    for line in open(os.path.join(SRC, f"draft{y}.psv"), encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("|")
        if f[7] in POS and f[9] and float(f[9]) > 5 and f[8]:
            rows.append(dict(season=y, overall=int(f[0]), rd=int(f[1]), name=f[6],
                             pos=f[7], act=float(f[8]), proj=float(f[9])))
d = pd.DataFrame(rows)
d["espn_rk"] = d.groupby(["season", "pos"])["proj"].rank(ascending=False, method="first")
d["draft_rk"] = d.groupby(["season", "pos"])["overall"].rank(method="first")
d["gap"] = d["espn_rk"] - d["draft_rk"]          # positive = room took him EARLIER

print(f"\n{BAR}\n  AGREEMENT WITH ESPN, WITHIN POSITION\n{BAR}")
print("  Spearman between ESPN's projected order and the order taken.")
print("  1.00 would be drafting straight down ESPN's list at that position.\n")
print(f"{'season':>8}" + "".join(f"{p:>9}" for p in POS) + f"{'all':>9}")
for y in SEASONS + ["ALL"]:
    g0 = d if y == "ALL" else d[d.season == y]
    line = f"{str(y):>8}"
    for p in POS:
        g = g0[g0.pos == p]
        line += (f"{g.espn_rk.corr(g.draft_rk, method='spearman'):>9.2f}"
                 if len(g) > 4 else f"{'-':>9}")
    print(line + f"{g0.espn_rk.corr(g0.draft_rk, method='spearman'):>9.2f}")

print(f"\n\n{BAR}\n  HOW FAR OFF, IN PLACES AT THE POSITION\n{BAR}")
print(f"{'pos':>5}{'n':>6}{'mean |gap|':>12}{'median':>9}{'within 3':>10}{'within 5':>10}")
for p in POS:
    a = d[d.pos == p].gap.abs()
    print(f"{p:>5}{len(a):>6}{a.mean():>12.1f}{a.median():>9.1f}"
          f"{(a <= 3).mean()*100:>9.0f}%{(a <= 5).mean()*100:>9.0f}%")

print(f"\n\n{BAR}\n  DID DEVIATING FROM ESPN PAY?\n{BAR}")
print("  Measured against THE ROUND the pick was taken in, which is the only")
print("  honest yardstick: a reach is by definition an earlier pick, so scoring")
print("  it against the position's overall mean rewards it for the very thing")
print("  under test. Doing that flattered agreement by ~20 points a pick and")
print("  reversed the sign on fading -- see the second table.\n")
d["vs_round"] = d.act - d.groupby(["season", "rd"])["act"].transform("mean")
d["vs_pos"] = d.act - d.groupby(["season", "pos"])["act"].transform("mean")


def split(g, col):
    e, s, l = g[g.gap >= 5], g[g.gap.abs() < 5], g[g.gap <= -5]
    f = lambda x: f"{x[col].mean():+7.1f} (n={len(x):>3})" if len(x) else f"{'-':>15}"
    return f(e), f(s), f(l)


for label, col in (("against the round taken", "vs_round"),
                   ("against the position mean (the flawed one)", "vs_pos")):
    print(f"  {label}")
    print(f"{'pos':>5}{'reached 5+':>20}{'agreed':>20}{'faded 5+':>20}")
    for p in POS + ["ALL"]:
        g = d if p == "ALL" else d[d.pos == p]
        e, s, l = split(g, col)
        print(f"{p:>5}{e:>20}{s:>20}{l:>20}")
    print()

print(f"\n{BAR}\n  2025 -- BIGGEST DISAGREEMENTS\n{BAR}")
d25 = d[d.season == 2025]
for lab, sub in (("REACHES -- taken far earlier than ESPN had him",
                  d25.nlargest(8, "gap")),
                 ("FALLS -- let slide well past ESPN's rank",
                  d25.nsmallest(8, "gap"))):
    print(f"\n  {lab}")
    for r in sub.itertuples():
        print(f"    {r.name:<23}{r.pos}  ESPN {r.pos}{int(r.espn_rk):<3}"
              f" -> taken {r.pos}{int(r.draft_rk):<3} at pick {r.overall:<4}"
              f"({r.gap:+3.0f})   finished {r.act:>5.0f} pts")
