"""Turn current-season ADP into expected auction prices, then draft example rosters.

Pricing, in two parts:

1. ORDERING inside each position comes from UNDERDOG. Sharp money, continuously
   repriced, and it moves first -- Jamie's call, backed by years of watching it.

2. CROSS-POSITION WEIGHTING comes from PBAFFL's own positional price curves,
   because Underdog cannot supply it: Underdog is best ball, with 18 rounds, a
   FLEX this league does not have, and no kicker or defense at all. League
   history says RB1 goes for $66 here while QB1 goes for $36 -- that gap IS our
   format (no FLEX, and a mandatory K and DEF). So Underdog says who the 5th-best
   RB is; league history says what the 5th RB costs.

   K and DEF, which Underdog never drafts, come from FFC.

3. Rosters are then filled under the real constraints: $200, 16 picks, and a
   starting nine of 1 QB / 3 WR / 2 RB / 1 TE / 1 K / 1 DEF with no FLEX.

Caveat: these rosters are ILLUSTRATIONS of allocation strategy, not player
recommendations. No projection enters the pricing at all -- the ordering is the
market's and the analysis only decides how to SPEND against it.

Run:  python build_2026_board.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata", "analysis")
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))

BUDGET, SPOTS = 200, 16
STARTERS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}

# Price the board off the last three seasons only. The league's positional
# market has drifted materially -- RB fell from 48.6% of spend in 2020 to 35.8%
# in 2024 while WR rose to 47.7% -- so nine-year averages price the wrong market.
PRICE_SEASONS = (2023, 2025)

# ---------------------------------------------------- 1. positional curves
#
# Underdog supplies the ORDERING inside each position -- Jamie's judgement,
# backed by years of watching it: sharp money, continuously repriced, and it
# moves first. What Underdog cannot supply is how THIS league values one
# position against another, because it is best ball: 18 rounds, a FLEX we don't
# have, and no kicker or defense at all.
#
# So the re-weighting is done with PBAFFL's own positional price curves. They
# encode our format directly -- RB1 goes for $66 here while QB1 goes for $36,
# precisely because we start no FLEX and must roster a K and a DEF. Underdog
# says WHO is the 5th-best RB; league history says what the 5th RB costs.
POS_HIST = pd.read_sql(f"""
    SELECT season, position, price FROM draft_picks
    WHERE season BETWEEN {PRICE_SEASONS[0]} AND {PRICE_SEASONS[1]}
      AND position IN ('QB','RB','WR','TE','K','DEF')
""", con)
POS_HIST["pos_rank"] = POS_HIST.groupby(["season", "position"])["price"] \
    .rank(ascending=False, method="first").astype(int)

pos_curve = {}
for pos, g in POS_HIST.groupby("position"):
    depth = int(g["pos_rank"].max())
    raw = g.groupby("pos_rank")["price"].median().reindex(range(1, depth + 1))
    sm = raw.rolling(window=3, center=True, min_periods=1).median().ffill().fillna(1)
    iso = IsotonicRegression(increasing=False, y_min=1)
    pos_curve[pos] = pd.Series(
        iso.fit_transform(list(sm.index), sm.values), index=sm.index).clip(lower=1)


def price_for(pos, rank):
    """What the Nth-most-expensive player at this position costs in PBAFFL."""
    cv = pos_curve.get(pos)
    if cv is None or not len(cv):
        return 1
    return int(round(cv.iloc[min(int(rank), len(cv)) - 1]))


# kept for the diagnostic printout below
hist = pd.read_sql(f"""
    SELECT p.season, p.player_key, p.adp, d.price
    FROM v_preseason p
    JOIN draft_picks d ON d.season = p.season AND d.player_key = p.player_key
    WHERE p.season BETWEEN {PRICE_SEASONS[0]} AND {PRICE_SEASONS[1]}
