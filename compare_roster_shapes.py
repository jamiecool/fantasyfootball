"""Score genuinely different roster SHAPES against the 2026 board.

Written after a fair challenge: the first three example rosters were all
stars-and-scrubs in disguise (3-4 big buys, then a wall of $1s), so nothing was
actually being compared. Worse, arguing for concentration contradicts our own
finding that concentration does not predict roster quality (r = +0.02 across
106 team-seasons).

So: build shapes that really differ in concentration, and score each one's
STARTING LINEUP with the price->points relationship from league history.

Scoring is expected value only. It says nothing about variance, which matters
for a manager whose stated goal is to finish 1st rather than merely above .500.
"""
import os
import sqlite3

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata", "analysis")
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))

BUDGET, SPOTS = 200, 16
STARTERS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}

# ---- expected season points as a function of (position, price) --------------
hist = pd.read_sql("""
    SELECT d.position, d.price, COALESCE(f.points, 0) AS points
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season = d.season AND f.player_key = d.player_key
    WHERE d.position IN ('QB','RB','WR','TE','K','DEF')
""", con)
# index each season out of the way by using all years pooled; points are already
# on a comparable scale because replacement levels barely drift (see README)
curves = {}
for pos, g in hist.groupby("position"):
    if len(g) < 30:
        continue
    x = np.log(g["price"].clip(lower=1))
    order = np.argsort(x.values)
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
    iso.fit(x.values[order], g["points"].values[order])
    curves[pos] = iso

DEF_POINTS = 90.0          # no nflverse D/ST data; flat estimate, same for all shapes


def exp_points(pos, price):
    if pos == "DEF":
        return DEF_POINTS
    if pos not in curves:
        return 0.0
    return float(curves[pos].predict([np.log(max(price, 1))])[0])


board = pd.read_csv(os.path.join(OUT, "board_2026.csv"))
board = board[board["adp_rank"] <= 250].copy()


def build(shape, label):
    """shape: list of (position, target_price). Greedy nearest affordable price."""
    avail, roster, budget = board.copy(), [], BUDGET
    floor = int(board["est_price"].min())    # real cheapest, not an assumed $1

    def afford(n_after):
        """Most we can spend now and still fill n_after spots at the floor."""
        return budget - n_after * floor

    # K and DEF are mandatory and always ~$2. Buy them FIRST so everything else
    # budgets around them -- letting them skip the affordability check silently
    # consumed $4 and left shapes unable to fill their last roster spots.
    for pos in ("K", "DEF"):
        if any(p == pos for p, _ in shape):
            roster.append({"position": pos, "player_name": f"(streaming {pos})",
                           "est_price": 2, "nfl_team": "--"})
            budget -= 2

    for pos, target in shape:
        if pos in ("K", "DEF"):
            continue
        pool = avail[avail.position == pos].copy()
        pool = pool[pool.est_price <= afford(SPOTS - len(roster) - 1)]
        if not len(pool):
            continue
        pick = pool.iloc[(pool.est_price - target).abs().argsort().iloc[0]]
        roster.append(pick.to_dict())
        budget -= int(pick.est_price)
        avail = avail.drop(pick.name)

    # Bench at minimum, but capped by position. Without caps the filler stacked
    # three backup TEs behind a $27 starter, which no one would ever do.
    BENCH_CAP = {"RB": 6, "WR": 7, "TE": 2, "QB": 2}
    while len(roster) < SPOTS:
        held = pd.DataFrame(roster)["position"].value_counts().to_dict()
        room = [p for p, cap in BENCH_CAP.items() if held.get(p, 0) < cap]
        pool = avail[(avail.est_price <= afford(SPOTS - len(roster) - 1))
                     & avail.position.isin(room)]
        if not len(pool):
            break
        # cheapest first, and among ties prefer the better ADP at RB/WR
        cheap = pool[pool.est_price == pool.est_price.min()]
        pref = cheap[cheap.position.isin(["RB", "WR"])]
        pick = (pref if len(pref) else cheap).nsmallest(1, "adp").iloc[0]
        roster.append(pick.to_dict())
        budget -= int(pick.est_price)
        avail = avail.drop(pick.name)

    r = pd.DataFrame(roster)
    counts, starters = dict(STARTERS), []
    for _, p in r.sort_values("est_price", ascending=False).iterrows():
        if counts.get(p["position"], 0) > 0:
            starters.append(p)
            counts[p["position"]] -= 1
    s = pd.DataFrame(starters)
    proj = sum(exp_points(p["position"], p["est_price"]) for _, p in s.iterrows())

    # Bench value. exp_points is fitted on ACTUAL season totals, which already
    # net out the games a starter missed -- so the bench is not a deduction, it
    # is the points that FILL those empty weeks. Earlier scoring counted zero
    # for this, which is exactly the bias Jamie flagged.
    names = set(s["player_name"])
    bench_pts = 0.0
    for _, st in s.iterrows():
        pos = st["position"]
        if pos in ("K", "DEF"):
            continue
        missed = 17 - exp_games(st["est_price"])
        pool = r[(r["position"] == pos) & (~r["player_name"].isin(names))]
        if len(pool):
            b = pool.loc[pool["est_price"].idxmax()]
            bench_pts += missed * exp_points(pos, b["est_price"]) / exp_games(b["est_price"])
    spent = int(r["est_price"].sum())
    top3 = int(r["est_price"].nlargest(3).sum())
    legal = all(counts[p] == 0 for p in counts)
    return {"shape": label, "spent": spent, "picks": len(r),
            "top3_pct": round(100 * top3 / BUDGET), "max_bid": int(r["est_price"].max()),
            "bench_spend": spent - int(s["est_price"].sum()),
            "proj_starter_pts": round(proj), "bench_fill_pts": round(bench_pts),
            "total_pts": round(proj + bench_pts),
            "legal": legal, "roster": r, "start": s}


