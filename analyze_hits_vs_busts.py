"""Chase hits, or avoid busts and let the room bust for you?

The question assumes hits and busts are two dials you can set independently.
Part 1 checks that. Part 2 asks the question that IS live once you know the
answer: does it matter how BUSTY your opponents are? "Let my leaguemates bust"
is a claim about order statistics -- if eleven other teams swing wildly, the
score that wins the league is the max of eleven wild draws, and the bar moves.
That is a real effect and it is testable.

Run:  python analyze_hits_vs_busts.py
"""
import os
import sqlite3

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
con = sqlite3.connect(os.path.join(ROOT, "cleandata", "fantasy.db"))
rng = np.random.default_rng(909)
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
repl = {}
for (s, p), g in fr.groupby(["season", "position"]):
    if p in SLOTS:
        n = (10 if s == 2020 else 12) * SLOTS[p]
        row = g[g.pos_rank == n]
        repl[(s, p)] = row.points.iloc[0] if len(row) else 0
picks["repl"] = [repl.get((x.season, x.position), 0) for x in picks.itertuples()]
picks["par"] = (picks.points.fillna(0) - picks.repl).clip(lower=0)

# A HIT beats what the room paid for: the player who finished at your PRICE rank.
# A BUST returns nothing above replacement -- the roster spot was burned.
picks["price_rank"] = picks.groupby(["season", "position"]).price.rank(
    ascending=False, method="first")
cp = {(r.season, r.position, int(r.pos_rank)): r.points for r in fr.itertuples()}


def pts_at(season, pos, rank):
    r = int(round(rank))
    while r > 0:
        if (season, pos, r) in cp:
            return cp[(season, pos, r)]
        r -= 1
    return 0.0


picks["expected"] = [pts_at(x.season, x.position, x.price_rank) for x in picks.itertuples()]
picks["hit"] = picks.points.fillna(0) > picks.expected * 1.15     # beat by 15%+
picks["bust"] = picks.par <= 0
BANDS = [0, 2, 5, 10, 20, 35, 200]
LAB = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
picks["band"] = pd.cut(picks.price, bins=BANDS, labels=LAB)

# --------------------------------------------------------------------------
hdr("1. ARE 'HIT' AND 'AVOID BUST' EVEN SEPARATE DIALS?")
# --------------------------------------------------------------------------
g = picks.groupby("band", observed=True).agg(
    n=("price", "size"), hit=("hit", "mean"), bust=("bust", "mean"),
    par_per_pick=("par", "mean"))
g["hit %"] = (100 * g.hit).round(0)
g["bust %"] = (100 * g.bust).round(0)
g["par/pick"] = g.par_per_pick.round(0)
print(g[["n", "hit %", "bust %", "par/pick"]].to_string())
r = np.corrcoef(picks.groupby("band", observed=True).hit.mean(),
                picks.groupby("band", observed=True).bust.mean())[0, 1]
print(f"\n  correlation between a band's hit rate and its bust rate: {r:+.2f}")
print("  If that is strongly NEGATIVE, the same players do both jobs and there is")
print("  no dial to choose between -- 'chase hits' and 'avoid busts' buy the same guy.")

# --------------------------------------------------------------------------
hdr("2. SO WHAT IS THE REAL DIAL? number of shots vs size of shot")
# --------------------------------------------------------------------------
print("  Per DOLLAR, cheap picks hit more often than their cost implies.")
print("  Per ROSTER SPOT, expensive picks win outright. You have 16 spots and $200,")
print("  so the binding question is how to divide, not which kind to like.\n")
for lo, hi, lab in [(1, 2, "$1-2"), (6, 10, "$6-10"), (21, 35, "$21-35"), (36, 200, "$36+")]:
    sub = picks[(picks.price >= lo) & (picks.price <= hi)]
    spots = len(sub)
    dollars = sub.price.sum()
    print(f"  {lab:8} {spots:4} picks, ${dollars:6,}  ->  "
          f"{sub.par.sum()/spots:6.1f} PAR per SPOT   {sub.par.sum()/dollars:5.2f} PAR per $")

