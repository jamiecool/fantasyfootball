"""Test rule 11: "pay the certainty premium less readily than your leaguemates do."

Rule 11 shipped at medium confidence with the honest caveat "theory plus our tier
data; the objective itself is not yet modelled". Weekly data now exists, so the
objective CAN be modelled, and the rule makes three separable claims:

  A. Elite players carry a premium -- priced above their expected-points value.
  B. Price buys FLOOR (certainty), which is what the premium is paid for.
  C. A threshold objective -- make top 6, then win three weeks -- rewards CEILING,
     so that premium is worse value for us than for the rest of the room.

C is the load-bearing claim and the one never tested. If it fails, rule 11 is
wrong. If it holds, there is still a separate question the rule never asks: can
ceiling be bought WITHOUT the premium? If floor and ceiling are the same players,
"pay the premium less readily" is unactionable at the top of the board.

Run:  python analyze_certainty_premium.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
rng = np.random.default_rng(20260811)

BANDS = [0, 2, 5, 10, 20, 35, 200]
LABELS = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
STARTERS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1}
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}


def hdr(t):
    print("\n" + "=" * 84 + f"\n{t}\n" + "=" * 84)


def boot_ci(vals, fn=np.mean, n=2000):
    vals = np.asarray(vals, dtype=float)
    if len(vals) < 3:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(vals), (n, len(vals)))
    s = fn(vals[idx], axis=1)
    return np.percentile(s, 2.5), np.percentile(s, 97.5)


# --------------------------------------------------------------------------
# data: every drafted skill player, his price, his season, his weekly shape
# --------------------------------------------------------------------------
picks = pd.read_sql("""
    SELECT d.season, d.player_key, d.player_name, d.position, d.price, d.franchise,
           f.points, f.pos_rank, f.games
    FROM draft_picks d
    LEFT JOIN final_ranks f ON f.season=d.season AND f.player_key=d.player_key
    WHERE d.position IN ('QB','RB','WR','TE')""", con)
pw = pd.read_sql("SELECT season, player_key, week, points, position FROM player_weeks", con)

wk = pw.groupby(["season", "player_key"]).agg(
    n_wk=("points", "size"), wk_mean=("points", "mean"),
    wk_sd=("points", "std")).reset_index()
picks = picks.merge(wk, on=["season", "player_key"], how="left")
picks["band"] = pd.cut(picks["price"], bins=BANDS, labels=LABELS)
teams_n = picks["season"].map(lambda s: 10 if s == 2020 else 12)
picks["need"] = teams_n * picks["position"].map(SLOTS)
picks["startable"] = picks["pos_rank"].notna() & (picks["pos_rank"] <= picks["need"])
picks["top3"] = picks["pos_rank"].notna() & (picks["pos_rank"] <= 3)
picks["top1"] = picks["pos_rank"] == 1

# points above replacement, same definition the tier work uses
fr = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)
repl = {}
for (s, p), g in fr.groupby(["season", "position"]):
    if p in SLOTS:
        n = (10 if s == 2020 else 12) * SLOTS[p]
        row = g[g.pos_rank == n]
        repl[(s, p)] = row.points.iloc[0] if len(row) else 0
picks["par"] = [max(0.0, (x.points or 0) - repl.get((x.season, x.position), 0))
                for x in picks.itertuples()]

# --------------------------------------------------------------------------
hdr("CLAIM A -- is there a premium? return per dollar by price band")
# --------------------------------------------------------------------------
g = picks.groupby("band", observed=True).agg(
    n=("price", "size"), spend=("price", "sum"), par=("par", "sum"))
g["ret_per_$"] = ((g.par / g.par.sum()) / (g.spend / g.spend.sum())).round(2)
print(g[["n", "ret_per_$"]].to_string())

top = picks.sort_values("price", ascending=False).groupby("season").head(1)
top3 = picks.sort_values("price", ascending=False).groupby("season").head(3)
for lab, sub in [("most expensive pick of the draft", top),
                 ("three most expensive picks", top3)]:
    r = (sub.par.sum() / picks.par.sum()) / (sub.price.sum() / picks.price.sum())
    print(f"\n  {lab:34} n={len(sub):3}  return per dollar {r:.2f}")
print("\n  A premium exists if these sit below 1.00 -- you are paying more per unit")
print("  of production than the market average.")

# --------------------------------------------------------------------------
hdr("CLAIM B -- what does the premium buy: floor or ceiling?")
# --------------------------------------------------------------------------
rows = []
for b, gg in picks.groupby("band", observed=True):
    played = gg[gg.n_wk >= 10]
    lo, hi = boot_ci(gg.top3.astype(float))
    rows.append({
        "band": b, "n": len(gg),
        "startable%": round(100 * gg.startable.mean()),
        "top3%": round(100 * gg.top3.mean(), 1),
        "top3 CI": f"{100*lo:.0f}-{100*hi:.0f}" if not np.isnan(lo) else "—",
        "pos1%": round(100 * gg.top1.mean(), 1),
        "wk CV": round((played.wk_sd / played.wk_mean).median(), 2) if len(played) else np.nan,
    })
print(pd.DataFrame(rows).to_string(index=False))
print("\n  startable% is FLOOR. top3% is CEILING. wk CV is week-to-week volatility")
print("  (SD / mean) among players who actually played 10+ games -- lower = steadier.")

# --------------------------------------------------------------------------
hdr("CLAIM B2 -- can ceiling be bought cheaply? where top-3 seasons come from")
# --------------------------------------------------------------------------
t3 = picks[picks.top3]
share = (t3.groupby("band", observed=True).size() / len(t3) * 100).round(1)
spend = (picks.groupby("band", observed=True).price.sum()
         / picks.price.sum() * 100).round(1)
cmp_ = pd.DataFrame({"% of all top-3 seasons": share, "% of all money": spend})
cmp_["ceiling per $"] = (cmp_.iloc[:, 0] / cmp_.iloc[:, 1]).round(2)
print(cmp_.to_string())
for pos in ["QB", "RB", "WR", "TE"]:
    sub = picks[picks.position == pos]
    cheap = sub[sub.price <= 10]
    print(f"  {pos}: {int(cheap.top3.sum()):2} top-3 seasons from {len(cheap):3} picks "
          f"at $10 or less   ({100*cheap.top3.mean():.1f}%)")

# --------------------------------------------------------------------------
hdr("CLAIM C -- THE TEST. does a threshold objective reward variance?")
# --------------------------------------------------------------------------
# Real team-level weekly scores, built from each franchise's DRAFTED roster.
# Best legal lineup each week among players they drafted -- perfect hindsight, so
# an upper bound, but applied identically to all 106 teams so comparisons hold.
# In-season adds are excluded (they take ~29% of roster spots), so treat the
# absolute level as indicative and the SPREAD as the finding.
pw_pos = pw.merge(picks[["season", "player_key", "franchise"]],
                  on=["season", "player_key"], how="inner")
team_wk = []
for (s, fchise, w), gg in pw_pos.groupby(["season", "franchise", "week"]):
    tot = 0.0
    for pos, k in STARTERS.items():
        if pos == "K":
            continue
        tot += gg[gg.position == pos].points.nlargest(k).sum()
    team_wk.append({"season": s, "franchise": fchise, "week": w, "pts": tot})
team_wk = pd.DataFrame(team_wk)
ts = team_wk[team_wk.week <= 17].groupby(["season", "franchise"]).agg(
    mu=("pts", "mean"), sd=("pts", "std")).reset_index()
print(f"106 franchise-seasons of weekly team scores (drafted roster, best lineup):")
print(f"  weekly team mean : {ts.mu.mean():.1f}  (spread {ts.mu.min():.0f}-{ts.mu.max():.0f})")
print(f"  weekly team SD   : {ts.sd.mean():.1f}  (spread {ts.sd.min():.0f}-{ts.sd.max():.0f})")
MU, SD_LO, SD_HI = ts.mu.mean(), ts.sd.quantile(0.15), ts.sd.quantile(0.85)
print(f"  a STEADY team (15th pct SD) = {SD_LO:.1f};  a SPIKY team (85th pct) = {SD_HI:.1f}")


def simulate(test_sd, test_mu=MU, n_leagues=30000, weeks=13):
    """One test team vs 11 league-average opponents. Returns P(top6), P(title).

    Everything is held equal except the test team's weekly SD, so any difference
    in title rate is attributable to variance alone -- which is exactly the claim.
    """
    made, won, byes = 0, 0, 0
    base_sd = ts.sd.mean()
    for _ in range(n_leagues):
        sc = rng.normal(MU, base_sd, (12, weeks))
        sc[0] = rng.normal(test_mu, test_sd, weeks)
        # round-robin-ish: each week pair teams at random
        wins = np.zeros(12)
        for w in range(weeks):
            order = rng.permutation(12)
            for i in range(0, 12, 2):
                a, b = order[i], order[i + 1]
                if sc[a, w] > sc[b, w]:
                    wins[a] += 1
                else:
                    wins[b] += 1
        pf = sc.sum(axis=1)
        seed = np.lexsort((-pf, -wins))          # wins, then points-for
        if 0 not in seed[:6]:
            continue
        made += 1
        pos = int(np.where(seed == 0)[0][0])
        if pos < 2:
            byes += 1
        # playoffs weeks 15-17: top 2 bye, then two rounds; 3-6 play a round first
        field = list(seed[:6])
        sds = np.array([test_sd if t == 0 else base_sd for t in field])
        mus = np.array([test_mu if t == 0 else MU for t in field])
        r1 = rng.normal(mus, sds)
        alive = [field[0], field[1],
                 field[2] if r1[2] > r1[5] else field[5],
                 field[3] if r1[3] > r1[4] else field[4]]
        if 0 not in alive:
            continue
        sds = np.array([test_sd if t == 0 else base_sd for t in alive])
        mus = np.array([test_mu if t == 0 else MU for t in alive])
        r2 = rng.normal(mus, sds)
        fin = [alive[0] if r2[0] > r2[3] else alive[3],
               alive[1] if r2[1] > r2[2] else alive[2]]
        if 0 not in fin:
            continue
        sds = np.array([test_sd if t == 0 else base_sd for t in fin])
        mus = np.array([test_mu if t == 0 else MU for t in fin])
        r3 = rng.normal(mus, sds)
        if fin[int(np.argmax(r3))] == 0:
            won += 1
    n = n_leagues
    return 100 * made / n, 100 * byes / n, 100 * won / n


print("\n  Equal expected points. ONLY weekly variance differs.")
print(f"  {'weekly SD':>10} {'P(top 6)':>10} {'P(bye)':>9} {'P(title)':>10} {'vs steady':>11}")
res = {}
for lab, sd in [("steady", SD_LO), ("average", ts.sd.mean()), ("spiky", SD_HI),
                ("very spiky", ts.sd.quantile(0.97))]:
    m, b, t = simulate(sd)
    res[lab] = t
    rel = f"{t/res['steady']:.2f}x" if "steady" in res else "—"
    print(f"  {lab:>10} {sd:5.1f} {m:9.1f}% {b:8.1f}% {t:9.2f}% {rel:>11}")

print("\n  Now the same test for a team that is BEHIND on talent -- the case where")
print("  variance is supposed to matter most:")
print(f"  {'weekly SD':>10} {'P(top 6)':>10} {'P(title)':>10}")
for lab, sd in [("steady", SD_LO), ("spiky", SD_HI)]:
    m, b, t = simulate(sd, test_mu=MU * 0.93)
    print(f"  {lab:>10} {sd:5.1f} {m:9.1f}% {t:9.2f}%")
print("\n  ...and for a team AHEAD on talent:")
print(f"  {'weekly SD':>10} {'P(top 6)':>10} {'P(title)':>10}")
for lab, sd in [("steady", SD_LO), ("spiky", SD_HI)]:
    m, b, t = simulate(sd, test_mu=MU * 1.07)
    print(f"  {lab:>10} {sd:5.1f} {m:9.1f}% {t:9.2f}%")

# --------------------------------------------------------------------------
hdr("HOW MUCH IS A POINT OF WEEKLY MEAN WORTH, IN TITLES?")
# --------------------------------------------------------------------------
# Sets the exchange rate: if variance is worth little and mean is worth a lot,
# then buying the best player is right even at a premium.
print(f"  {'weekly mean':>12} {'P(top 6)':>10} {'P(title)':>10}")
for mult in [0.90, 0.95, 1.00, 1.05, 1.10]:
    m, b, t = simulate(ts.sd.mean(), test_mu=MU * mult)
    print(f"  {MU*mult:11.1f} {m:9.1f}% {t:9.2f}%   ({mult:.0%} of average)")

# --------------------------------------------------------------------------
hdr("THE DISCREPANCY -- what does capping your top bid actually cost?")
# --------------------------------------------------------------------------
# Per-dollar metrics say never buy expensive players. But you cannot field a
# roster of $1 players: 16 spots and $200 forces an average of $12.50, so the
# marginal question is points per ROSTER SPOT, not per dollar. That confound is
# what invalidated the VBD finding (rule 15). This test respects the constraint:
# best legal roster under a hard cap on any single bid.
board = pd.read_csv(os.path.join(ROOT, "cleandata", "analysis", "board_2026.csv"))
proj = pd.read_sql("SELECT player_key, proj_points FROM projections WHERE season=2026", con)
bd = board.merge(proj, on="player_key", how="left").dropna(subset=["proj_points"])
bd["est_price"] = bd["est_price"].clip(lower=1).astype(int)
NEED = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}
BUDGET, SPOTS = 200, 16
BENCH = SPOTS - sum(NEED.values())


def best_roster(cap, budget=BUDGET):
    """Exact DP: max projected starter points, every bid <= cap, bench filled at $1+."""
    pool = bd[bd.est_price <= cap]
    # each position: best total points for taking k players at cost c
    per = {}
    for pos, k_need in NEED.items():
        cand = pool[pool.position == pos].nlargest(60, "proj_points")
        best = {(0, 0): 0.0}
        for r in cand.itertuples():
            nxt = dict(best)
            for (k, c), v in best.items():
                if k >= k_need:
                    continue
                key = (k + 1, c + r.est_price)
                if key[1] <= budget and nxt.get(key, -1) < v + r.proj_points:
                    nxt[key] = v + r.proj_points
            best = nxt
        per[pos] = {c: v for (k, c), v in best.items() if k == k_need}
        if not per[pos]:
            return None
    # combine positions over budget
    cur = {0: 0.0}
    for pos in NEED:
        nxt = {}
        for c0, v0 in cur.items():
            for c1, v1 in per[pos].items():
                c = c0 + c1
                if c <= budget - BENCH and nxt.get(c, -1) < v0 + v1:
                    nxt[c] = v0 + v1
        cur = nxt
        if not cur:
            return None
    return max(cur.values())


print(f"  {'max bid':>9} {'starter pts':>13} {'vs uncapped':>13}")
base = best_roster(999)
for cap in [999, 70, 60, 50, 40, 30, 25, 20, 15]:
    v = best_roster(cap)
    if v is None:
        print(f"  {cap:>9} {'no legal roster':>13}")
        continue
    lab = "uncapped" if cap == 999 else f"${cap}"
    print(f"  {lab:>9} {v:13.0f} {100*(v-base)/base:12.1f}%")