""", con)
hist["adp_rank"] = hist.groupby("season")["adp"].rank(method="first").astype(int)

# Each ADP rank has only ~3 observations (3 seasons), so per-rank medians are
# noisy. Smooth over a window of neighbouring ranks first, then enforce
# monotonicity with ISOTONIC REGRESSION.
#
# An earlier version used np.minimum.accumulate for the monotonic step. That was
# wrong: a running minimum drags every later rank down to any dip, so a low
# median at rank 9 flattened ranks 10-17 to a single price and under-priced them
# by $5-12 each. Isotonic finds the best-fitting monotone curve instead.
RANKS = range(1, 261)
raw = hist.groupby("adp_rank")["price"].median().reindex(RANKS)

# Nothing deeper than this rank has ever been drafted out of the ADP list, so
# there is no evidence there -- forward-filling instead carried ~$2 all the way
# down and produced a board with NO $1 players, when $1 is in fact the single
# most common price in league history (97 of 576 picks over 2023-25).
last_seen = int(hist["adp_rank"].max())
smooth = raw.rolling(window=7, center=True, min_periods=1).median()
smooth.loc[last_seen + 1:] = 1.0
smooth = smooth.ffill().fillna(1)

iso = IsotonicRegression(increasing=False, y_min=1)
curve = pd.Series(iso.fit_transform(list(RANKS), smooth.values), index=RANKS).clip(lower=1)

# ---------------------------------------------------------------- 2. 2026
# Underdog for the QB/RB/WR/TE ordering; FFC for K and DEF, which Underdog does
# not draft at all. Each player is then priced off his own position's curve.
ud = pd.read_sql("""
    SELECT player_name, player_key, position, nfl_team, adp
    FROM preseason_adp
    WHERE season = 2026 AND source = 'underdog' AND scoring_format = 'half-ppr'
""", con)
kd = pd.read_sql("""
    SELECT player_name, player_key, position, nfl_team, adp
    FROM preseason_adp
    WHERE season = 2026 AND source = 'ffc' AND scoring_format = 'half-ppr'
      AND position IN ('K','DEF')
