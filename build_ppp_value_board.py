"""A Perennial Push board priced on WHAT EACH POSITIONAL SLOT HAS ACTUALLY SCORED.

Jamie's method, 2026-09-04:

  1. ORDERING within a position comes from Underdog, exactly as the existing
     board does -- the settled method, unchanged.
  2. VALUE comes from this league's own history: what the Nth player TAKEN at
     that position actually went on to score, averaged over recent seasons, and
     handed to whoever Underdog has at N. Gibbs is Underdog's RB1, so Gibbs gets
     what the first back off the board has historically returned.

     Jamie's phrasing was "average the RB1s from the last three years". Read
     literally that means the players who FINISHED RB1, which is an order
     statistic nobody can draft -- see the long note at part 1. The version
     implemented here is the same idea aimed at the slot rather than the finish.

WHY THIS IS BETTER THAN WHAT IT REPLACES. The current board carries ESPN's
projection as its value column, and this repo distrusts projections for exactly
the reason PPP-6 keeps demonstrating -- one algorithm is not a market. A
positional-rank average is not a forecast of a player at all. It is the empirical
answer to "what has this slot been worth", which is the only question a draft
board needs, and it is measured in this league's own scored points.

SCORED FROM THE LEAGUE'S OWN DRAFT RECORDS, not from nflverse. Those are already
full PPR under PPP's rules by construction, and unlike nflverse they contain
kickers AND defences, which a board has to price.

THE BOARD RANKS ON VALUE OVER REPLACEMENT, not on raw points. Ranking on raw
points would put twenty quarterbacks on top: in a superflex league they score
most, and most of it is available for free from the 24th one. Replacement levels
are the realised, flex-aware ones from PPP-7.

Run:
    python build_ppp_value_board.py        # writes cleandata/analysis/ppp_value_board.csv
"""
import json
import os
import statistics as st

import pandas as pd
from collections import defaultdict

from sklearn.isotonic import IsotonicRegression

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "rawdata", "ppp")
OUT = os.path.join(ROOT, "cleandata", "analysis")
# FIVE seasons, not the three Jamie specified, and the reason is sample size:
# each rank gets ONE observation per season, so three seasons cannot separate
# RB1 from RB3 and the monotone fit collapses the top of every position into a
# tie. Five resolves quarterback and receiver cleanly. (The pick curve elsewhere
# uses three because a room's PRICES are smooth; scored POINTS are not.)
VALUE_SEASONS = [2021, 2022, 2023, 2024, 2025]
SMOOTH = 5                                  # ranks either side, before the monotone fit
TEAMS = 12

# Realised, flex-aware replacement (PPP-7). The flex is what makes RB and WR
# replacement deeper than the dedicated slots alone would imply.
REPLACEMENT_RANK = {"QB": 24, "RB": 29, "WR": 42, "TE": 12, "K": 12, "DEF": 12}

# ---- 1. what each positional slot has actually RETURNED ---------------------
#
# THE SLOT IS DEFINED BY WHERE HE WAS DRAFTED, NOT WHERE HE FINISHED, and the
# difference is the whole correctness of this file.
#
# Averaging the players who FINISHED Nth at a position gives an order statistic:
# the luckiest of that year's contenders. Nobody can draft it. Over 2023-25 the
# back who finished RB1 averaged 390.3 points while the back actually taken first
# averaged 223.8 -- a 166-point gap, and similar gaps sit at the top of every
# position. Handing the finisher's number to a preseason favourite would overstate
# the top of the board by more than a round of value.
#
# So the value of "the Nth back" is what the Nth back TAKEN went on to score. That
# is the empirical answer to "what has this slot been worth to the person who
# spent the pick", and it prices in how predictable the position is for free --
# which matters, because draft order predicts finish at rho 0.60 for backs and
# 0.04 for defences.
by_rank = defaultdict(list)
for y in VALUE_SEASONS:
    pos_picks = defaultdict(list)
    for line in open(os.path.join(SRC, f"draft{y}.psv"), encoding="utf-8"):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("|")
        if f[8]:
            pos_picks[f[7]].append((int(f[0]), float(f[8])))
    for pos, vals in pos_picks.items():
        for i, (_, pts) in enumerate(sorted(vals), start=1):     # sorted by pick
            by_rank[(pos, i)].append(pts)

