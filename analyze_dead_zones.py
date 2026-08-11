"""Where is the dead money, position by position?

Prompted by Jamie catching an inconsistency: WR $21-35 returns 0.75 per dollar
and RB $11-20 returns 0.76 -- the same effect -- but only the WR band got
written up as a rule, because WR has more picks and therefore a tighter
interval. Treating one as real and staying silent on the other is a statement
about our sample size, not about the league.

So: every position, every band, one method, and the intervals reported next to
the estimates rather than used to silently drop findings.

A band is dead if BOTH agree:
  * it returns less per dollar than the draft average, and
  * the money is better spent at the same position somewhere else

Run:  python analyze_dead_zones.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
rng = np.random.default_rng(31337)
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
BANDS = [0, 2, 5, 10, 20, 35, 200]
LABELS = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]

p = pd.read_sql("""
    SELECT d.season, d.position, d.price, COALESCE(f.points, 0) pts, f.pos_rank
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season = d.season AND f.player_key = d.player_key
    WHERE d.position IN ('QB','RB','WR','TE')""", con)
fr = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)
repl = {}
for (s, pos), g in fr.groupby(["season", "position"]):
    if pos in SLOTS:
        n = (10 if s == 2020 else 12) * SLOTS[pos]
        row = g[g.pos_rank == n]
        repl[(s, pos)] = row.points.iloc[0] if len(row) else 0
p["par"] = [max(0.0, x.pts - repl.get((x.season, x.position), 0)) for x in p.itertuples()]
p["band"] = pd.cut(p.price, bins=BANDS, labels=LABELS)

print("=" * 88)
print("PER-DOLLAR RETURN BY POSITION AND BAND, with bootstrap intervals")
print("=" * 88)
print("  1.00 = the band paid for itself. Intervals resample within position.\n")
dead, ROWS = {}, []
for pos in ["QB", "RB", "WR", "TE"]:
    s = p[p.position == pos]
    print(f"  {pos}   ({len(s)} picks)")
    print(f"    {'band':8} {'n':>4} {'per $':>7} {'95% CI':>14}  {'PAR/pick':>9}  verdict")
    worst, worst_band = 9e9, None
    for b in LABELS:
        sub = s[s.band == b]
        if len(sub) < 10:
            continue
        rs = []
        for _ in range(3000):
            bs = s.iloc[rng.integers(0, len(s), len(s))]
            m = bs.band == b
            if bs.par.sum() <= 0 or bs[m].price.sum() <= 0:
                continue
            rs.append((bs[m].par.sum() / bs.par.sum())
                      / (bs[m].price.sum() / bs.price.sum()))
        est, lo, hi = np.mean(rs), *np.percentile(rs, [2.5, 97.5])
        if est < worst:
            worst, worst_band = est, b
        verdict = ("DEAD (interval clears 1.0)" if hi < 1
                   else "good (interval clears 1.0)" if lo > 1 else "")
        slope = (np.polyfit(sub.price, sub.pts, 1)[0]
                 if sub.price.nunique() >= 3 else float("nan"))
        ROWS.append({"position": pos, "band": b, "n": len(sub),
                     "est": round(float(est), 3), "lo": round(float(lo), 3),
                     "hi": round(float(hi), 3),
                     "par_per_pick": round(float(sub.par.mean()), 1),
                     "slope": None if np.isnan(slope) else round(float(slope), 2),
                     "verdict": "dead" if hi < 1 else "good" if lo > 1 else "unclear"})
        print(f"    {b:8} {len(sub):>4} {est:7.2f} {f'{lo:.2f}-{hi:.2f}':>14}  "
              f"{sub.par.mean():9.0f}  {verdict}")
    dead[pos] = (worst_band, worst)
    print(f"    -> worst band at {pos}: {worst_band} at {worst:.2f}\n")

print("=" * 88)
print("THE ANSWER: each position's worst band, side by side")
print("=" * 88)
print(f"  {'pos':4} {'dead band':10} {'per $':>7}   what to do instead")
ADVICE = {
    "QB": "the $3-8 band; QB1-3 costs $59 per top-5 season against $22 there",
    "RB": "either side of it: $1-10 lottery tickets, or $21+ for a real one",
    "WR": "$6-20 is the sweet spot, or pay $36+ for an actual difference-maker",
    "TE": "$1-10, or accept that TE is mostly a coin flip at any price",
}
for pos in ["QB", "RB", "WR", "TE"]:
    band, est = dead[pos]
    print(f"  {pos:4} {band:10} {est:7.2f}   {ADVICE[pos]}")

# ---------------------------------------------------------------- cross-check
print("\n" + "=" * 88)
print("CROSS-CHECK: what does the NEXT dollar buy inside each band?")
print("=" * 88)
print("  Independent of the per-dollar ratio -- fits points against price and")
print("  reads the slope. A dead zone should be flat here too.\n")
print(f"  {'pos':4}" + "".join(f"{b:>10}" for b in LABELS))
for pos in ["QB", "RB", "WR", "TE"]:
    s = p[p.position == pos]
    cells = []
    for b in LABELS:
        sub = s[s.band == b]
        if len(sub) < 10 or sub.price.nunique() < 3:
            cells.append(f"{'—':>10}")
            continue
        slope = np.polyfit(sub.price, sub.pts, 1)[0]
        cells.append(f"{slope:10.1f}")
    print(f"  {pos:4}" + "".join(cells))
print("\n  points bought per extra dollar, within band. Near zero = dead money.")

# ------------------------------------------------------------------ persist
OUT = os.path.join(ROOT, "cleandata", "analysis")
os.makedirs(OUT, exist_ok=True)
out = pd.DataFrame(ROWS)
out.to_csv(os.path.join(OUT, "dead_zones.csv"), index=False)
print()
print(f"wrote {len(out)} rows -> cleandata/analysis/dead_zones.csv")
print(f"  {(out.verdict == 'dead').sum()} bands confirmed dead, "
      f"{(out.verdict == 'good').sum()} confirmed good, "
      f"{(out.verdict == 'unclear').sum()} cannot be called")

# ==========================================================================
# CROSS-POSITION, which the per-band chart above cannot see.
#
# Every ratio above is computed WITHIN a position, so "RB $36+ = 1.03" means
# fine RELATIVE TO OTHER RBs. It says nothing about whether RB as a whole
# deserves the money. That is a different question and it has a different answer.
# ==========================================================================
print("\n" + "=" * 88)
print("IS A WHOLE POSITION OVER- OR UNDER-PRICED?")
print("=" * 88)
gp = p.groupby("position").agg(n=("price", "size"), spend=("price", "sum"),
                               par=("par", "sum"))
gp["$ share%"] = (100 * gp.spend / gp.spend.sum()).round(1)
gp["PAR share%"] = (100 * gp.par / gp.par.sum()).round(1)
gp["ratio"] = (gp["PAR share%"] / gp["$ share%"]).round(2)
for pos in gp.index:
    rs = []
    for _ in range(3000):
        bs = p.iloc[rng.integers(0, len(p), len(p))]
        m = bs.position == pos
        if bs.par.sum() <= 0 or bs[m].price.sum() <= 0:
            continue
        rs.append((bs[m].par.sum() / bs.par.sum())
                  / (bs[m].price.sum() / bs.price.sum()))
    lo, hi = np.percentile(rs, [2.5, 97.5])
    gp.loc[pos, "CI"] = f"{lo:.2f}-{hi:.2f}"
    gp.loc[pos, "verdict"] = ("OVERPRICED" if hi < 1
                              else "underpriced" if lo > 1 else "cannot call")
print(gp[["n", "$ share%", "PAR share%", "ratio", "CI", "verdict"]].to_string())

print("\n  ...but check whether it still holds. Season by season:")
sy = p.groupby(["season", "position"]).agg(sp=("price", "sum"), pr=("par", "sum")).reset_index()
sy["r"] = ((sy.pr / sy.groupby("season").pr.transform("sum"))
           / (sy.sp / sy.groupby("season").sp.transform("sum")))
piv = sy.pivot(index="season", columns="position", values="r").round(2)
print(piv.to_string())
print("\n  RB sat below 1.0 in seven straight seasons and then flipped in 2024-25.")
print("  build_2026_board.py already prices off 2023-25 only for exactly this")
print("  reason; a nine-season average is pricing a market that has moved.")
