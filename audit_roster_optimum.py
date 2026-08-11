"""Audit build_best_roster.py's answer. Both checks came back badly.

Written to test the claim "this is the best roster we can construct". It is not,
on two separate counts, and the second one matters far more than the first.

1. THE SEARCH DOES NOT CONVERGE. 32 of 156 single $5 reallocations improve the
   recommended allocation, the best by +12.7 points. Hill climbing wanders here
   because an isotonic fit is piecewise constant: the landscape is long flat
   plateaus separated by small cliffs, so there is no gradient to follow across
   most of it.

2. SHAPE BARELY MATTERS ANYWAY. Score five deliberately opposite allocations on
   the same $200 -- stars-and-scrubs, two bats, one bat, flat, and the search's
   own answer -- and they span 1.2%. Stars-and-scrubs nominally wins, by less
   than the noise. This independently reproduces rule 3, which measured r = +0.02
   between concentration and drafted-roster quality across 106 real team-seasons.

So there is no "best roster" to walk in with. The allocation is close to
irrelevant; what matters is not overpaying into the dead zones and taking what
the room actually misprices on the night.

One thing the marginal table does support: the steepest QB step is $5-10 at 6.4
points per dollar, and every QB dollar above $20 buys nothing the fit can see.
That is rule 5, arrived at independently.

Caveat on reading the marginal table: isotonic fits are step functions, so a 0.0
means "no data distinguishes these prices", not "provably worthless".

Run:  python audit_roster_optimum.py
"""
import contextlib
import io
import os

REPO = os.path.join("c:", os.sep, "Users", "Jamie", "repos", "fantasyfootball")
TARGET = os.path.join(REPO, "build_best_roster.py")

# reuse the optimiser's fitted curves and evaluator without re-running the search
src = io.open(TARGET, encoding="utf-8").read()
head = src[:src.index("best = None")]
g = {"__name__": "_hdr", "__file__": TARGET}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(head, "hdr", "exec"), g)
CURVE, evaluate, make = g["CURVE"], g["evaluate"], g["make"]
START, POS, np = g["START"], g["POS"], g["np"]

COUNTS = {"QB": 2, "RB": 4, "WR": 7, "TE": 1, "K": 1, "DEF": 1}
PRICES = {"QB": [10, 1], "RB": [25, 16, 12, 7], "WR": [19, 19, 18, 18, 13, 7, 5],
          "TE": [25], "K": [1], "DEF": [2]}

print("=" * 76)
print("1. WHAT THE NEXT $5 BUYS, at each price -- the reason for the shape")
print("=" * 76)
cols = (1, 5, 10, 15, 20, 30, 40, 55)
print("   " + " " * 5 + "".join("%9s" % ("$" + str(p)) for p in cols))
for pos in ["QB", "RB", "WR", "TE"]:
    def f(p, _pos=pos):
        return float(np.atleast_1d(CURVE[_pos]([p]))[0])
    print("   %-5s" % pos + "".join("%9.1f" % ((f(p + 5) - f(p)) / 5) for p in cols))
print("\n   points per extra dollar. Flat stretches are where money does nothing.")

print("\n" + "=" * 76)
print("2. IS IT AT AN OPTIMUM? move $5 between every pair of slots")
print("=" * 76)
base = evaluate(make(COUNTS, PRICES))[0]
print("   baseline %.1f pts\n" % base)
moves, slots = [], [(p, i) for p in POS for i in range(len(PRICES[p]))]
for (pa, ia) in slots:
    for (pb, ib) in slots:
        if (pa, ia) == (pb, ib) or PRICES[pa][ia] - 5 < 1:
            continue
        cand = {k: list(v) for k, v in PRICES.items()}
        cand[pa][ia] -= 5
        cand[pb][ib] += 5
        moves.append((evaluate(make(COUNTS, cand))[0] - base,
                      "$%d %s -> $%d %s" % (PRICES[pa][ia], pa, PRICES[pb][ib], pb)))
moves.sort(reverse=True)
print("   %d reallocations tested; %d improve by more than 0.5 pts"
      % (len(moves), len([m for m in moves if m[0] > 0.5])))
print("\n   best moves still available:")
for d, lab in moves[:4]:
    print("     %+7.1f   %s" % (d, lab))
print("\n   worst, i.e. what the allocation is avoiding:")
for d, lab in moves[-3:]:
    print("     %+7.1f   %s" % (d, lab))

print("\n" + "=" * 76)
print("3. HOW MUCH DOES SHAPE ACTUALLY MATTER?")
print("=" * 76)
print("   Rule 3 says concentration explains nothing on 106 real team-seasons.")
print("   Score deliberately different shapes on the same $200 and see.\n")
ALT = {
    "the recommended one": (COUNTS, PRICES),
    "one big bat":        ({"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1, "DEF": 1},
                           {"QB": [8, 1], "RB": [60, 6, 3, 2],
                            "WR": [40, 25, 20, 12, 6, 3], "TE": [10, 1],
                            "K": [1], "DEF": [2]}),
    "two bats":           ({"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1, "DEF": 1},
                           {"QB": [6, 1], "RB": [55, 8, 3, 2],
                            "WR": [52, 18, 12, 8, 5, 3], "TE": [22, 1],
                            "K": [1], "DEF": [2]}),
    "totally flat":       ({"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1, "DEF": 1},
                           {"QB": [14, 12], "RB": [14, 13, 13, 12],
                            "WR": [14, 13, 13, 13, 12, 12], "TE": [13, 12],
                            "K": [1], "DEF": [2]}),
    "stars and scrubs":   ({"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1, "DEF": 1},
                           {"QB": [2, 1], "RB": [62, 2, 1, 1],
                            "WR": [58, 55, 2, 2, 1, 1], "TE": [8, 1],
                            "K": [1], "DEF": [2]}),
}
res = []
for name, (c, pr) in ALT.items():
    m, lo, hi = evaluate(make(c, pr))
    res.append((m, lo, sum(sum(v) for v in pr.values()), name))
res.sort(reverse=True)
top = res[0][0]
print("   %-22s %6s %9s %8s %9s" % ("shape", "spend", "exp pts", "bad yr", "vs best"))
for m, lo, tot, name in res:
    print("   %-22s %6s %9.0f %8.0f %8.1f%%"
          % (name, "$" + str(tot), m, lo, 100 * (m - top) / top))
print("\n   spread best to worst: %.1f%%" % (100 * (res[0][0] - res[-1][0]) / res[-1][0]))
