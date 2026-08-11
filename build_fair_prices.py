"""What each player SHOULD cost, given what his price band has actually returned.

Two different numbers, and keeping them apart is the whole point:

  est_price   what the room will pay. Underdog ordering, priced on PBAFFL's own
              positional curves. This is a forecast of behaviour.
  fair_price  what he is worth, if every dollar in the draft bought the same
              amount of production above replacement. This is a valuation.

The gap between them is the edge. Where fair sits above market, the room is
systematically underpaying for that slice of the board; where it sits below, the
room is overpaying, which is exactly what the dead-zone bands are.

METHOD, and the trap it is avoiding:

Allocating the $2,400 pool in proportion to points above replacement is textbook
VBD, and this project already REJECTED that (rule 15) because it assumes roster
spots are free. With 16 of them at 12 teams, 192 players must be bought, so the
first $192 of the pool is not allocatable at all -- every team has to fill its
bench regardless. So:

    fair = $1 + (pool - 192) x (a player's expected PAR / all expected PAR)

which is VBD *after* paying for the spots. That single correction is what stops
it from manufacturing $90 studs the way the rejected version did.

Expected PAR comes from an isotonic fit of PAR against price, per position, over
THE SAME 2023-25 WINDOW build_2026_board.py prices on. Valuing on nine seasons
while pricing on three meant the two halves of the board described different
markets -- RB returned under 1.0 for seven straight seasons then flipped to 1.01
and 1.08 in 2024-25, so the long window docked every RB for a market that has
moved on. Isotonic rather than raw cells for the usual reason: the top of the
board rests on a handful of picks.

Run:  python build_fair_prices.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata", "analysis")
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))

TEAMS, SPOTS, BUDGET = 12, 16, 200
POOL = TEAMS * BUDGET                 # 2400
DRAFTED = TEAMS * SPOTS               # 192
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}

# ------------------------------------------------- expected PAR against price
p = pd.read_sql("""
    SELECT d.season, d.position, d.price, COALESCE(f.points, 0) pts
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season = d.season AND f.player_key = d.player_key
""", con)
fr = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)
repl = {}
for (s, pos), g in fr.groupby(["season", "position"]):
    if pos in SLOTS:
        n = (10 if s == 2020 else 12) * SLOTS[pos]
        row = g[g.pos_rank == n]
        repl[(s, pos)] = row.points.iloc[0] if len(row) else 0
p["par"] = [max(0.0, x.pts - repl.get((x.season, x.position), 0)) for x in p.itertuples()]

# SAME WINDOW AS THE PRICE CURVE. build_2026_board.py fits est_price on 2023-25
# only, because the positional market has moved -- RB fell from 48.6% of spend
# in 2020 to 35.8% in 2024. Valuing on nine seasons while pricing on three meant
# the two halves of the board were describing different markets, and it showed:
# RB returned below 1.0 for seven straight seasons and then flipped to 1.01 and
# 1.08 in 2024-25, so the long window was docking every RB for a market that no
# longer exists.
PAR_SEASONS = (2023, 2025)
full = p
p = p[p.season.between(*PAR_SEASONS)].copy()
print(f"fitting PAR on {PAR_SEASONS[0]}-{PAR_SEASONS[1]} to match the price curve "
      f"({len(p)} picks of {len(full)})")
_thin = [pos for pos, g in p.groupby("position") if len(g) < 40]
if _thin:
    print(f"  thin after the cut, treat their curves with suspicion: {_thin}")

CURVE = {}
for pos, sub in p.groupby("position"):
    if len(sub) < 25 or sub.price.nunique() < 4:
        CURVE[pos] = (lambda v, m=float(sub.par.mean()): np.full(len(np.atleast_1d(v)), m))
        continue
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
    iso.fit(sub.price.to_numpy(float), sub.par.to_numpy(float))
    CURVE[pos] = iso.predict

print("expected PAR at each price, fitted over the matched window:")
pts = (1, 3, 8, 15, 25, 40, 60)
print("  " + " " * 5 + "".join("%8s" % ("$" + str(v)) for v in pts))
for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    if pos in CURVE:
        print("  %-5s" % pos + "".join("%8.0f" % CURVE[pos]([v])[0] for v in pts))

# ------------------------------------------------------------ price the board
board = pd.read_csv(os.path.join(OUT, "board_2026.csv"))
board["est_price"] = board["est_price"].clip(lower=1).astype(int)
board = board.sort_values("est_price", ascending=False).reset_index(drop=True)

# Only the players who will actually be bought get a share of the pool. Beyond
# 192 there is no money left to allocate -- those are $1 flyers by definition.
board["draftable"] = board.index < DRAFTED
board["exp_par"] = [float(CURVE.get(r.position, CURVE["WR"])([r.est_price])[0])
                    for r in board.itertuples()]
board.loc[~board["draftable"], "exp_par"] = 0.0

# nflverse has no team-defence stat lines, so DEF has no PAR at any price. That
# is missing data, not evidence of worthlessness -- repricing it to $1 would be
# inventing a finding. Hold DEF at market and take it out of the allocation.
NO_DATA = board["position"] == "DEF"
held = int(board.loc[NO_DATA & board["draftable"], "est_price"].sum())

surplus = POOL - DRAFTED - held               # what is left to allocate on evidence
tot = board.loc[board["draftable"] & ~NO_DATA, "exp_par"].sum()
board["fair_price"] = (1 + surplus * board["exp_par"] / tot).round(0).astype(int)
board.loc[~board["draftable"], "fair_price"] = 1
board.loc[NO_DATA, "fair_price"] = board.loc[NO_DATA, "est_price"]
print(f"\n  DEF held at market (${held} across "
      f"{int((NO_DATA & board['draftable']).sum())} defences) -- no outcome data exists")
board["fair_gap"] = board["fair_price"] - board["est_price"]

chk = board.loc[board["draftable"], "fair_price"].sum()
print(f"\nfair prices sum to ${chk:,} against a ${POOL:,} pool "
      f"({100 * chk / POOL:.0f}%); market prices sum to "
      f"${board.loc[board['draftable'], 'est_price'].sum():,}")

# what the window change costs or gives back, position by position
_alt = {}
for pos, sub in full.groupby("position"):
    if len(sub) >= 25 and sub.price.nunique() >= 4:
        _i = IsotonicRegression(increasing=True, out_of_bounds="clip")
        _i.fit(sub.price.to_numpy(float), sub.par.to_numpy(float))
        _alt[pos] = _i.predict
board["par_9yr"] = [float(_alt[r.position]([r.est_price])[0]) if r.position in _alt
                    else 0.0 for r in board.itertuples()]
board.loc[~board["draftable"] | NO_DATA, "par_9yr"] = 0.0
_t9 = board.loc[board["draftable"] & ~NO_DATA, "par_9yr"].sum()
board["fair_9yr"] = (1 + surplus * board["par_9yr"] / _t9).round(0).astype(int)
board.loc[NO_DATA, "fair_9yr"] = board.loc[NO_DATA, "est_price"]
_cmp = board[board.draftable].groupby("position").agg(
    market=("est_price", "sum"), nine=("fair_9yr", "sum"), three=("fair_price", "sum"))
_cmp["9yr vs mkt"] = (_cmp.nine - _cmp.market).astype(int)
_cmp["3yr vs mkt"] = (_cmp.three - _cmp.market).astype(int)
print("\n" + "=" * 76)
print("WHAT MATCHING THE WINDOW CHANGED, by position")
print("=" * 76)
print(_cmp[["market", "9yr vs mkt", "3yr vs mkt"]].to_string())

cols = ["player_key", "player_name", "position", "nfl_team", "est_price",
        "fair_price", "fair_gap", "exp_par", "draftable"]
board[cols].to_csv(os.path.join(OUT, "fair_prices_2026.csv"), index=False)

print("\n" + "=" * 76)
print("THE ROOM IS OVERPAYING MOST FOR THESE")
print("=" * 76)
print(board.nsmallest(12, "fair_gap")[
    ["player_name", "position", "nfl_team", "est_price", "fair_price", "fair_gap"]
].to_string(index=False))
print("\n" + "=" * 76)
print("AND UNDERPAYING MOST FOR THESE")
print("=" * 76)
print(board[board.draftable].nlargest(12, "fair_gap")[
    ["player_name", "position", "nfl_team", "est_price", "fair_price", "fair_gap"]
].to_string(index=False))

print("\n" + "=" * 76)
print("WHERE THE MONEY MOVES, BY POSITION AND BAND")
print("=" * 76)
d = board[board.draftable].copy()
d["band"] = pd.cut(d.est_price, [0, 2, 5, 10, 20, 35, 200],
                   labels=["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"])
g = d.groupby(["position", "band"], observed=True).agg(
    n=("est_price", "size"), market=("est_price", "sum"), fair=("fair_price", "sum"))
g["shift"] = (g.fair - g.market).astype(int)
g["per_player"] = (g["shift"] / g["n"]).round(1)
print(g[g.n > 0][["n", "market", "fair", "shift", "per_player"]].to_string())
print("\n  negative = the room pays more than the band has ever returned")
