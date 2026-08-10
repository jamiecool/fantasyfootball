"""What did a dollar actually buy, by position and price tier? (2017-2025)

Deliberately assumption-free: no replacement baseline, no valuation model, no
projections. Just the realized relationship between price paid and points
delivered across 1,695 auction picks, which is the thing a draft board needs
and the thing that decides which VBD baseline is right later.

Method notes that matter:
  * A drafted player with no stat line scored ZERO, not "missing" -- he was
    bought and returned nothing (holdouts, retirements, season-ending injuries).
    Dropping those would bias every tier upward.
  * DEF is excluded entirely: nflverse has no team-defense data, so its NULLs
    mean "unknown", not "zero". K is kept (we score it from the rulebook).
  * Scoring environments drift between seasons, so points are indexed against
    the mean drafted skill-player of that same season before pooling.

Run:  python analyze_price_value.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "cleandata", "fantasy.db")
OUT = os.path.join(ROOT, "cleandata", "analysis")
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(DB)

df = pd.read_sql("""
    SELECT d.season, d.franchise, d.price, d.price_share, d.position,
           d.nomination_order, d.price_source,
           f.points, f.pos_rank, f.games
    FROM draft_picks d
    LEFT JOIN final_ranks f
      ON f.season = d.season AND f.player_key = d.player_key
    WHERE d.position IN ('QB','RB','WR','TE','K')