# One observation per rank per season, so the raw curve is not monotone -- QB5 came
# in under QB8. Smooth over neighbouring ranks, then force it monotone with
# IsotonicRegression, never a running extremum (trap 9).
#
# RUNNING BACK STAYS FLAT ACROSS THE TOP AND THAT IS NOT THE SMOOTHER. It survives
# every window and season count tried: the first five backs taken have returned
# about the same on average. Which agrees with PPP-3 (85% of rounds 1-3 backs
# finish startable) and with PPP-6 (reaching at running back cost ~40 points).
# AND THE CURVE ONLY DIFFERENTIATES WHERE THE ORDER PREDICTS ANYTHING.
#
# Draft order within a position predicts the finish at rho 0.60 for backs and
# 0.58 for receivers -- real signal, so a downward curve is earned. At kicker it
# is 0.12 and at defence 0.04: knowing a defence was taken first tells you
# essentially nothing about how it finished. Fitting a curve there dresses noise
# up as information, and the first version of this file did exactly that and put
# the Texans defence at pick 42.
#
# So each position's rho is measured here, and anything below MIN_RHO is FLATTENED
# to the position's mean -- every kicker worth the same, every defence worth the
# same, which is the honest expected value when the ordering carries no signal.
# They then fall to the end of the board on their own, with no rule telling them
# to, which is what PPP-3 says the room should do anyway.
MIN_RHO = 0.25
rho = {}
for pos in {k[0] for k in by_rank}:
    pairs = []
    for (p, r), vals in by_rank.items():
        if p == pos:
            pairs += [(r, v) for v in vals]
    if len(pairs) > 20:
        dr = pd.Series([x[0] for x in pairs]).rank()
        fr = pd.Series([-x[1] for x in pairs]).rank()
        rho[pos] = dr.corr(fr, method="spearman")

slot_value = {}
depth = defaultdict(int)
for pos in {k[0] for k in by_rank}:
    ranks = sorted(r for (p, r) in by_rank if p == pos
                   and len(by_rank[(p, r)]) >= len(VALUE_SEASONS) - 1)
    if not ranks:
        continue
    raw = [st.mean(by_rank[(pos, r)]) for r in ranks]
    if rho.get(pos, 0) < MIN_RHO:
        flat = round(st.mean(raw), 1)
        fit = [flat] * len(ranks)
    else:
        h = SMOOTH // 2
        sm = [st.mean(raw[max(0, i - h):i + h + 1]) for i in range(len(raw))]
        fit = IsotonicRegression(increasing=False, y_min=0).fit_transform(ranks, sm)
    for r, v in zip(ranks, fit):
        slot_value[(pos, r)] = round(float(v), 1)
    depth[pos] = max(ranks)

print("\nHOW MUCH DOES DRAFT ORDER PREDICT THE FINISH, BY POSITION?")
for p in ("QB", "RB", "WR", "TE", "K", "DEF"):
    if p in rho:
        note = "curve fitted" if rho[p] >= MIN_RHO else "FLATTENED -- no signal to fit"
        print(f"    {p:>4}  rho {rho[p]:>5.2f}   {note}")


def value_at(pos, rank):
    """The slot's worth, holding the last observed value once the pool runs out."""
    if (pos, rank) in slot_value:
        return slot_value[(pos, rank)]
    d = depth.get(pos, 0)
    return slot_value.get((pos, d), 0.0) if d else 0.0


# ---- 2. the ordering, which is Underdog's (K/DEF from ESPN) -----------------
D = json.load(open(os.path.join(OUT, "ppp_data.json"), encoding="utf-8"))
board = []
for p in D["board"]:
    pos, prank = p["pos"], p["prank"]
    proj = value_at(pos, prank)
    repl = value_at(pos, REPLACEMENT_RANK.get(pos, 12))
    board.append(dict(
        name=p["n"], pos=pos, prank=prank, team=p["tm"], key=p["key"], pid=p["pid"],
        src=p["src"], proj=proj, repl=repl, vor=round(proj - repl, 1),
        espn_exp=p["exp"], old_rank=p["rank"]))

board.sort(key=lambda r: -r["vor"])
for i, r in enumerate(board, 1):
    r["rank"] = i
    r["rd"] = (i - 1) // TEAMS + 1
    r["pk"] = (i - 1) % TEAMS + 1
    r["move"] = (r["old_rank"] - i) if r["old_rank"] else None

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "ppp_value_board.csv")
cols = ["rank", "rd", "pk", "name", "pos", "prank", "team", "proj", "repl", "vor",
        "src", "espn_exp", "old_rank", "move", "key", "pid"]
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(",".join(cols) + "\n")
    for r in board:
        f.write(",".join('"%s"' % r[c] if c in ("name",) else str(r.get(c, ""))
                         for c in cols) + "\n")

print(f"\n\nTHE BOARD -- ranked by value over replacement, top 48\n")
print(f"{'#':>3}{'rd.pk':>7}  {'player':<24}{'pos':>5}{'proj':>8}{'repl':>7}{'VOR':>8}"
      f"{'vs old':>8}")
for r in board[:48]:
    mv = f"{r['move']:+d}" if r["move"] is not None else "-"
    slot = f"{r['rd']}.{r['pk']:02d}"
    print(f"{r['rank']:>3}{slot:>7}  {r['name']:<24}{r['pos'] + str(r['prank']):>5}"
          f"{r['proj']:>8.1f}{r['repl']:>7.1f}{r['vor']:>8.1f}{mv:>8}")

print(f"\nwrote {path}  ({len(board)} players)")
mix = defaultdict(int)
for r in board[:36]:
    mix[r["pos"]] += 1
print("first three rounds by position: " + "  ".join(f"{k} {mix[k]}" for k in
      ("QB", "RB", "WR", "TE") if mix[k]))