# Availability by price tier, from final_ranks.games over 9 seasons (17-game year)
GAMES_BY_TIER = {1: 12.8, 3: 13.3, 6: 13.0, 11: 13.8, 21: 13.5, 36: 14.1}


def exp_games(price):
    for lo in sorted(GAMES_BY_TIER, reverse=True):
        if price >= lo:
            return GAMES_BY_TIER[lo]
    return 12.8


SHAPES = {
    "A. stars & scrubs": [
        ("RB", 64), ("WR", 62), ("WR", 56), ("TE", 34), ("QB", 2),
        ("K", 2), ("DEF", 2), ("RB", 2), ("WR", 2)],
    "B. balanced - nothing over $30": [
        ("RB", 30), ("RB", 26), ("WR", 30), ("WR", 26), ("WR", 25),
        ("TE", 27), ("QB", 9), ("K", 2), ("DEF", 2)],
    "C. barbell - two bats then mid": [
        ("RB", 64), ("WR", 62), ("WR", 25), ("WR", 20), ("RB", 17),
        ("TE", 19), ("QB", 7), ("K", 2), ("DEF", 2)],
    "D. findings-led": [
        ("WR", 62), ("WR", 47), ("RB", 44), ("TE", 34), ("WR", 25),
        ("RB", 2), ("QB", 2), ("K", 2), ("DEF", 2)],
    "E. flat - starters $18-25": [
        ("RB", 25), ("RB", 23), ("WR", 25), ("WR", 25), ("WR", 24),
        ("TE", 19), ("QB", 25), ("K", 2), ("DEF", 2)],
    # --- shapes that actually buy a bench, which nothing above did ---
    "F. two bats + REAL bench": [
        ("RB", 62), ("WR", 56), ("WR", 20), ("WR", 14), ("RB", 14),
        ("TE", 12), ("QB", 2), ("K", 2), ("DEF", 2),
        ("RB", 10), ("RB", 9), ("WR", 9), ("WR", 7), ("TE", 6)],
    "G. depth-first - 12 real players": [
        ("RB", 25), ("RB", 20), ("WR", 25), ("WR", 20), ("WR", 17),
        ("TE", 12), ("QB", 2), ("K", 2), ("DEF", 2),
        ("RB", 12), ("RB", 10), ("WR", 12), ("WR", 10), ("WR", 9)],
}

rows = [build(v, k) for k, v in SHAPES.items()]
tab = pd.DataFrame([{k: r[k] for k in
                     ("shape", "spent", "picks", "max_bid", "top3_pct",
                      "bench_spend", "proj_starter_pts", "bench_fill_pts",
                      "total_pts", "legal")}
                    for r in rows]).sort_values("total_pts", ascending=False)
print("=" * 92)
print("ROSTER SHAPES SCORED ON THE 2026 BOARD  (proj = expected starting-lineup points)")
print("=" * 92)
print(tab.to_string(index=False))

best = max(rows, key=lambda r: r["total_pts"])
print(f"\nbest projected shape: {best['shape']}")
print("\nits starting lineup:")
for _, p in best["start"].sort_values("est_price", ascending=False).iterrows():
    print(f"   ${p['est_price']:>3}  {p['position']:<4} {p['player_name']:<24}"
          f" -> {exp_points(p['position'], p['est_price']):.0f} pts")

print("\n" + "-" * 92)
print("spread between best and worst shape: "
      f"{tab['total_pts'].max() - tab['total_pts'].min()} points "
      f"({100 * (tab['total_pts'].max() / tab['total_pts'].min() - 1):.1f}%)")
print("For scale, one starter tier is worth ~78 pts at WR and ~119 at RB, so a")
print("spread smaller than that means these shapes are effectively equivalent.")
