"""Smashes measured in STARTER TIERS, not absolute finish. (2017-2025)

Jamie's correction to the earlier "top-3 = elite" framing:

  "If I pay $50 for a player they pretty much need to be top 3 or it's a
   problem. But say I pay $5 for a WR and he hits as a top-12 WR - that's a
   smash, because now I have a WR1 in my WR3 spot. That's a huge matchup
   advantage."

So value is relative to (a) the slot you are filling and (b) what you paid,
not to an absolute leaderboard. This league starts 1 QB / 2 RB / 3 WR / 1 TE
/ 1 K with no FLEX, so with 12 teams:

    pos_tier = ceil(positional_finish / teams)

A WR finishing WR12 is tier 1 ("WR1 quality"), WR30 is tier 3 ("WR3 quality").
Getting a tier-1 player into your WR3 slot is +2 tiers of edge. A $50 player
who returns tier 2 has cost you money even though he "started".

Run:  python analyze_tier_surplus.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata", "analysis")
os.makedirs(OUT, exist_ok=True)
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))

CAP = 8          # everything this deep or worse is equally useless
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1}

df = pd.read_sql("""
    SELECT d.season, d.franchise, d.price, d.position, f.points, f.pos_rank
    FROM draft_picks d
    LEFT JOIN final_ranks f
      ON f.season = d.season AND f.player_key = d.player_key
    WHERE d.position IN ('QB','RB','WR','TE','K')
""", con)
df["points"] = df["points"].fillna(0.0)
df["teams"] = df["season"].map(lambda s: 10 if s == 2020 else 12)

# realized starter tier; never-played / unranked falls to the cap
df["pos_tier"] = np.ceil(df["pos_rank"] / df["teams"]).fillna(CAP).clip(upper=CAP).astype(int)
df["slots"] = df["position"].map(SLOTS)
df["startable"] = df["pos_tier"] <= df["slots"]

TIERS = [0, 2, 5, 10, 20, 35, 100]
LABELS = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
df["price_tier"] = pd.cut(df["price"], bins=TIERS, labels=LABELS)


def block(t):
    print("\n" + "=" * 76 + f"\n{t}\n" + "=" * 76)


# --------------------------------------------- 1. what is a tier worth?
block("1. WHAT IS ONE STARTER TIER ACTUALLY WORTH? (mean season points)")
w = df[df["pos_tier"] < CAP].pivot_table(index="pos_tier", columns="position",
                                         values="points", aggfunc="mean")
print(w.round(0).to_string())
print("\ngap from tier 1 to tier 3 (the edge Jamie describes at WR):")
for p in ["QB", "RB", "WR", "TE"]:
    if 1 in w.index and 3 in w.index and p in w:
        print(f"  {p}: tier1 {w.loc[1, p]:.0f} - tier3 {w.loc[3, p]:.0f} "
              f"= {w.loc[1, p] - w.loc[3, p]:+.0f} pts/season")

# ------------------------------------- 2. what tier does each price buy?
block("2. WHAT STARTER TIER DID EACH PRICE ACTUALLY BUY? (median realized tier)")
med = df.pivot_table(index="position", columns="price_tier", values="pos_tier",
                     aggfunc="median", observed=True)
cnt = df.pivot_table(index="position", columns="price_tier", values="price",
                     aggfunc="size", observed=True)
print(med.where(cnt >= 8).to_string())
print("\n(lower is better. This is the market's actual delivery curve.)")

# ------------------------------------------------ 3. price-relative smash
block("3. SMASH = BEAT YOUR PRICE'S EXPECTED TIER BY >=2 TIERS")
print("Expected tier is fitted per position from price, so the bar scales with")
print("cost: a $50 player must return tier 1, a $5 player only needs ~tier 3.\n")
df["exp_tier"] = np.nan
for pos, g in df.groupby("position"):
    if len(g) < 25:
        continue
    xs = np.log(g["price"].clip(lower=1))
    deg = 2 if g["price"].nunique() > 5 else 1
    df.loc[g.index, "exp_tier"] = np.polyval(np.polyfit(xs, g["pos_tier"], deg), xs)
df["tier_surplus"] = df["exp_tier"] - df["pos_tier"]
df["smash"] = df["tier_surplus"] >= 2
df["price_bust"] = df["tier_surplus"] <= -2

s = df.groupby("price_tier", observed=True).agg(
    picks=("price", "size"), avg_price=("price", "mean"),
    exp_tier=("exp_tier", "mean"), got_tier=("pos_tier", "mean"),
    smash=("smash", "mean"), bust=("price_bust", "mean"))
s["smash"] = (s["smash"] * 100).round(1)
s["bust"] = (s["bust"] * 100).round(1)
s["smashes_per_$100"] = (100 * s["smash"] / 100 / s["avg_price"]).round(2)
print(s.round(2).to_string())

print("\n!! LIMITATION of the >=2-tier threshold: it is not available to every")
print("   pick. A $36+ player's expected tier is already ~2.1, so beating it by")
print("   2 requires tier 0.1 -- impossible, hence the 0.0% smash rate. Same at")
print("   QB and TE, where even $1-2 picks are expected around tier 2. The")
print("   metric therefore only measures cheap RB/WR. Section 5's tier-1 rate")
print("   is well-defined for every position and price and is the better lens.")

block("4. SMASH RATE BY POSITION x PRICE  (% beating their price by 2+ tiers)")
sm = df.pivot_table(index="position", columns="price_tier", values="smash",
                    aggfunc="mean", observed=True)
print((sm * 100).where(cnt >= 8).round(0).to_string())
print("(QB/TE zeros are the artifact described above, not a real finding.)")
print("\nsmashes per $100 spent:")
pr = df.pivot_table(index="position", columns="price_tier", values="price",
                    aggfunc="mean", observed=True)
print((100 * sm / pr).where(cnt >= 8).round(2).to_string())

block("5. THE JAMIE CASE: cheap picks that returned a TOP-SLOT (tier 1) season")
print("i.e. a player good enough for your WR1/RB1/QB1 slot, bought cheap.\n")
df["tier1"] = df["pos_tier"] == 1
t1 = df.pivot_table(index="position", columns="price_tier", values="tier1",
                    aggfunc="mean", observed=True)
print("tier-1 rate %:")
print((t1 * 100).where(cnt >= 8).round(0).to_string())
print("\ntier-1 seasons bought per $100:")
print((100 * t1 / pr).where(cnt >= 8).round(2).to_string())

block("6. DID EXPENSIVE PLAYERS DELIVER? ($36+ picks by realized tier)")
exp = df[df["price"] >= 36]
d = exp.groupby(["position", "pos_tier"]).size().unstack(fill_value=0)
print(d.to_string())
print(f"\n$36+ picks returning tier 1: {(exp['pos_tier'] == 1).mean():.0%}")
print(f"$36+ picks not even startable: {(~exp['startable']).mean():.0%}")

df.to_csv(os.path.join(OUT, "tier_surplus.csv"), index=False, encoding="utf-8-sig")
print(f"\n\nwrote {OUT}/tier_surplus.csv")
