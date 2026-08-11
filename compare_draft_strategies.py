"""Two 2026 drafts compared: buy the best roster vs capture discounts.

"Round" here is SNAKE TERMINOLOGY MAPPED ONTO AN AUCTION, per Jamie: round 1 is
simply the 12 most expensive players drafted, round 2 the next 12, and so on.
It is a price band, not a moment in time -- the actual nomination order is
irrelevant. An earlier version of this file modelled rounds as nomination
timing, derived an availability ceiling from 9 seasons of nomination data, and
solved the wrong problem entirely.

DRAFT 1 - MAX OUTPUT.  Pay the going rate. Maximise projected starter points.
DRAFT 2 - DISCOUNT.    Same board, but up to MAX_DISC_PER_ROUND picks per price
                       band can be had below the going rate, with the discount
                       widening by DISCOUNT_PER_ROUND per band.

Both drafts also pay a PREMIUM on the top TOP_N_PREMIUM players -- that is a
fact about the room, not a choice, and it lands in round 1 where no discount
exists to offset it.

Both: $200, 16 picks, starting nine of 1 QB / 2 RB / 3 WR / 1 TE / 1 K / 1 DEF,
bench at $1. Starters chosen by exact multi-choice knapsack DP.
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata", "analysis")
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))

BUDGET, SPOTS = 200, 16
STARTERS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}
BENCH = SPOTS - sum(STARTERS.values())
STARTER_BUDGET = BUDGET - BENCH
TEAMS = 12

DISCOUNT_PER_ROUND = float(os.environ.get("DISC", 0.10))
MAX_DISC = float(os.environ.get("MAXDISC", 0.80))
MAX_DISC_PER_ROUND = int(os.environ.get("PERROUND", 2))
TOP_N_PREMIUM = int(os.environ.get("TOPN", 6))
PREMIUM = float(os.environ.get("PREM", 0.15))

# ---- pool -------------------------------------------------------------------
proj = pd.read_sql("""
    SELECT player_key, player_name, position, nfl_team, proj_points
    FROM projections WHERE season = 2026