""", con)

df["points"] = df["points"].fillna(0.0)          # drafted, never played -> zero
df["games"] = df["games"].fillna(0)

# index points against that season's mean drafted skill player
season_mean = df.groupby("season")["points"].transform("mean")
df["pts_idx"] = df["points"] / season_mean

# did the pick return a startable season? (starter demand = teams x slots)
TEAMS = df["season"].map(lambda s: 10 if s == 2020 else 12)
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1}
df["need"] = TEAMS * df["position"].map(SLOTS)
df["startable"] = df["pos_rank"].notna() & (df["pos_rank"] <= df["need"])
df["bust"] = df["pos_rank"].isna() | (df["pos_rank"] > df["need"] * 2)

TIERS = [0, 2, 5, 10, 20, 35, 100]
LABELS = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
df["tier"] = pd.cut(df["price"], bins=TIERS, labels=LABELS)


def block(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------- 1. by tier
block("1. WHAT A DOLLAR BOUGHT, BY PRICE TIER (all skill positions, 9 seasons)")
t = df.groupby("tier", observed=True).agg(
    picks=("price", "size"), avg_price=("price", "mean"),
    avg_points=("points", "mean"), median_points=("points", "median"),
    startable=("startable", "mean"), bust=("bust", "mean"))
t["pts_per_$"] = t["avg_points"] / t["avg_price"]
t["share_of_spend"] = df.groupby("tier", observed=True)["price"].sum() / df["price"].sum()
t["share_of_points"] = df.groupby("tier", observed=True)["points"].sum() / df["points"].sum()
for c in ("startable", "bust", "share_of_spend", "share_of_points"):
    t[c] = (t[c] * 100).round(1)
print(t.round(2).to_string())
print("\nNote: pts_per_$ always favours cheap players (a $1 player who scores 50")
print("has 50 pts/$). Read it with startable% and share_of_points, not alone.")

# ------------------------------------------------------- 2. position x tier
block("2. POINTS PER DOLLAR, POSITION x TIER  (blank = fewer than 8 picks)")
piv = df.pivot_table(index="position", columns="tier", values="points",
                     aggfunc="mean", observed=True)
cnt = df.pivot_table(index="position", columns="tier", values="points",
                     aggfunc="size", observed=True)
prc = df.pivot_table(index="position", columns="tier", values="price",
                     aggfunc="mean", observed=True)
ppd = (piv / prc).where(cnt >= 8)
print(ppd.round(2).to_string())
print("\nstartable rate, position x tier:")
sr = df.pivot_table(index="position", columns="tier", values="startable",
                    aggfunc="mean", observed=True)
print((sr * 100).where(cnt >= 8).round(0).to_string())
print("\npick counts:")
print(cnt.to_string())

# ------------------------------------------- 3. cost per startable season
block("3. COST PER STARTABLE SEASON  (baseline-free cross-position comparison)")
print("Comparing raw points across positions is invalid -- QBs simply score more")
print("(2025 replacement: QB 272 pts vs WR 138), so any pooled points-vs-price")
print("curve flatters QBs for reasons that have nothing to do with the market.")
print("Roster slots, though, are RULES not assumptions. So: how many dollars did")
print("it take to buy one startable season at each position? Lower is better.\n")
cps = (df.groupby(["position", "tier"], observed=True)
       .agg(picks=("price", "size"), avg_price=("price", "mean"),
            startable=("startable", "mean")).reset_index())
cps["cost_per_startable"] = (cps["avg_price"] / cps["startable"].replace(0, np.nan)).round(1)
tab = cps.pivot(index="position", columns="tier", values="cost_per_startable")
print(tab.where(cnt >= 8).to_string())
print("\nby position overall:")
o = df.groupby("position").agg(picks=("price", "size"), spend=("price", "sum"),
                               startable=("startable", "sum"))
o["cost_per_startable"] = (o["spend"] / o["startable"].replace(0, np.nan)).round(1)
print(o.sort_values("cost_per_startable").to_string())

# --------------------------- 4. within-position price efficiency (surplus)
block("4. WITHIN-POSITION PRICE EFFICIENCY (surplus vs that position's own curve)")
print("A separate points-vs-price curve is fitted per position, so this asks")
print("only: within this position, which price tiers beat their own market?")
print("Positive = that tier out-returned what its price implied AT THAT POSITION.\n")
df["surplus"] = np.nan
for pos, g in df.groupby("position"):
    if len(g) < 25:
        continue
    xs = np.log(g["price"].clip(lower=1))
    deg = 2 if g["price"].nunique() > 5 else 1
    df.loc[g.index, "surplus"] = g["pts_idx"] - np.polyval(np.polyfit(xs, g["pts_idx"], deg), xs)

sp = df.pivot_table(index="position", columns="tier", values="surplus",
                    aggfunc="mean", observed=True)
print((sp * 100).where(cnt >= 8).round(0).to_string())
print("\n(units: % of a season's mean drafted player. Rows centre near zero by")
print(" construction -- the signal is the PATTERN ACROSS TIERS, not the level.)")

# --------------------------------------------------- 5. does timing matter?
block("5. DOES NOMINATION TIMING MOVE PRICE? (auction-specific)")
n = df[df["nomination_order"].notna()].copy()
n["phase"] = pd.cut(n["nomination_order"], bins=[0, 24, 48, 96, 144, 200],
                    labels=["1-24", "25-48", "49-96", "97-144", "145+"])
print("surplus here is the within-position measure from section 4, so it is not")
print("confounded by which positions happen to go early.\n")
ph = n.groupby("phase", observed=True).agg(
    picks=("price", "size"), avg_price=("price", "mean"),
    avg_points=("points", "mean"), surplus=("surplus", "mean"),
    startable=("startable", "mean"))
ph["surplus_pct"] = (ph["surplus"] * 100).round(1)
ph["startable"] = (ph["startable"] * 100).round(1)
print(ph[["picks", "avg_price", "avg_points", "startable", "surplus_pct"]].round(2).to_string())

print("\nsame, holding price tier fixed (does timing matter beyond price?):")
tp = n.pivot_table(index="tier", columns="phase", values="surplus",
                   aggfunc="mean", observed=True)
tn = n.pivot_table(index="tier", columns="phase", values="surplus",
                   aggfunc="size", observed=True)
print((tp * 100).where(tn >= 8).round(0).to_string())

df.to_csv(os.path.join(OUT, "pick_value.csv"), index=False, encoding="utf-8-sig")
t.round(3).to_csv(os.path.join(OUT, "value_by_tier.csv"), encoding="utf-8-sig")
o.round(3).to_csv(os.path.join(OUT, "cost_per_startable.csv"), encoding="utf-8-sig")
print(f"\n\nwrote per-pick detail + summaries to {OUT}")
