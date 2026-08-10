"""Sample-size audit of every finding in CLAUDE.md.

Written after two findings were knocked down in consecutive turns, both of which
rested on thin position x tier cells. The pattern was clear enough to check
systematically rather than wait to be caught again.

For each claim: the n behind it and a 95% bootstrap CI. A claim is only as good
as the interval -- if the CI spans the decision boundary (e.g. contains 50% for
a "more often than not" claim, or contains 1.0 for a ratio), it cannot support a
recommendation no matter how clean the point estimate looks.

Run:  python audit_findings.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
rng = np.random.default_rng(0)

d = pd.read_sql("""
    SELECT d.season, d.price, d.position, d.franchise,
           COALESCE(f.points, 0) pts, f.pos_rank, f.games
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season = d.season AND f.player_key = d.player_key
    WHERE d.position IN ('QB','RB','WR','TE','K')
""", con)
TEAMS = d["season"].map(lambda s: 10 if s == 2020 else 12)
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1}
d["need"] = TEAMS * d["position"].map(SLOTS)
d["startable"] = d["pos_rank"].notna() & (d["pos_rank"] <= d["need"])
d["top5"] = d["pos_rank"].notna() & (d["pos_rank"] <= 5)
TIERS = [0, 2, 5, 10, 20, 35, 100]
LABELS = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
d["tier"] = pd.cut(d["price"], bins=TIERS, labels=LABELS)


def ci(vals, n_boot=8000):
    """95% bootstrap CI of the mean."""
    v = np.asarray(vals, dtype=float)
    if len(v) == 0:
        return (np.nan, np.nan)
    b = [rng.choice(v, len(v), replace=True).mean() for _ in range(n_boot)]
    return np.percentile(b, 2.5), np.percentile(b, 97.5)


print("=" * 88)
print("1. POSITION x TIER CELL SIZES  — the source of both retracted findings")
print("=" * 88)
cnt = d.pivot_table(index="position", columns="tier", values="price",
                    aggfunc="size", observed=True)
print(cnt.fillna(0).astype(int).to_string())
thin = [(p, t, int(cnt.loc[p, t])) for p in cnt.index for t in cnt.columns
        if pd.notna(cnt.loc[p, t]) and cnt.loc[p, t] < 25]
print(f"\ncells with n < 25 (too thin to support a recommendation): {len(thin)}")
print("   " + ", ".join(f"{p} {t}={n}" for p, t, n in thin))

print("\n" + "=" * 88)
print("2. THE HEADLINE CLAIMS, WITH INTERVALS")
print("=" * 88)
print(f"{'claim':<46}{'n':>6}{'est':>8}{'95% CI':>18}  verdict")
print("-" * 88)

rows = []


def check(label, vals, boundary, unit="%"):
    v = np.asarray(vals, dtype=float)
    lo, hi = ci(v)
    m = v.mean()
    f = 100 if unit == "%" else 1
    crosses = lo < boundary < hi
    verdict = "WEAK - CI spans " + f"{boundary * f:g}{unit}" if crosses else "supported"
    if len(v) < 25:
        verdict = "THIN (n<25) " + ("- CI spans boundary" if crosses else "")
    print(f"{label:<46}{len(v):>6}{m * f:>7.0f}{unit}"
          f"{f'[{lo * f:.0f}, {hi * f:.0f}]':>18}  {verdict}")
    rows.append({"claim": label, "n": len(v), "est": m, "lo": lo, "hi": hi,
                 "verdict": verdict})


# --- TE claim (Finding 8) --------------------------------------------------
te = d[(d.position == "TE") & (d.price.between(21, 35))]
check("TE $21-35 finishes top-5", te.top5, 0.5)

# --- cheap QB / TE lottery (Finding 5/7) -----------------------------------
for pos in ["QB", "TE", "RB", "WR"]:
    g = d[(d.position == pos) & (d.price <= 2)]
    check(f"{pos} $1-2 is startable", g.startable, 0.5)

# --- elite reliability (Finding 11 supporting claim) -----------------------
for pos in ["RB", "WR"]:
    g = d[(d.position == pos) & (d.price >= 36)]
    check(f"{pos} $36+ is startable", g.startable, 0.5)

# --- the big-sample claims -------------------------------------------------
check("any $1-2 pick is startable", d[d.price <= 2].startable, 0.5)
check("any $36+ pick is startable", d[d.price >= 36].startable, 0.5)

print("\n" + "=" * 88)
print("3. TIER VALUE RATIOS  — the large-sample result that has survived")
print("=" * 88)
fr = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)
rep = {}
for (s, p), g in fr.groupby(["season", "position"]):
    if p in SLOTS:
        n = (10 if s == 2020 else 12) * SLOTS[p]
        r = g[g.pos_rank == n]
        rep[(s, p)] = r.points.iloc[0] if len(r) else 0
d["par"] = [max(0, r.pts - rep.get((r.season, r.position), 0)) for r in d.itertuples()]
g = d.groupby("tier", observed=True).agg(picks=("price", "size"),
                                         spend=("price", "sum"), par=("par", "sum"))
g["ratio"] = (100 * g.par / g.par.sum()) / (100 * g.spend / g.spend.sum())
# bootstrap the ratio by resampling picks
out = []
for t in LABELS:
    sub = d[d.tier == t]
    if not len(sub):
        continue
    bs = []
    for _ in range(2000):
        idx = rng.integers(0, len(d), len(d))
        samp = d.iloc[idx]
        s2 = samp[samp.tier == t]
        if len(s2) and samp.par.sum() > 0 and samp.price.sum() > 0:
            bs.append((s2.par.sum() / samp.par.sum()) / (s2.price.sum() / samp.price.sum()))
    out.append({"tier": t, "picks": len(sub), "ratio": round(g.loc[t, "ratio"], 2),
                "ci_lo": round(np.percentile(bs, 2.5), 2),
                "ci_hi": round(np.percentile(bs, 97.5), 2),
                "crosses_1.0": bool(np.percentile(bs, 2.5) < 1 < np.percentile(bs, 97.5))})
print(pd.DataFrame(out).to_string(index=False))
print("\nratio > 1 = tier returned more value than it cost. CI crossing 1.0 means")
print("we cannot say the tier is mispriced in either direction.")

pd.DataFrame(rows).to_csv(
    os.path.join(ROOT, "cleandata", "analysis", "findings_audit.csv"),
    index=False, encoding="utf-8-sig")
print("\nwrote cleandata/analysis/findings_audit.csv")
