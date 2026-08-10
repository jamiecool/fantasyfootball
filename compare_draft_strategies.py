"""Two 2026 drafts compared: buy the best roster vs hunt discounts.

DRAFT 1 - MAX OUTPUT. Pay list price, maximise projected starting-lineup points.
DRAFT 2 - DISCOUNT. Up to two players per nomination round, at a discount that
          grows 5 points per round (round 1 = 0%, round 2 = 5%, round 3 = 10%...).

The catch, and it is what makes this a real question: you cannot wait for elite
players. Nine seasons of nomination data say the most expensive player still on
the board in round R is roughly that round's 90th percentile price -- $65 in
round 1, $37 by round 5, $8 by round 11. So every 5% of discount costs access.

Each player is therefore bought in the LATEST round he is realistically still
available, which is the largest discount actually obtainable for him.

Both drafts: $200, 16 picks, starting nine of 1 QB / 2 RB / 3 WR / 1 TE / 1 K /
1 DEF, bench at $1. Solved exactly by multi-choice knapsack DP, not greedily.
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
STARTER_BUDGET = BUDGET - BENCH          # bench at $1 each
DISCOUNT_PER_ROUND = 0.05
MAX_PER_ROUND = 2

# ---- availability ceiling per nomination round, from 9 seasons -------------
hist = pd.read_sql("""
    SELECT season, nomination_order n, price FROM draft_picks
    WHERE nomination_order IS NOT NULL
""", con)
hist["teams"] = hist["season"].map(lambda s: 10 if s == 2020 else 12)
hist["round"] = ((hist["n"] - 1) // hist["teams"] + 1).astype(int)
ceiling = hist.groupby("round")["price"].quantile(0.90).to_dict()
ROUNDS = sorted(ceiling)


def latest_round(price):
    """Last round in which a player at this price is realistically available."""
    ok = [r for r in ROUNDS if price <= ceiling[r]]
    return max(ok) if ok else 1


# ---- the 2026 player pool --------------------------------------------------
proj = pd.read_sql("""
    SELECT player_key, player_name, position, nfl_team, proj_points
    FROM projections WHERE season = 2026
""", con)
board = pd.read_csv(os.path.join(OUT, "board_2026.csv"))[["player_key", "est_price"]]
pool = proj.merge(board, on="player_key", how="inner")

# K and DEF never appear on the Underdog board; this league always pays $1-2
kd = proj[proj["position"].isin(["K", "DEF"])].copy()
kd["est_price"] = 2
pool = pd.concat([pool[~pool["position"].isin(["K", "DEF"])], kd], ignore_index=True)
pool = pool[pool["proj_points"] > 0].copy()
pool["price"] = pool["est_price"].astype(int).clip(lower=1)
pool["round"] = pool["price"].map(latest_round)
pool["disc_price"] = np.maximum(
    1, np.round(pool["price"] * (1 - DISCOUNT_PER_ROUND * (pool["round"] - 1)))
).astype(int)

# keep the top few per position by points to bound the DP
pool = (pool.sort_values("proj_points", ascending=False)
        .groupby("position").head(60).reset_index(drop=True))


def best_by_position(players, k, cap, price_col):
    """DP: best total points using EXACTLY k of these players, per cost 0..cap.

    Returns (points array, chosen-index array) so rosters can be reconstructed.
    """
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


def solve(price_col, label, enforce_rounds):
    pos_tabs = {}
    for pos, k in STARTERS.items():
        cand = pool[pool["position"] == pos]
        arr, pick = best_by_position(cand, k, STARTER_BUDGET, price_col)
        pos_tabs[pos] = (arr, pick, cand)

    # convolve the six positions across the budget
    order = list(STARTERS)
    cur = np.full(STARTER_BUDGET + 1, -1e9)
    cur[0] = 0.0
    trace = [dict() for _ in range(len(order))]
    for i, pos in enumerate(order):
        arr = pos_tabs[pos][0]
        nxt = np.full(STARTER_BUDGET + 1, -1e9)
        for b in range(STARTER_BUDGET + 1):
            if cur[b] <= -1e8:
                continue
            for c in range(STARTER_BUDGET + 1 - b):
                if arr[c] <= -1e8:
                    continue
                if cur[b] + arr[c] > nxt[b + c]:
                    nxt[b + c] = cur[b] + arr[c]
                    trace[i][b + c] = (b, c)
        cur = nxt

    best_cost = int(np.argmax(cur))
    total = cur[best_cost]

    # walk back to recover the actual players
    chosen, cost = [], best_cost
    for i in range(len(order) - 1, -1, -1):
        b, c = trace[i][cost]
        pos = order[i]
        arr, pick, cand = pos_tabs[pos]
        k, budget_left = STARTERS[pos], c
        while k > 0:
            idx, prev_b, prev_k = pick[k][budget_left]
            chosen.append(cand.loc[idx])
            budget_left, k = prev_b, prev_k
        cost = b

    s = pd.DataFrame(chosen)
    return {"label": label, "starters": s, "spend": int(s[price_col].sum()),
            "points": round(total, 1), "price_col": price_col}


d1 = solve("price", "DRAFT 1 - MAX OUTPUT (list price)", False)
d2 = solve("disc_price", "DRAFT 2 - DISCOUNT (buy late, up to 2/round)", True)


def show(r):
    s = r["starters"].sort_values(r["price_col"], ascending=False)
    print("\n" + "=" * 78)
    print(f"{r['label']}   ->  {r['points']} projected starter points")
    print("=" * 78)
    for _, p in s.iterrows():
        lst, dsc, rd = int(p["price"]), int(p["disc_price"]), int(p["round"])
        extra = (f"  (list ${lst}, rd {rd}, -{int(DISCOUNT_PER_ROUND * (rd - 1) * 100)}%)"
                 if r["price_col"] == "disc_price" and dsc != lst else "")
        print(f"   ${int(p[r['price_col']]):>3}  {p['position']:<4} "
              f"{p['player_name']:<24} {p['nfl_team']:<4} {p['proj_points']:>6.0f} pts{extra}")
    print(f"\n   starters ${r['spend']} + ${BENCH} bench = ${r['spend'] + BENCH} of ${BUDGET}")
    # round feasibility: no more than MAX_PER_ROUND buys in any round
    if r["price_col"] == "disc_price":
        cnt = r["starters"]["round"].value_counts()
        bad = cnt[cnt > MAX_PER_ROUND]
        print(f"   rounds used: {dict(sorted(cnt.items()))}")
        print("   CHECK: " + ("LEGAL - max 2 buys per round"
                              if bad.empty else f"VIOLATION in rounds {list(bad.index)}"))


show(d1)
show(d2)

print("\n" + "=" * 78)
print("VERDICT")
print("=" * 78)
diff = d2["points"] - d1["points"]
print(f"  max-output roster : {d1['points']} pts, starters cost ${d1['spend']}")
print(f"  discount roster   : {d2['points']} pts, starters cost ${d2['spend']}")
print(f"  difference        : {diff:+.1f} pts ({100 * diff / d1['points']:+.1f}%)")
print("\n  one starter tier is worth ~78 pts at WR and ~119 at RB, for scale.")
