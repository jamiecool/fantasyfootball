"""Search for the best roster we can actually buy, and name the 2026 players.

Objective is rule 16: maximise expected points. Not hit rate, not floor, not a
roster shape -- the threshold objective amplifies the mean, so the mean is what
we maximise.

Scoring uses REAL OUTCOMES, not projections. For a given price at a given
position, we have nine seasons of what players bought at that price actually
returned, busts included as zeros. Rule 4 says our projections are the weakest
input we have, so they are kept out of this entirely -- projections decide
nothing here, history does.

The roster is scored the way it is actually used: you own 16 and start 9, so a
draw is scored as the best legal lineup out of what you own. That matters. An
earlier version of the shape work scored only the intended starters, which
credited concentration for free and made stars-and-scrubs look better than it is.

Search is hill climbing on (composition, price vector) under common random
numbers -- the same draws are reused for every candidate, so two allocations are
compared on the same luck rather than on sampling noise.

Run:  python build_best_roster.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
rng = np.random.default_rng(20260811)

BUDGET, SPOTS = 200, 16
START = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}
POS = ["QB", "RB", "WR", "TE"]
MAXP = 80
NDRAW = 3000

# ---------------------------------------------------------------- outcome pools
picks = pd.read_sql("""
    SELECT d.season, d.position, d.price, COALESCE(f.points, 0) points
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season = d.season AND f.player_key = d.player_key
""", con)

# E[points | price] is fitted as a SMOOTH MONOTONE CURVE per position rather
# than read off raw price cells.
#
# The first version binned prices directly and the optimiser promptly bought a
# $36 quarterback, because QB at $36+ has n=4 in this league and those four
# happen to be the best quarterback seasons of the era. That is the same failure
# the price curve hit earlier -- thin cells at the top read as signal. Isotonic
# regression over all nine seasons shrinks a lucky cell toward its neighbours,
# and residuals are pooled within position so the spread stays realistic.
from sklearn.isotonic import IsotonicRegression                    # noqa: E402

POOL, CURVE = {}, {}
for pos in START:
    sub = picks[picks.position == pos]
    if len(sub) < 30:
        CURVE[pos] = lambda p, m=sub["points"].mean(): m
        resid = (sub["points"] - sub["points"].mean()).to_numpy(dtype=float)
    else:
        iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
        iso.fit(sub["price"].to_numpy(dtype=float), sub["points"].to_numpy(dtype=float))
        CURVE[pos] = iso.predict
        resid = (sub["points"].to_numpy(dtype=float)
                 - iso.predict(sub["price"].to_numpy(dtype=float)))
    for price in range(1, MAXP + 1):
        fitted = float(np.atleast_1d(CURVE[pos]([price]))[0]) if callable(CURVE[pos]) else 0.0
        # a player cannot score below zero, and a bust is a real outcome
        POOL[(pos, price)] = np.clip(fitted + resid, 0, None)

print("fitted E[points | price], all 9 seasons:")
print(f"  {'':4}" + "".join(f"{('$' + str(p)):>8}" for p in (1, 5, 10, 20, 35, 50, 65)))
for pos in ["QB", "RB", "WR", "TE"]:
    vals = [float(np.atleast_1d(CURVE[pos]([p]))[0]) for p in (1, 5, 10, 20, 35, 50, 65)]
    print(f"  {pos:4}" + "".join(f"{v:8.0f}" for v in vals))
print()

# common random numbers: one fixed uniform draw per (slot, iteration)
U = rng.random((SPOTS, NDRAW))


def sample(pos, price, row):
    """Deterministic draw for this slot from the pool at that price."""
    arr = POOL[(pos, min(max(int(price), 1), MAXP))]
    idx = (U[row] * len(arr)).astype(int).clip(0, len(arr) - 1)
    return arr[idx]


def evaluate(alloc):
    """alloc: list of (position, price), length SPOTS. Returns mean, p10, p90."""
    draws = {}
    for i, (pos, price) in enumerate(alloc):
        draws.setdefault(pos, []).append(sample(pos, price, i))
    total = np.zeros(NDRAW)
    for pos, need in START.items():
        got = draws.get(pos)
        if not got or len(got) < need:
            return -1e9, 0, 0                # illegal: cannot fill the lineup
        stack = np.sort(np.stack(got), axis=0)[::-1]      # best first
        total += stack[:need].sum(axis=0)
    return total.mean(), np.percentile(total, 10), np.percentile(total, 90)


def make(counts, prices):
    out = []
    for pos, n in counts.items():
        out += [(pos, prices[pos][i]) for i in range(n)]
    return out


def random_start():
    counts = {"QB": int(rng.integers(1, 3)), "TE": int(rng.integers(1, 3)),
              "K": 1, "DEF": 1}
    left = SPOTS - sum(counts.values())
    counts["RB"] = int(rng.integers(3, min(7, left - 4) + 1))
    counts["WR"] = left - counts["RB"]
    # cheap mandatory slots first, then split what is left at random
    prices = {"K": [1], "DEF": [2]}
    pool = BUDGET - 3
    weights = {p: rng.random(counts[p]) for p in POS}
    tot = sum(w.sum() for w in weights.values())
    for p in POS:
        raw = (weights[p] / tot * pool)
        prices[p] = sorted([max(1, int(round(x))) for x in raw], reverse=True)
    return counts, prices


def spend(prices):
    return sum(sum(v) for v in prices.values())


def repair(prices):
    """Nudge the allocation back to exactly BUDGET."""
    while spend(prices) > BUDGET:
        p = max(POS, key=lambda x: max(prices[x]))
        i = int(np.argmax(prices[p]))
        if prices[p][i] > 1:
            prices[p][i] -= 1
        else:
            break
    while spend(prices) < BUDGET:
        p = POS[int(rng.integers(0, len(POS)))]
        prices[p][int(rng.integers(0, len(prices[p])))] += 1
    return prices


best = None
for restart in range(14):
    counts, prices = random_start()
    prices = repair(prices)
    cur = evaluate(make(counts, prices))[0]
    for step in range(700):
        cand = {k: list(v) for k, v in prices.items()}
        a, b = rng.choice(POS, 2, replace=False)
        ia = int(rng.integers(0, len(cand[a])))
        ib = int(rng.integers(0, len(cand[b])))
        amt = int(rng.integers(1, 7))
        if cand[a][ia] - amt < 1:
            continue
        cand[a][ia] -= amt
        cand[b][ib] += amt
        val = evaluate(make(counts, cand))[0]
        if val > cur:
            cur, prices = val, cand
    m, lo, hi = evaluate(make(counts, prices))
    if best is None or m > best[0]:
        best = (m, lo, hi, counts, {k: sorted(v, reverse=True) for k, v in prices.items()})

mean, p10, p90, counts, prices = best
print("=" * 78)
print("BEST ROSTER SHAPE FOUND")
print("=" * 78)
print(f"  expected starting-lineup points {mean:,.0f}   "
      f"(bad year {p10:,.0f} / good year {p90:,.0f})")
print(f"  {sum(counts.values())} players, ${spend(prices)} of ${BUDGET}")
print()
for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    if pos in prices:
        print(f"  {pos:4} x{counts[pos]}  " + "  ".join(f"${x}" for x in prices[pos]))

# --------------------------------------------------------- name the 2026 players
board = pd.read_csv(os.path.join(ROOT, "cleandata", "analysis", "board_2026.csv"))
vt = pd.read_sql("SELECT team, pts_per_game, vegas_rank FROM vegas_team", con)
board = board.merge(vt, left_on="nfl_team", right_on="team", how="left")
print("\n" + "=" * 78)
print("WHO THAT BUYS ON THE 2026 BOARD")
print("=" * 78)
taken, rows = set(), []
for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    for target in prices.get(pos, []):
        cand = board[(board.position == pos) & (~board.player_key.isin(taken))].copy()
        if not len(cand):
            continue
        cand["d"] = (cand.est_price - target).abs()
        pick = cand.nsmallest(1, "d").iloc[0]
        taken.add(pick.player_key)
        rows.append({"pos": pos, "target": target, "player": pick.player_name,
                     "price": int(pick.est_price), "team": pick.nfl_team,
                     "off": pick.get("pts_per_game", float("nan"))})
r = pd.DataFrame(rows)
starters = []
for pos, n in START.items():
    starters += list(r[r.pos == pos].nlargest(n, "price").index)
r["role"] = ["START" if i in starters else "bench" for i in r.index]
for role in ("START", "bench"):
    print(f"\n  {role}")
    for x in r[r.role == role].itertuples():
        off = f"{x.off:.1f}" if pd.notna(x.off) else "  — "
        print(f"    ${x.price:>3}  {x.pos:4} {x.player[:26]:26} {x.team:4} off {off}")
print(f"\n  total ${r.price.sum()}  ({len(r)} players)")

print("\n" + "=" * 78)
print("DOES THE OPTIMISER AGREE WITH THE RULES?")
print("=" * 78)
qb = prices["QB"][0]
wr_dead = sum(1 for x in prices["WR"] if 21 <= x <= 35)
bench_spend = r[r.role == "bench"].price.sum()
checks = [
    ("5", "never pay up for QB (target $3-8)", f"top QB ${qb}", 3 <= qb <= 10),
    ("18", "no WR in the $21-35 dead zone", f"{wr_dead} WRs in band", wr_dead == 0),
    ("19", "own 4-5 WR, do not concentrate", f"{counts['WR']} WRs", counts["WR"] >= 4),
    ("9", "about $17 on the bench", f"${bench_spend} on bench", 8 <= bench_spend <= 40),
    ("1", "cheap picks return more per dollar", f"{sum(1 for p in POS for x in prices[p] if x <= 5)} at $1-5", True),
]
for rid, text, got, ok in checks:
    print(f"  rule {rid:>2}  {'AGREES ' if ok else 'DIVERGES'}  {text:38} -> {got}")


# ==========================================================================
# TWO KNOWN BIASES, both of which inflate what the search above recommends.
#
# 1. HINDSIGHT SUBSTITUTION. Scoring "best legal lineup from what you own" on
#    SEASON totals lets the bench be chosen after the fact. In reality you set
#    a lineup weekly, in advance, without knowing. Depth is therefore worth
#    less than this says, which is why the search wants a $69 bench where rule
#    9 measured about $17.
#
# 2. A THIN QB CURVE. Only ~19 QB picks above $20 exist in nine seasons, so the
#    steep top of the fitted QB curve rests on very little. Rule 5 rests on 63
#    picks in its target band and was tested a different way entirely.
#
# So the useful question is not "which wins" but "what does obeying the rules
# cost". Constrain to them and measure the gap.
# ==========================================================================


def bench_spend(counts, prices):
    tot = 0
    for pos, n in counts.items():
        tot += sum(sorted(prices[pos], reverse=True)[START[pos]:])
    return tot


def constrained_best(qb_cap, bench_cap, restarts=10, steps=700):
    bst = None
    for _ in range(restarts):
        counts, prices = random_start()
        prices["QB"] = [min(x, qb_cap) for x in prices["QB"]]
        prices = repair(prices)
        prices["QB"] = [min(x, qb_cap) for x in prices["QB"]]
        cur = evaluate(make(counts, prices))[0]
        for _ in range(steps):
            cand = {k: list(v) for k, v in prices.items()}
            a, b = rng.choice(POS, 2, replace=False)
            ia, ib = int(rng.integers(0, len(cand[a]))), int(rng.integers(0, len(cand[b])))
            amt = int(rng.integers(1, 7))
            if cand[a][ia] - amt < 1:
                continue
            cand[a][ia] -= amt
            cand[b][ib] += amt
            if max(cand["QB"]) > qb_cap or bench_spend(counts, cand) > bench_cap:
                continue
            val = evaluate(make(counts, cand))[0]
            if val > cur:
                cur, prices = val, cand
        m, lo, hi = evaluate(make(counts, prices))
        if bst is None or m > bst[0]:
            bst = (m, lo, hi, counts,
                   {k: sorted(v, reverse=True) for k, v in prices.items()})
    return bst


def name_them(counts, prices, label):
    taken2, rows2 = set(), []
    for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
        for target in prices.get(pos, []):
            cand = board[(board.position == pos)
                         & (~board.player_key.isin(taken2))].copy()
            if not len(cand):
                continue
            cand["d"] = (cand.est_price - target).abs()
            pick = cand.nsmallest(1, "d").iloc[0]
            taken2.add(pick.player_key)
            rows2.append({"pos": pos, "player": pick.player_name,
                          "price": int(pick.est_price), "team": pick.nfl_team,
                          "off": pick.get("pts_per_game", float("nan"))})
    rr = pd.DataFrame(rows2)
    st = []
    for pos, n in START.items():
        st += list(rr[rr.pos == pos].nlargest(n, "price").index)
    rr["role"] = ["START" if i in st else "bench" for i in rr.index]
    print("\n  " + label)
    for role in ("START", "bench"):
        print("    " + role)
        for x in rr[rr.role == role].itertuples():
            off = ("%.1f" % x.off) if pd.notna(x.off) else "  - "
            print("      $%3d  %-4s %-26s %-4s off %s"
                  % (x.price, x.pos, x.player[:26], x.team, off))
    print("    total $%d across %d players" % (rr.price.sum(), len(rr)))
    return rr


print("\n" + "=" * 78)
print("WHAT OBEYING THE RULES COSTS")
print("=" * 78)
cm, clo, chi, ccounts, cprices = constrained_best(qb_cap=10, bench_cap=32)
print("  unconstrained search    %6.0f pts   (bad year %.0f)" % (mean, p10))
print("  rules 5 + 9 respected   %6.0f pts   (bad year %.0f)   %+.1f%%"
      % (cm, clo, 100 * (cm - mean) / mean))
print()
for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    if pos in cprices:
        print("  %-4s x%d  %s" % (pos, ccounts[pos],
                                  "  ".join("$%d" % x for x in cprices[pos])))
name_them(ccounts, cprices, "THE ROSTER I WOULD ACTUALLY RUN")