""", con)
board = pd.read_csv(os.path.join(OUT, "board_2026.csv"))[["player_key", "est_price"]]
pool = proj.merge(board, on="player_key", how="inner")
pool = pool[pool["proj_points"] > 0].copy()
pool["list_price"] = pool["est_price"].astype(int).clip(lower=1)

# Rounds = price bands of 12, over the 192 players who actually get drafted.
pool = pool.sort_values("list_price", ascending=False).reset_index(drop=True)
pool["price_rank"] = np.arange(1, len(pool) + 1)
pool["round"] = np.ceil(pool["price_rank"] / TEAMS).astype(int)

# Top-N premium: unavoidable, and it sits in round 1 where no discount applies.
pool["is_top"] = pool["price_rank"] <= TOP_N_PREMIUM
pool["price"] = np.where(pool["is_top"],
                         np.round(pool["list_price"] * (1 + PREMIUM)),
                         pool["list_price"]).astype(int)

pool["discount"] = np.minimum(MAX_DISC, DISCOUNT_PER_ROUND * (pool["round"] - 1))
pool["disc_price"] = np.maximum(
    1, np.round(pool["price"] * (1 - pool["discount"]))).astype(int)

pool = (pool.sort_values("proj_points", ascending=False)
        .groupby("position").head(60).reset_index(drop=True))


def best_by_position(players, k, cap, price_col):
    NEG = -1e9
    dp = np.full((k + 1, cap + 1), NEG)
    dp[0, 0] = 0.0
    pick = [[None] * (cap + 1) for _ in range(k + 1)]
    for idx, row in players.iterrows():
        c, v = int(row[price_col]), float(row["proj_points"])
        for j in range(k, 0, -1):
            for b in range(cap, c - 1, -1):
                if dp[j - 1, b - c] + v > dp[j, b]:
                    dp[j, b] = dp[j - 1, b - c] + v
                    pick[j][b] = (idx, b - c, j - 1)
    return dp[k], pick


def solve(price_col, label):
    tabs = {}
    for pos, k in STARTERS.items():
        cand = pool[pool["position"] == pos]
        tabs[pos] = (*best_by_position(cand, k, STARTER_BUDGET, price_col), cand)
    order = list(STARTERS)
    cur = np.full(STARTER_BUDGET + 1, -1e9)
    cur[0] = 0.0
    trace = [dict() for _ in order]
    for i, pos in enumerate(order):
        arr = tabs[pos][0]
        nxt = np.full(STARTER_BUDGET + 1, -1e9)
        for b in range(STARTER_BUDGET + 1):
            if cur[b] <= -1e8:
                continue
            for c in range(STARTER_BUDGET + 1 - b):
                if arr[c] > -1e8 and cur[b] + arr[c] > nxt[b + c]:
                    nxt[b + c] = cur[b] + arr[c]
                    trace[i][b + c] = (b, c)
        cur = nxt
    cost = int(np.argmax(cur))
    total = cur[cost]
    chosen = []
    for i in range(len(order) - 1, -1, -1):
        b, c = trace[i][cost]
        arr, pick, cand = tabs[order[i]]
        k, left = STARTERS[order[i]], c
        while k > 0:
            idx, prev_b, prev_k = pick[k][left]
            chosen.append(cand.loc[idx])
            left, k = prev_b, prev_k
        cost = b
    s = pd.DataFrame(chosen)
    return {"label": label, "starters": s, "price_col": price_col,
            "spend": int(s[price_col].sum()), "points": round(total, 1)}


def apply_discount_cap(r):
    """At most MAX_DISC_PER_ROUND picks per band may take the discount.

    Extras in a band revert to the going rate. Cheapest way to satisfy this is
    to discount the most expensive picks in each band, since the discount is a
    percentage.
    """
    s = r["starters"].copy()
    s["paid"] = s["disc_price"]
    for rd, g in s.groupby("round"):
        if len(g) > MAX_DISC_PER_ROUND:
            keep = g.nlargest(MAX_DISC_PER_ROUND, "price").index
            revert = [i for i in g.index if i not in keep]
            s.loc[revert, "paid"] = s.loc[revert, "price"]
    r["starters"], r["spend"] = s, int(s["paid"].sum())
    r["over_budget"] = r["spend"] + BENCH > BUDGET
    return r


d1 = solve("price", "DRAFT 1 - MAX OUTPUT (pay the going rate)")
d1["starters"]["paid"] = d1["starters"]["price"]
d2 = apply_discount_cap(solve("disc_price", "DRAFT 2 - DISCOUNT (up to "
                              f"{MAX_DISC_PER_ROUND} per price band)"))

print(f"\nassumptions: rounds are price bands of {TEAMS}; top {TOP_N_PREMIUM} pay "
      f"+{PREMIUM:.0%}; discount {DISCOUNT_PER_ROUND:.0%}/band (cap {MAX_DISC:.0%}); "
      f"max {MAX_DISC_PER_ROUND} discounted per band")


def show(r):
    s = r["starters"].sort_values("paid", ascending=False)
    print("\n" + "=" * 80)
    print(f"{r['label']}   ->  {r['points']} projected starter points")
    print("=" * 80)
    for _, p in s.iterrows():
        note = " PREMIUM" if p["is_top"] else ""
        if p["paid"] != p["price"]:
            note = f"  (rd {int(p['round'])} band, was ${int(p['price'])}, -{p['discount']:.0%})"
        print(f"   ${int(p['paid']):>3}  {p['position']:<4} {p['player_name']:<24}"
              f" {p['proj_points']:>6.0f} pts{note}")
    print(f"\n   starters ${r['spend']} + ${BENCH} bench = ${r['spend'] + BENCH} of ${BUDGET}")
    print(f"   picks per band: {dict(sorted(s['round'].value_counts().items()))}")
    if r.get("over_budget"):
        print("   ! OVER BUDGET once the discount cap is applied")


show(d1)
show(d2)
print("\n" + "=" * 80)
print("VERDICT")
print("=" * 80)
diff = d2["points"] - d1["points"]
print(f"  max-output : {d1['points']} pts for ${d1['spend']}")
print(f"  discount   : {d2['points']} pts for ${d2['spend']}")
print(f"  difference : {diff:+.1f} pts ({100 * diff / d1['points']:+.1f}%)")
print("\n  one starter tier is worth ~78 pts at WR and ~119 at RB, for scale.")
