"""What is the right WR allocation? Barbell like RB, or something else?

WR is structurally unlike the other positions in this league: THREE starters and
no FLEX, so 36 WRs start every week against 24 RBs, 12 QBs and 12 TEs. That moves
replacement level far deeper and should flatten the value curve -- the question is
whether it flattens it enough to change the shape of the buy.

Rule 7 says barbell RB. Rule 8 only says elite WR production costs $36+; it never
said how to SPEND at WR. This settles that, using the same machinery for RB as a
control so the two are comparable.

The test that matters is the third one: hold a WR budget fixed, deal real
historical outcomes conditioned on price, and score BEST 3 OF 5 -- because you
start three but own five, and the bench is where a bust gets covered. Scoring
only the intended starters is what made an earlier version of the roster-shape
work overrate concentration.

Run:  python analyze_wr_shape.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
rng = np.random.default_rng(4242)
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}


def hdr(t):
    print("\n" + "=" * 86 + f"\n{t}\n" + "=" * 86)


picks = pd.read_sql("""
    SELECT d.season, d.player_key, d.player_name, d.position, d.price, d.franchise,
           f.points, f.pos_rank
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season=d.season AND f.player_key=d.player_key
    WHERE d.position IN ('QB','RB','WR','TE')""", con)
fr = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)

# --------------------------------------------------------------------------
hdr("1. THE VALUE CURVE -- how fast does each position fall away?")
# --------------------------------------------------------------------------
# Normalised to each position's own last starter, so positions are comparable:
# 1.00 = the worst player you could start there.
print(f"  {'':6}" + "".join(f"{('rk'+str(r)):>8}" for r in [1, 3, 6, 12, 18, 24, 36, 48]))
curves = {}
for pos in ["QB", "RB", "WR", "TE"]:
    last = 12 * SLOTS[pos]
    vals = []
    for rk in [1, 3, 6, 12, 18, 24, 36, 48]:
        v = fr[(fr.position == pos) & (fr.pos_rank == rk)].groupby("season").points.first()
        base = fr[(fr.position == pos) & (fr.pos_rank == last)].groupby("season").points.first()
        vals.append((v / base).mean())
    curves[pos] = vals
    print(f"  {pos:6}" + "".join(f"{v:8.2f}" for v in vals))
print(f"\n  Each position's last starter is rank {12*SLOTS['QB']} QB / {12*SLOTS['RB']} RB "
      f"/ {12*SLOTS['WR']} WR / {12*SLOTS['TE']} TE.")
print("  A FLAT curve means the elite guy is barely better than the replaceable one.")

# --------------------------------------------------------------------------
hdr("2. WHAT EACH PRICE BAND RETURNS, WR vs RB")
# --------------------------------------------------------------------------
B = [0, 2, 5, 10, 20, 35, 200]
L = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
picks["band"] = pd.cut(picks["price"], bins=B, labels=L)
repl = {}
for (s, p), g in fr.groupby(["season", "position"]):
    if p in SLOTS:
        n = (10 if s == 2020 else 12) * SLOTS[p]
        row = g[g.pos_rank == n]
        repl[(s, p)] = row.points.iloc[0] if len(row) else 0
picks["par"] = [max(0.0, (x.points or 0) - repl.get((x.season, x.position), 0))
                for x in picks.itertuples()]

for pos in ["WR", "RB"]:
    sub = picks[picks.position == pos]
    need = sub["season"].map(lambda s: (10 if s == 2020 else 12)) * SLOTS[pos]
    sub = sub.assign(startable=sub.pos_rank.notna() & (sub.pos_rank <= need),
                     top12=sub.pos_rank.notna() & (sub.pos_rank <= 12))
    g = sub.groupby("band", observed=True).agg(
        n=("price", "size"), avg_price=("price", "mean"),
        startable=("startable", "mean"), top12=("top12", "mean"),
        par_per_pick=("par", "mean"), spend=("price", "sum"), par=("par", "sum"))
    g["par_per_$"] = ((g.par / g.par.sum()) / (g.spend / g.spend.sum())).round(2)
    g["startable"] = (100 * g.startable).round(0)
    g["top12"] = (100 * g.top12).round(0)
    g["par_per_pick"] = g.par_per_pick.round(0)
    g["avg_price"] = g.avg_price.round(0)
    print(f"\n  {pos}   (startable = top {12*SLOTS[pos]}; top12 = a true difference-maker)")
    print(g[["n", "avg_price", "startable", "top12", "par_per_pick", "par_per_$"]]
          .to_string())

# --------------------------------------------------------------------------
hdr("3. THE TEST -- fixed WR budget, real outcomes, best 3 of 5")
# --------------------------------------------------------------------------
wr_spend = picks[picks.position == "WR"].groupby(["season", "franchise"]).price.sum()
print(f"  What teams actually spend on WR: median ${wr_spend.median():.0f}, "
      f"quartiles ${wr_spend.quantile(.25):.0f}-${wr_spend.quantile(.75):.0f}")


def outcome_pool(pos, price, window=0.30, floor=6):
    """Real season outcomes for players bought near this price. Undrafted-quality
    misses included as zeros -- a pick that never played is a real result."""
    sub = picks[picks.position == pos]
    lo, hi = price * (1 - window), price * (1 + window)
    pool = sub[(sub.price >= max(1, lo)) & (sub.price <= hi + 1)]
    if len(pool) < floor:                       # widen until it is not noise
        sub = sub.assign(d=(sub.price - price).abs())
        pool = sub.nsmallest(max(floor, 25), "d")
    return pool.points.fillna(0).values


def score_shape(prices, pos="WR", start=3, n=20000):
    """prices = what you pay for each player you own. Score best `start` of them."""
    pools = [outcome_pool(pos, p) for p in prices]
    draws = np.stack([p[rng.integers(0, len(p), n)] for p in pools])   # (players, n)
    best = np.sort(draws, axis=0)[-start:].sum(axis=0)
    return best.mean(), np.percentile(best, 10), np.percentile(best, 90)


BUDGET = int(round(wr_spend.median() / 5) * 5)
print(f"\n  Every shape below spends ${BUDGET} on FIVE wide receivers and starts the")
print(f"  best three. Outcomes dealt from real WRs bought at those prices, 2017-2025.\n")
SHAPES = [
    ("one bat + scraps",      [BUDGET - 4 - 6, 2, 2, 3, 3]),
    ("two bats + scraps",     [(BUDGET - 8) // 2, (BUDGET - 8) // 2, 2, 3, 3]),
    ("barbell: 1 elite + mid", [BUDGET - 30, 12, 10, 4, 4]),
    ("three even starters",   [(BUDGET - 6) // 3, (BUDGET - 6) // 3, (BUDGET - 6) // 3, 3, 3]),
    ("flat five",             [BUDGET // 5] * 5),
    ("mid-heavy, no elite",   [22, 20, 18, 8, BUDGET - 68]),
]
rows = []
for lab, pr in SHAPES:
    pr = [max(1, int(x)) for x in pr]
    if abs(sum(pr) - BUDGET) > 3:
        pr[0] += BUDGET - sum(pr)
    m, p10, p90 = score_shape(pr)
    rows.append({"shape": lab, "prices": "-".join(f"${x}" for x in sorted(pr, reverse=True)),
                 "spend": sum(pr), "exp_pts": round(m), "bad case (p10)": round(p10),
                 "good case (p90)": round(p90)})
out = pd.DataFrame(rows).sort_values("exp_pts", ascending=False)
print(out.to_string(index=False))
best, worst = out.exp_pts.max(), out.exp_pts.min()
print(f"\n  spread best-to-worst: {best-worst} pts ({100*(best-worst)/worst:.1f}%)")

# --------------------------------------------------------------------------
hdr("4. CONTROL -- same machinery on RB, where the barbell rule already exists")
# --------------------------------------------------------------------------
rb_spend = picks[picks.position == "RB"].groupby(["season", "franchise"]).price.sum()
RB_BUDGET = int(round(rb_spend.median() / 5) * 5)
print(f"  Median RB spend ${RB_BUDGET}; four RBs owned, best TWO start.\n")
RB_SHAPES = [
    ("one bat + scraps",   [RB_BUDGET - 6, 2, 2, 2]),
    ("two bats",           [(RB_BUDGET - 4) // 2, (RB_BUDGET - 4) // 2, 2, 2]),
    ("barbell 1 elite+mid", [RB_BUDGET - 22, 14, 4, 4]),
    ("all mid-tier",       [RB_BUDGET // 4] * 4),
]
rows = []
for lab, pr in RB_SHAPES:
    pr = [max(1, int(x)) for x in pr]
    if abs(sum(pr) - RB_BUDGET) > 3:
        pr[0] += RB_BUDGET - sum(pr)
    m, p10, p90 = score_shape(pr, pos="RB", start=2)
    rows.append({"shape": lab, "prices": "-".join(f"${x}" for x in sorted(pr, reverse=True)),
                 "exp_pts": round(m), "bad case (p10)": round(p10),
                 "good case (p90)": round(p90)})
print(pd.DataFrame(rows).sort_values("exp_pts", ascending=False).to_string(index=False))

# --------------------------------------------------------------------------
hdr("5. HOW MUCH OF THE ROOM'S WR MONEY GOES WHERE, AND DID IT WORK?")
# --------------------------------------------------------------------------
wr = picks[picks.position == "WR"]
tot = wr.price.sum()
sh = wr.groupby("band", observed=True).agg(picks=("price", "size"), spend=("price", "sum"))
sh["% of WR money"] = (100 * sh.spend / tot).round(1)
sh["% of WR PAR"] = (100 * wr.groupby("band", observed=True).par.sum() / wr.par.sum()).round(1)
print(sh[["picks", "% of WR money", "% of WR PAR"]].to_string())
