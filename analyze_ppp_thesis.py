"""Jamie's thesis, tested in two halves.

  A. The room drafts off generic SUPERFLEX cheat sheets, which assume no FLEX,
     so running backs are systematically undervalued here.
  B. Therefore the play is three top backs, using the flex to bank a large
     positional delta, and minimising the losses elsewhere.

A is a claim about the MARKET: does the board's ordering match a no-flex
valuation better than a flex-aware one? B is a claim about STRATEGY and needs a
simulation.

Valuation uses `exp` -- ESPN's projection deflated by this league's measured
position ratio. Projections never rank the board here, but comparing two
hypothetical valuations of the same players is exactly the roster-evaluation job
a projection is the right currency for.
"""
import json
import os
from collections import defaultdict

import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(ROOT, "cleandata", "analysis", "ppp_data.json"),
                   encoding="utf-8"))
TEAMS, RDS = 12, 18
BAR = "=" * 76

# realised replacement, measured in PPP-7 from nflverse 2017-25 at full PPR
REPL_FLEX = {"QB": 179.5, "RB": 158.3, "WR": 155.3, "TE": 144.5}
REPL_NOFLEX = {"QB": 179.5, "RB": 176.7, "WR": 170.3, "TE": 144.5}

b = pd.DataFrame([p for p in D["board"] if p["rank"] is not None])
b["vor_flex"] = b.exp - b.position.map(REPL_FLEX) if False else \
    b["exp"] - b["pos"].map(REPL_FLEX)
b["vor_noflex"] = b["exp"] - b["pos"].map(REPL_NOFLEX)
b["rk_flex"] = b.vor_flex.rank(ascending=False, method="first")
b["rk_noflex"] = b.vor_noflex.rank(ascending=False, method="first")

print(f"{BAR}\n  A. DOES THE BOARD LOOK NO-FLEX OR FLEX-AWARE?\n{BAR}")
print("  The board's order is Underdog within position + this league's own pick")
print("  curve across positions, i.e. how the room actually behaves.\n")
for lab, col in (("no-flex valuation", "rk_noflex"), ("flex-aware valuation", "rk_flex")):
    print(f"  board order vs {lab:<22} rho = "
          f"{b['rank'].corr(b[col], method='spearman'):.4f}")

print("\n  Mean board rank minus valuation rank, by position")
print("  (positive = the room takes them LATER than that valuation says)\n")
print(f"{'pos':>5}{'n':>5}{'vs no-flex':>13}{'vs flex-aware':>16}{'difference':>13}")
for p in ("QB", "RB", "WR", "TE"):
    g = b[b.pos == p]
    a = (g["rank"] - g.rk_noflex).mean()
    f = (g["rank"] - g.rk_flex).mean()
    print(f"{p:>5}{len(g):>5}{a:>13.1f}{f:>16.1f}{f-a:>13.1f}")

print("\n  Top 36 of the board against each valuation's top 36:")
for lab, col in (("board (the room)", "rank"), ("no-flex", "rk_noflex"),
                 ("flex-aware", "rk_flex")):
    top = b.nsmallest(36, col)
    c = top.pos.value_counts()
    print(f"    {lab:<18}" + "  ".join(f"{k} {int(c.get(k,0)):>2}"
                                       for k in ("QB", "RB", "WR", "TE")))

# ---------------------------------------------------------------- B ---------
print(f"\n\n{BAR}\n  B. IS 'THREE TOP BACKS' THE PLAY FROM THE 1.01?\n{BAR}")
SLOT = 1
PICKS = [(r - 1) * TEAMS + (SLOT if r % 2 else TEAMS + 1 - SLOT)
         for r in range(1, RDS + 1)]
ranked = sorted([p for p in D["board"] if p["rank"] is not None],
                key=lambda p: p["rank"])
stream = {q: sorted([p for p in D["board"] if p["pos"] == q],
                    key=lambda x: -(x["exp"] or 0)) for q in ("K", "DEF")}
NEED = [("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("SUPERFLEX", 1),
        ("FLEX", 1), ("K", 1), ("DEF", 1)]


def start_points(roster):
    by = defaultdict(list)
    for p in roster:
        by[p["pos"]].append(p)
    for k in by:
        by[k].sort(key=lambda x: -(x["exp"] or 0))
    used, tot, filled = set(), 0.0, 0
    def take(q):
        nonlocal tot, filled
        for p in by.get(q, []):
            if id(p) not in used:
                used.add(id(p)); tot += p["exp"] or 0; filled += 1; return True
        return False
    for q, n in NEED:
        for _ in range(n):
            if q == "SUPERFLEX":
                take("QB") or take("RB") or take("WR") or take("TE")
            elif q == "FLEX":
                take("RB") or take("WR") or take("TE")
            else:
                take(q)
    return tot, filled


def run(plan):
    taken, roster = set(), []
    for rd, no in enumerate(PICKS, start=1):
        want = plan(rd)
        if want in ("K", "DEF"):
            pick = next((p for p in stream[want] if id(p) not in taken), None)
        else:
            av = [p for p in ranked if p["rank"] >= no and id(p) not in taken]
            if want:
                av = [p for p in av if p["pos"] == want] or av
            pick = av[0] if av else None
        if pick:
            taken.add(id(pick)); roster.append(pick)
    return roster


def mk(rb_rounds, qb_rounds):
    def plan(rd):
        if rd == 13: return "K"
        if rd == 15: return "DEF"
        if rd in rb_rounds: return "RB"
        if rd in qb_rounds: return "QB"
        return None
    return plan


QB = {8, 9}                                    # the PPP-1/PPP-2 optimum
STRATS = {
    "0 forced RB (pure best available)": mk(set(), QB),
    "1 RB early (rd 1)": mk({1}, QB),
    "2 RB early (rds 1-2)": mk({1, 2}, QB),
    "3 RB early (rds 1,2,3)  <- the thesis": mk({1, 2, 3}, QB),
    "3 RB, spread (rds 1,3,5)": mk({1, 3, 5}, QB),
    "4 RB early (rds 1-4)": mk({1, 2, 3, 4}, QB),
    "3 RB early + QB at 7,9": mk({1, 2, 3}, {7, 9}),
    "3 RB early + QB at 2,3": mk({1, 4, 5}, {2, 3}),
}
print(f"{'strategy':<42}{'start pts':>10}{'slots':>7}   roster")
res = []
for name, plan in STRATS.items():
    r = run(plan)
    pts, filled = start_points(r)
    c = defaultdict(int)
    for p in r: c[p["pos"]] += 1
    shape = " ".join(f"{k}{c[k]}" for k in ("QB","RB","WR","TE","K","DEF") if c[k])
    res.append((pts, name, filled, shape))
    print(f"{name:<42}{pts:>10.1f}{filled:>7}   {shape}")
print("\nbest to worst:")
for pts, name, filled, shape in sorted(res, reverse=True):
    flag = "" if filled == 11 else "   <- ILLEGAL LINEUP"
    print(f"  {pts:>8.1f}  {name}{flag}")