""", con)
adp = pd.concat([ud, kd], ignore_index=True).drop_duplicates("player_key")

adp["pos_rank"] = adp.groupby("position")["adp"].rank(method="first").astype(int)
adp["est_price"] = [price_for(r.position, r.pos_rank) for r in adp.itertuples()]
# board order is by what the player will cost, not by raw ADP, because the
# positions are on different price scales
adp = adp.sort_values(["est_price", "adp"], ascending=[False, True]).reset_index(drop=True)
adp["adp_rank"] = range(1, len(adp) + 1)

# NOT calibrated up to the $2,400 pool, deliberately. Rank-matched prices land
# where history says (rank 1 = $69 against an all-time league max of $74), but
# they sum ~15% light across the board. Scaling the gap away pushed rank 1 to
# $84 -- above any price ever paid here -- so per-player accuracy was kept and
# the aggregate gap left alone. Treat these as a FLOOR: in a live room expect
# competitive bidding to run a few dollars over on players people want.

# FFC drafts kickers and defenses, so both now carry real market prices. The
# placeholder "(streaming K/DEF)" rows this used to inject are gone.
pool = adp.copy()
missing = [p for p in ("K", "DEF") if not (pool["position"] == p).any()]
if missing:
    pool = pd.concat([pool, pd.DataFrame([
        {"player_name": f"(streaming {p})", "player_key": f"_{p.lower()}",
         "position": p, "nfl_team": "--", "adp": 999, "adp_rank": 999,
         "est_price": 2} for p in missing])], ignore_index=True)
    print(f"  (no market data for {missing}; using $2 placeholders)")

print("2026 prices: Underdog ordering within position, priced on this "
      "league's own positional curves (FFC supplies K/DEF)")
print(pool.head(14)[["adp_rank", "player_name", "position", "pos_rank", "nfl_team",
                     "adp", "est_price"]].to_string(index=False))
print(f"\ntotal estimated value on the board: ${pool['est_price'].sum():,} "
      f"(league has ${BUDGET * 12:,} to spend)")


# nobody rosters four quarterbacks; cap what the bench filler may stack
MAX_AT = {"QB": 2, "TE": 2, "K": 1, "DEF": 1, "RB": 7, "WR": 8}


def draft(rules, label, note):
    """Greedy fill: best-ADP player allowed by the rules, subject to budget."""
    budget, roster, avail = BUDGET, [], pool.copy()
    need = dict(STARTERS)
    held = {p: 0 for p in MAX_AT}

    def reserve(after_pos=None):
        """Cheapest cost of everything still legally required after a buy.

        Reserving only $1 per empty spot is not enough: a mandatory K and DEF
        cost ~$2 each, and without this the greedy spends down and ends up
        unable to field a legal lineup.
        """
        pending = dict(need)
        if after_pos and pending.get(after_pos, 0) > 0:
            pending[after_pos] -= 1
        cost, slots = 0, 0
        for pos, n in pending.items():
            if n <= 0:
                continue
            cheap = avail[avail.position == pos]["est_price"].nsmallest(n)
            cost += int(cheap.sum()) if len(cheap) >= n else n
            slots += n
        bench_left = max(0, SPOTS - len(roster) - 1 - slots)
        return cost + bench_left

    def take(pick):
        """Buy a player only if the rest of a legal roster remains affordable."""
        nonlocal budget, avail
        if int(pick.est_price) > budget - reserve(pick.position):
            return False
        roster.append(pick)
        budget -= int(pick.est_price)
        held[pick.position] = held.get(pick.position, 0) + 1
        avail = avail.drop(pick.name)
        return True

    for pos, lo, hi, count in rules:                      # priority buys
        for _ in range(count):
            ok = avail[(avail.position == pos) & (avail.est_price >= lo)
                       & (avail.est_price <= hi)]
            if len(ok) and take(ok.iloc[0]):
                need[pos] = max(0, need.get(pos, 0) - 1)

    for pos, n in list(need.items()):                     # unfilled starting slots
        for _ in range(n):
            ok = avail[avail.position == pos].sort_values("est_price")
            for _, cand in ok.iterrows():
                if take(cand):
                    need[pos] -= 1
                    break

    while len(roster) < SPOTS:                            # bench, cheapest upside
        room = [p for p, c in held.items() if c < MAX_AT[p] and p not in ("K", "DEF")]
        ok = avail[avail.position.isin(room)].sort_values(["est_price", "adp"])
        ok = ok[ok.est_price <= budget - (SPOTS - len(roster) - 1)]
        if not len(ok):
            break
        # among equally-priced players prefer the best ADP at RB/WR
        cheapest = ok[ok.est_price == ok.est_price.min()]
        pref = cheapest[cheapest.position.isin(["RB", "WR"])]
        if not take((pref if len(pref) else cheapest).iloc[0]):
            break

    r = pd.DataFrame(roster)
    print("\n" + "=" * 74)
    print(f"{label}\n{note}")
    print("=" * 74)
    starters, bench, counts = [], [], dict(STARTERS)
    for _, p in r.sort_values("est_price", ascending=False).iterrows():
        if counts.get(p.position, 0) > 0:
            starters.append(p)
            counts[p.position] -= 1
        else:
            bench.append(p)
    for tag, group in (("STARTERS", starters), ("BENCH", bench)):
        print(f"\n  {tag}")
        for p in group:
            print(f"    ${p.est_price:>3}  {p.position:<4} {p.player_name:<24} {p.nfl_team}")
    spent = int(r["est_price"].sum())
    print(f"\n  spent ${spent} of ${BUDGET} on {len(r)} picks "
          f"(${BUDGET - spent} left)")
    by = r.groupby("position")["est_price"].sum().to_dict()
    print("  by position: " + "  ".join(f"{k} ${v}" for k, v in sorted(by.items())))

    # a roster that can't field a legal lineup is worthless -- fail loudly
    have = r["position"].value_counts().to_dict()
    problems = [f"{pos} {have.get(pos, 0)}/{n}" for pos, n in STARTERS.items()
                if have.get(pos, 0) < n]
    if spent > BUDGET:
        problems.append(f"over budget by ${spent - BUDGET}")
    if len(r) != SPOTS:
        problems.append(f"{len(r)} picks, need {SPOTS}")
    print("  CHECK: " + ("LEGAL - fills every starting slot" if not problems
                         else "INVALID -> " + ", ".join(problems)))
    return r


# rules: (position, min_price, max_price, how_many) in priority order
draft([("RB", 36, 99, 1), ("WR", 36, 99, 2), ("TE", 21, 35, 1),
       ("WR", 6, 20, 1), ("RB", 1, 5, 1), ("QB", 1, 2, 1), ("K", 1, 3, 1), ("DEF", 1, 3, 1)],
      "ROSTER A - findings-driven",
      "$36+ on RB/WR (only tier that beats the median starter), $21-35 TE\n"
      "(cheapest above-median slot), $1-2 QB lottery ticket, no mid-tier RB.")

draft([("RB", 36, 99, 2), ("WR", 36, 99, 1), ("WR", 11, 20, 2), ("RB", 11, 20, 1),
       ("TE", 6, 10, 1), ("QB", 6, 15, 1), ("K", 1, 3, 1), ("DEF", 1, 3, 1)],
      "ROSTER B - league-typical (what PBAFFL actually does)",
      "Mirrors the league's historical allocation: RB-heavy, mid-tier everywhere,\n"
      "a real QB. Included as the benchmark the strategy has to beat.")

draft([("WR", 36, 99, 3), ("RB", 36, 99, 1), ("TE", 1, 5, 1), ("QB", 1, 2, 1),
       ("RB", 1, 5, 1), ("K", 1, 3, 1), ("DEF", 1, 3, 1)],
      "ROSTER C - extreme stars-and-scrubs",
      "Four $36+ bats, everything else at minimum. Tests the published\n"
      "stars-and-scrubs finding, which this league's thin waiver wire argues against.")

pool.to_csv(os.path.join(OUT, "board_2026.csv"), index=False, encoding="utf-8-sig")
print(f"\n\nfull 2026 board with estimated prices -> {OUT}/board_2026.csv")