# --------------------------------------------------------------------------
hdr("3. THE LIVE QUESTION -- does it pay to be steady when the ROOM is busty?")
# --------------------------------------------------------------------------
# Real team-level weekly scores, drafted rosters, best legal lineup.
pw = pd.read_sql("SELECT season,player_key,week,points,position FROM player_weeks", con)
m = pw.merge(picks[["season", "player_key", "franchise"]], on=["season", "player_key"])
tw = []
for (s, f, w), gg in m.groupby(["season", "franchise", "week"]):
    tw.append({"season": s, "fr": f, "week": w,
               "pts": sum(gg[gg.position == p].points.nlargest(k).sum()
                          for p, k in SLOTS.items())})
tw = pd.DataFrame(tw)
tw = tw[tw.week <= 17]
ts = tw.groupby(["season", "fr"]).agg(mu=("pts", "mean"), sd=("pts", "std")).reset_index()
tw = tw.merge(ts, on=["season", "fr"])
tw["z"] = (tw.pts - tw.mu) / tw.mu
MU = ts.mu.mean()
lo_q, hi_q = ts.sd.quantile(.33), ts.sd.quantile(.67)
POOL = {"steady": tw[tw.sd <= lo_q].z.values,
        "normal": tw.z.values,
        "busty": tw[tw.sd >= hi_q].z.values}
# season-to-season roster quality also varies -- teams are not equally good
TAL_SD = (ts.mu / MU).std()
print(f"  Real weekly team mean {MU:.0f}; team talent SD {100*TAL_SD:.0f}% of mean.")
print(f"  Weekly shape pools: steady sd={POOL['steady'].std():.3f}, "
      f"normal {POOL['normal'].std():.3f}, busty {POOL['busty'].std():.3f}\n")


def sim(my_shape, opp_shape, n=25000, weeks=13):
    """Everyone equal on talent in expectation; only weekly SHAPE differs."""
    mine, opp = POOL[my_shape], POOL[opp_shape]
    made = won = 0
    for _ in range(n):
        tal = 1 + rng.normal(0, TAL_SD, 12)          # who drafted well this year
        sc = np.empty((12, weeks))
        sc[0] = MU * tal[0] * (1 + mine[rng.integers(0, len(mine), weeks)])
        sc[1:] = (MU * tal[1:, None]) * (1 + opp[rng.integers(0, len(opp), (11, weeks))])
        wins = np.zeros(12)
        for w in range(weeks):
            o = rng.permutation(12)
            for i in range(0, 12, 2):
                a, b = o[i], o[i + 1]
                if sc[a, w] > sc[b, w]:
                    wins[a] += 1
                else:
                    wins[b] += 1
        seed = np.lexsort((-sc.sum(1), -wins))
        if 0 not in seed[:6]:
            continue
        made += 1
        fld = list(seed[:6])

        def draw(t):
            pool = mine if t == 0 else opp
            return MU * tal[t] * (1 + pool[rng.integers(0, len(pool))])
        r1 = [draw(t) for t in fld]
        alive = [fld[0], fld[1],
                 fld[2] if r1[2] > r1[5] else fld[5],
                 fld[3] if r1[3] > r1[4] else fld[4]]
        if 0 not in alive:
            continue
        r2 = [draw(t) for t in alive]
        fin = [alive[0] if r2[0] > r2[3] else alive[3],
               alive[1] if r2[1] > r2[2] else alive[2]]
        if 0 not in fin:
            continue
        r3 = [draw(t) for t in fin]
        if fin[int(np.argmax(r3))] == 0:
            won += 1
    return 100 * made / n, 100 * won / n


print(f"  {'MY shape':>10} {'ROOM shape':>12} {'P(top 6)':>10} {'P(title)':>10}")
grid = {}
for opp in ["steady", "normal", "busty"]:
    for me in ["steady", "busty"]:
        mk, wn = sim(me, opp)
        grid[(me, opp)] = wn
        print(f"  {me:>10} {opp:>12} {mk:9.1f}% {wn:9.2f}%")
    d = grid[("busty", opp)] / grid[("steady", opp)]
    print(f"  {'':>10} {'busty/steady':>12} {'':>10} {d:9.2f}x\n")

print("  If the ratio RISES as the room gets bustier, then a wild room raises the")
print("  bar to win and you must match it. If it FALLS, steadiness is rewarded")
print("  exactly when everyone else is throwing away weeks.")
