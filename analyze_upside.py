"""Where do league-winning seasons come from? (2017-2025)

Jamie's framing: the goal is to finish 1st, not to post a winning record. A high
startable rate gets you the latter. What wins is hitting players who massively
out-produce what they cost. So this file optimises the TAIL, not the mean.

Definitions used here:
  smash   - top decile of within-position surplus (points delivered minus what
            that price normally buys AT THAT POSITION). Price-relative, so a $1
            RB6 counts and a $60 RB1 who merely met expectations does not.
  elite   - top-3 finish at the position, regardless of price. The raw
            production that actually wins weeks.

Run:  python analyze_upside.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata", "analysis")
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))

df = pd.read_sql("""
    SELECT d.season, d.franchise, d.price, d.position, d.nomination_order,
           f.points, f.pos_rank
    FROM draft_picks d
    LEFT JOIN final_ranks f
      ON f.season = d.season AND f.player_key = d.player_key
    WHERE d.position IN ('QB','RB','WR','TE','K')
""", con)
df["points"] = df["points"].fillna(0.0)
df["pts_idx"] = df["points"] / df.groupby("season")["points"].transform("mean")

TEAMS = df["season"].map(lambda s: 10 if s == 2020 else 12)
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1}
df["need"] = TEAMS * df["position"].map(SLOTS)
df["startable"] = df["pos_rank"].notna() & (df["pos_rank"] <= df["need"])
df["elite"] = df["pos_rank"].notna() & (df["pos_rank"] <= 3)

TIERS = [0, 2, 5, 10, 20, 35, 100]
LABELS = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
df["tier"] = pd.cut(df["price"], bins=TIERS, labels=LABELS)

# within-position surplus: points beyond what this price normally buys here
df["surplus"] = np.nan
for pos, g in df.groupby("position"):
    if len(g) < 25:
        continue
    xs = np.log(g["price"].clip(lower=1))
    deg = 2 if g["price"].nunique() > 5 else 1
    df.loc[g.index, "surplus"] = g["pts_idx"] - np.polyval(np.polyfit(xs, g["pts_idx"], deg), xs)
df["smash"] = df["surplus"] >= df["surplus"].quantile(0.90)


def block(t):
    print("\n" + "=" * 76 + f"\n{t}\n" + "=" * 76)


# ------------------------------------------------- 1. does upside beat mean?
block("1. DOES HITTING SMASHES PREDICT A BETTER ROSTER THAN JUST BEING SOLID?")
print("For each team-season, count smashes / startables / elites, then correlate")
print("each against that team's best-lineup points from drafted players.\n")
NEED = {"QB": 1, "WR": 3, "RB": 2, "TE": 1, "K": 1}
rows = []
for (s, fr), g in df.groupby(["season", "franchise"]):
    lineup = sum(g[g.position == p].nlargest(n, "points")["points"].sum()
                 for p, n in NEED.items())
    rows.append({"season": s, "franchise": fr, "lineup_pts": lineup,
                 "smashes": int(g["smash"].sum()), "startables": int(g["startable"].sum()),
                 "elites": int(g["elite"].sum()), "spend": g["price"].sum()})
tm = pd.DataFrame(rows)
tm["z_lineup"] = tm.groupby("season")["lineup_pts"].transform(lambda x: (x - x.mean()) / x.std())
print(f"team-seasons: {len(tm)}")
for col in ["smashes", "startables", "elites"]:
    z = tm.groupby("season")[col].transform(lambda x: (x - x.mean()) / x.std(ddof=0)).fillna(0)
    print(f"  corr(z_{col:<11}, z_lineup_points) = {z.corr(tm['z_lineup']):+.3f}")
print("\nAlso: how often did the season's best-drafted-roster team lead in each?")
top = tm.loc[tm.groupby("season")["lineup_pts"].idxmax()]
for col in ["smashes", "startables", "elites"]:
    lead = tm.loc[tm.groupby("season")[col].idxmax()][["season", "franchise"]]
    merged = top.merge(lead, on="season", suffixes=("_best", "_lead"))
    hit = (merged["franchise_best"] == merged["franchise_lead"]).mean()
    print(f"  best roster also led the league in {col:<11}: {hit:.0%} of seasons")

# ------------------------------------------- 2. where do elite seasons come from
block("2. WHAT DID ELITE SEASONS (top-3 at position) ACTUALLY COST?")
el = df[df["elite"]]
g = el.groupby("tier", observed=True).agg(elite_seasons=("price", "size"),
                                          avg_price=("price", "mean"))
g["pct_of_all_elite"] = (100 * g["elite_seasons"] / len(el)).round(1)
allp = df.groupby("tier", observed=True).size()
g["picks_in_tier"] = allp
g["rate"] = (100 * g["elite_seasons"] / allp).round(1)
print(g.to_string())
print(f"\ntotal elite seasons among drafted players: {len(el)}")
print("rate = chance a pick in that tier produced a top-3 positional season")

# ------------------------------------------ 3. smashes per dollar (allocation)
block("3. SMASHES PER $100 SPENT  (where upside is cheapest to buy)")
s = df.groupby("tier", observed=True).agg(picks=("price", "size"),
                                          avg_price=("price", "mean"),
                                          smash_rate=("smash", "mean"),
                                          elite_rate=("elite", "mean"))
s["smashes_per_$100"] = (100 * s["smash_rate"] / s["avg_price"]).round(2)
s["elites_per_$100"] = (100 * s["elite_rate"] / s["avg_price"]).round(2)
s["smash_rate"] = (s["smash_rate"] * 100).round(1)
s["elite_rate"] = (s["elite_rate"] * 100).round(1)
print(s.round(2).to_string())

block("4. SMASH RATE AND ELITE RATE, POSITION x TIER")
cnt = df.pivot_table(index="position", columns="tier", values="price",
                     aggfunc="size", observed=True)
for name, col in [("smash rate %", "smash"), ("elite (top-3) rate %", "elite")]:
    p = df.pivot_table(index="position", columns="tier", values=col,
                       aggfunc="mean", observed=True)
    print(f"\n{name}:")
    print((p * 100).where(cnt >= 8).round(0).to_string())

block("5. EXPECTED ELITE SEASONS PER $100, POSITION x TIER")
pe = df.pivot_table(index="position", columns="tier", values="elite",
                    aggfunc="mean", observed=True)
pp = df.pivot_table(index="position", columns="tier", values="price",
                    aggfunc="mean", observed=True)
print((100 * pe / pp).where(cnt >= 8).round(2).to_string())

tm.to_csv(os.path.join(OUT, "team_season_upside.csv"), index=False, encoding="utf-8-sig")
df.to_csv(os.path.join(OUT, "pick_upside.csv"), index=False, encoding="utf-8-sig")
print(f"\n\nwrote {OUT}")
