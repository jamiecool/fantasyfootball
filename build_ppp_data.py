"""Perennial Push (ESPN league 623238770) -> cleandata/analysis/ppp_data.json.

The second league on the dashboard, and almost nothing carries over from PBAFFL:
this one is a SNAKE draft, SUPERFLEX, full PPR, 18 rounds, 12 teams. Different
format, different scoring, different roster -- so it gets its own board, its own
history and its own strategy rules rather than reusing any of the auction work.

Reads five seasons of pick-by-pick drafts plus the 2026 board out of
rawdata/ppp/, and writes one JSON blob that build_dashboard.py folds into the
page's data as D["ppp"]. No network, no database -- the ESPN pulls are checked
in as PSV because they need an authenticated session to reproduce (see
rawdata/ppp/README.md).

Run:
    python build_ppp_data.py

THE BOARD IS BUILT BY ppp_board.py, on the same settled method as every other
board in this repo: Underdog ADP orders within a position, this league's own
2023-25 draft history weights across positions, and no projection touches the
sort. Read that module's docstring before changing anything about the ranking.

WHAT THIS FILE STILL DOES is the outcome analysis -- what a round actually
returned, which positions stop paying when, the quarterback gap -- plus two
measurements that are genuinely useful next to a board without being allowed to
rank it:

1. ESPN PROJECTS EVERY STARTER TO PLAY 17 GAMES, so its projections run high --
   actual points land at 0.83-0.89 of projection depending on position. `exp`
   deflates each projection by its own position's measured ratio. An
   informational column, not a ranking.

2. REPLACEMENT LEVEL IS MEASURED, NOT PROJECTED. ESPN's 24th-best QB for 2026
   projects 239.1 points; across five actual seasons the 24th-best QB scored
   153.7. That gap is the single best illustration of why this league's own
   history beats a projection feed for anything positional -- but it is now a
   finding on the Strategy tab rather than machinery inside the board.

A PREVIOUS VERSION RANKED THIS BOARD ON (1) AND (2) DIRECTLY, deriving value over
replacement from a starter requirement of QB = 2.0 per team. It reached broadly
the right conclusion about quarterbacks for defensible reasons, but it did it by
modelling the format from an assumption, and off a projection feed the repo had
already rejected for exactly that purpose. The draft history states the same fact
without the assumption. See CLAUDE.md trap 13.
"""
import json
import os
import statistics as st
from collections import defaultdict

from ppp_board import build_board

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "rawdata", "ppp")
OUT = os.path.join(ROOT, "cleandata", "analysis")

SEASONS = [2021, 2022, 2023, 2024, 2025]
TEAMS = {2021: 14, 2022: 12, 2023: 12, 2024: 12, 2025: 12}
ROUNDS = 18

# The board's cross-position curve uses the last THREE seasons, matching the
# window the PBAFFL price curve uses. The outcome analysis below uses all five:
# more history is better for measuring what a round returns, but a stale draft
# is actively misleading about where the room takes a position today. 2021 also
# had 14 teams, which would distort a pick-based curve for a 12-team league.
CURVE_SEASONS = [2023, 2024, 2025]

# Starters per team. Superflex is filled by a QB here in practice -- 33 QBs went
# in 2025 for 12 teams -- so QB carries two starting slots. The single FLEX is
# split across RB/WR/TE by how the league has actually used it, which is why
# these are fractional rather than whole slots.
NEED = {"QB": 2.0, "RB": 2.5, "WR": 3.3, "TE": 1.0, "K": 1.0, "DEF": 1.0}

BANDS = [(1, 3), (4, 6), (7, 9), (10, 12), (13, 15), (16, 18)]
SKILL = {"QB", "RB", "WR", "TE"}


def src(name):
    return os.path.join(SRC, name)


def rows(path):
    """PSV lines, minus a header row if there is one."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line:
                yield line.split("|")


# ---- 1. five seasons of picks ----------------------------------------------
# schema: overall|round|pick|teamId|playerId|keeper|name|pos|actual|proj|gp
picks = []
for y in SEASONS:
    for p in rows(src(f"draft{y}.psv")):
        picks.append(dict(
            s=y, o=int(p[0]), rd=int(p[1]), sl=int(p[2]), tm=int(p[3]), pid=p[4],
            n=p[6], pos=p[7],
            act=float(p[8]) if p[8] else None,
            prj=float(p[9]) if p[9] else None))
print(f"{len(picks)} picks across {len(SEASONS)} seasons")


def need(y, pos):
    """How many of this position started league-wide in season y."""
    return int(round(NEED[pos] * TEAMS[y]))


# Positional finish rank among players actually drafted that season, which is
# the only pool that matters -- a player nobody drafted was not an option.
for y in SEASONS:
    by_pos = defaultdict(list)
    for p in picks:
        if p["s"] == y and p["act"] is not None:
            by_pos[p["pos"]].append(p)
    for pos, lst in by_pos.items():
        lst.sort(key=lambda x: -x["act"])
        for i, p in enumerate(lst, 1):
            p["pr"] = i
for p in picks:
    p.setdefault("pr", None)
    p["st"] = 1 if (p["pr"] and p["pr"] <= need(p["s"], p["pos"])) else 0
    p["fin"] = f"{p['pos']}{p['pr']}" if p["pr"] else ""

# ---- 2. realised replacement level, and the projection deflator ------------
# See the two ideas in the module docstring -- this is where both are measured.
REPL_ACT, RATIO = {}, {}
for pos in NEED:
    floors = []
    for y in SEASONS:
        scored = sorted((p["act"] for p in picks
                         if p["s"] == y and p["pos"] == pos and p["act"] is not None),
                        reverse=True)
        i = need(y, pos) - 1
        if len(scored) > i:
            floors.append(scored[i])
    REPL_ACT[pos] = round(st.mean(floors), 1)
    # proj > 5 drops the players ESPN never expected to play, whose ratio is
    # noise divided by nothing
    g = [p for p in picks
         if p["pos"] == pos and p["prj"] and p["prj"] > 5 and p["act"] is not None]
    RATIO[pos] = round(st.mean(p["act"] for p in g) / st.mean(p["prj"] for p in g), 3)

# ---- 3. per-round aggregates -----------------------------------------------
rdstat = []
for rd in range(1, ROUNDS + 1):
    g = [p for p in picks if p["rd"] == rd and p["act"] is not None]
    rdstat.append(dict(rd=rd, n=len(g),
                       mean=round(st.mean(p["act"] for p in g), 1),
                       med=round(st.median(p["act"] for p in g), 1),
                       st=round(sum(p["st"] for p in g) / len(g) * 100)))
rdmean = {r["rd"]: r["mean"] for r in rdstat}
# A pick's value is against what its OWN round returned -- a 12th-rounder
# beating the 12th round is a good pick even though he scored less than a 2nd.
for p in picks:
    p["vor"] = round(p["act"] - rdmean[p["rd"]], 1) if p["act"] is not None else None

posband = []
for pos in ["QB", "RB", "WR", "TE", "K", "DEF"]:
    row = dict(pos=pos, cells=[])
    for lo, hi in BANDS:
        g = [p for p in picks
             if lo <= p["rd"] <= hi and p["pos"] == pos and p["act"] is not None]
        row["cells"].append(dict(
            band=f"{lo}-{hi}", n=len(g),
            st=round(sum(x["st"] for x in g) / len(g) * 100) if g else None,
            mean=round(st.mean(x["act"] for x in g), 1) if g else None))
    posband.append(row)

# The superflex question, measured: what did a QB return against the RB/WR/TE
# taken in the same rounds?
qbedge = []
for lo, hi in BANDS:
    q = [p["act"] for p in picks
         if lo <= p["rd"] <= hi and p["pos"] == "QB" and p["act"] is not None]
    f = [p["act"] for p in picks
         if lo <= p["rd"] <= hi and p["pos"] in ("RB", "WR", "TE") and p["act"] is not None]
    qbedge.append(dict(band=f"{lo}-{hi}", qb=round(st.mean(q), 1), qbn=len(q),
                       flex=round(st.mean(f), 1), flexn=len(f),
                       edge=round(st.mean(q) - st.mean(f), 1)))

poscount = [dict(rd=rd, **{x: sum(1 for p in picks if p["rd"] == rd and p["pos"] == x)
                           for x in ["QB", "RB", "WR", "TE", "K", "DEF"]})
            for rd in range(1, ROUNDS + 1)]
qbcum, tot = [], 0
for rd in range(1, ROUNDS + 1):
    tot += sum(1 for p in picks if p["rd"] == rd and p["pos"] == "QB")
    qbcum.append(round(tot / len(SEASONS), 1))

# ---- 4. the 2026 board -----------------------------------------------------
# THE SETTLED METHOD, and see ppp_board.py for why each half is what it is:
# Underdog orders within a position, this league's own 2023-25 draft history
# weights across positions, ESPN's ADP covers the K and DEF that Underdog has
# none of. No projection touches the sort.
board, DIAG = build_board(
    board_rows=list(rows(src("board2026.psv"))),
    picks=picks, seasons=CURVE_SEASONS, rounds=ROUNDS,
    teams_per=TEAMS[max(SEASONS)],
    db_path=os.path.join(ROOT, "cleandata", "fantasy.db"))

# Projections are carried as an informational column only -- never the ranking.
# `exp` deflates ESPN's number onto the scale this league's outcomes actually
# land on, which is a genuine measurement and useful to eyeball next to a pick;
# it is emphatically not what sorted the rows above.
for p in board:
    p["exp"] = round(p["prj"] * RATIO.get(p["pos"], 0.86), 1)
    p["vor"] = (round(p["exp"] - REPL_ACT[p["pos"]], 1)
                if p["pos"] in SKILL else None)

skill = [p for p in board if p["pos"] in SKILL]
stream = [p for p in board if p["pos"] not in SKILL]

# ---- 5. teams and their drafts ---------------------------------------------
teams = {}
for f in rows(src("teams.psv")):
    if f[0] == "season":
        continue
    teams.setdefault(f[0], []).append(dict(
        id=int(f[1]), name=f[2], ab=f[3], own=f[4], w=int(f[5]), l=int(f[6]),
        pf=float(f[7]), seed=int(f[8]), fin=int(f[9])))
for y in SEASONS:
    haul, starters = defaultdict(float), defaultdict(int)
    for p in picks:
        if p["s"] == y and p["act"]:
            haul[p["tm"]] += p["act"]
            starters[p["tm"]] += p["st"]
    for t in teams[str(y)]:
        t["haul"] = round(haul[t["id"]], 1)
        t["startables"] = starters[t["id"]]

qb_top3 = len([p for p in skill if p["pos"] == "QB" and p["rank"] <= 36])

D = dict(
    league=json.load(open(src("league.json"), encoding="utf-8")),
    seasons=SEASONS, curveSeasons=CURVE_SEASONS, rounds=ROUNDS,
    replacement=REPL_ACT, ratio=RATIO, need=NEED, curves=DIAG["curves"],
    nUnderdog=DIAG["n_underdog"], nEspn=DIAG["n_espn"],
    qbTop3=qb_top3, qbcum=qbcum, board=board, rdstat=rdstat, posband=posband,
    qbedge=qbedge, poscount=poscount, bands=[f"{a}-{b}" for a, b in BANDS],
    draft={str(y): [dict(o=p["o"], rd=p["rd"], pk=p["sl"], tm=p["tm"], n=p["n"],
                         pos=p["pos"], act=p["act"], prj=p["prj"], fin=p["fin"],
                         st=p["st"], vor=p["vor"])
                    for p in picks if p["s"] == y] for y in SEASONS},
    teams=teams)

# ---- 6. the strategy rules -------------------------------------------------
# Numbers are interpolated from what was just measured rather than typed in, so
# a re-run after new data cannot leave the prose asserting a stale figure. This
# is the same contract strategy_rules.py holds for PBAFFL.
rb = next(c for c in posband if c["pos"] == "RB")["cells"]
qb_cells = next(x for x in posband if x["pos"] == "QB")["cells"]
CURVE = DIAG["curves"]
D["rules"] = [
    dict(id="1", conf="high", area="Superflex",
         rule="The second quarterback is the best value on the board, and this room "
              "still underpays for it.",
         why=f"QBs taken in rounds 7-9 returned {qbedge[2]['qb']} points against "
             f"{qbedge[2]['flex']} for the RB/WR/TE taken alongside them "
             f"({qbedge[2]['edge']:+}); in rounds 10-12 the gap is {qbedge[3]['edge']:+}. "
             "Six of the ten biggest value picks in five seasons were QBs taken in "
             "rounds 6-12 - Mayfield rd 9 (365.8), Stafford rd 6 (350.4), Lawrence rd 8 "
             "(338.2), Nix rd 10 (317.2), Love rd 10 (319.1), Goff rd 12 (284.3).",
         n=f"{sum(c['n'] for c in qb_cells)} QB picks vs 587 RB/WR/TE picks, 5 seasons"),
    dict(id="2", conf="high", area="Superflex",
         rule="A quarterback who misses time is replaced by nothing. That is what makes "
              "them scarce here.",
         why="ESPN projects every starting quarterback to play a full season, so its "
             "24th-best QB for 2026 projects 239.1 points. Across five actual seasons "
             f"the 24th-best QB scored {REPL_ACT['QB']}. Twenty-four QBs start every week "
             "in a superflex league and there is no 25th worth having, so the real floor "
             f"is {REPL_ACT['QB']} - and anyone valuing quarterbacks off the projected "
             f"floor instead is quietly erasing about {round(239.1 - REPL_ACT['QB'])} "
             "points from every one of them. This board does not price off either floor; "
             "it takes the league's own draft history instead, which reaches the same "
             "conclusion without needing a projection to be right.",
         n="5 seasons of realized outcomes vs ESPN preseason projections"),
    dict(id="3", conf="high", area="Superflex",
         rule="ESPN's own board is built for a one-QB league. Do not draft from it here.",
         why="This league's own drafts say where a position goes: over 2023-25 the first "
             f"quarterback off the board went at overall pick {CURVE['QB'][1]:.0f} and the "
             f"fifth at {CURVE['QB'][5]:.0f}, where the fifth running back went at "
             f"{CURVE['RB'][5]:.0f} and the first tight end at {CURVE['TE'][1]:.0f}. "
             f"Ranked inside the same {len(board)}-player pool, ESPN has quarterbacks far "
             f"later than that. This board puts {qb_top3} inside the first three rounds; "
             f"the room itself has taken {qbcum[2]} by that point, so the market already "
             "knows. ESPN does not.",
         n=f"{sum(len(v) for v in CURVE.values())} position-rank observations, "
           f"{len(CURVE_SEASONS)} seasons"),
    dict(id="4", conf="high", area="Roster shape",
         rule="Never spend a pick on a kicker or defense before round 13.",
         why="K and D/ST were startable 85-100% of the time in every round band from 10 "
             "on. The 15 taken before round 13 averaged 133.1 points at position rank "
             "6.6; the 125 taken from round 13 on averaged 118.5 at rank 7.7. One "
             "position rank of quality costs a skill player worth roughly 149 points.",
         n="140 K/DEF picks, 5 seasons"),
    dict(id="5", conf="high", area="Running back",
         rule="Running back falls off a cliff after round 9. Take the backs you want "
              "before it.",
         why=f"RB startable rate runs {rb[0]['st']}% in rounds 1-3 and {rb[2]['st']}% in "
             f"7-9, then collapses to {rb[3]['st']}% in 10-12 and {rb[4]['st']}% in 13-15. "
             "Wide receiver follows the same curve one band later. Tight end holds up "
             "best late.",
         n=f"{sum(c['n'] for c in rb)} RB picks, 5 seasons"),
    dict(id="6", conf="high", area="Mindset",
         rule="Treat every projection as roughly 15% too high, and never rank off one.",
         why="Across 933 picks with usable ESPN preseason projections, actual points came "
             "in at 0.82-0.90 of projection in every round band through 15. By position "
             f"the ratio is {RATIO['QB']} for QBs, {RATIO['RB']} for RBs, {RATIO['WR']} "
             f"for WRs and {RATIO['TE']} for TEs, and the Exp column on the board applies "
             "each. But the deeper point is that a projection is one algorithm, not a "
             "market: two independent markets agree with each other at rho 0.95 while "
             "either agrees with a projection model at 0.65-0.72. Projections are a column "
             "here, never the sort.",
         n="933 picks with projections, 4 seasons"),
    dict(id="7", conf="medium", area="Draft slot",
         rule="Your draft slot is not worth worrying about.",
         why="Teams picking 1-4 averaged 6.75 wins and a 7.5 finish; slots 5-8 averaged "
             "7.55 wins and 5.7; slots 9-14 averaged 6.73 wins and 6.9. The spread is "
             "inside the noise for 62 team-seasons.",
         n="62 team-seasons, 5 seasons"),
    dict(id="8", conf="high", area="Mindset",
         rule="The draft matters here. It is not all waivers.",
         why="Total points from a team’s drafted players correlate +0.50 with wins and "
             "+0.64 with points scored. Rounds 1-3 supply only 26.3% of all drafted "
             "points, though - rounds 10-18 supply 36.6%. The draft is won in the middle "
             "and late rounds.",
         n="62 team-seasons, 1,116 picks"),
]

os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "ppp_data.json")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(D, f, separators=(",", ":"))

print(f"\nrealized replacement: {REPL_ACT}")
print(f"proj deflator by pos: {RATIO}       (informational columns only)")

print(f"\nboard ordering within position: {DIAG['n_underdog']} from Underdog, "
      f"{DIAG['n_espn']} from ESPN ADP (K/DEF plus anyone Underdog does not rank)")
if DIAG["espn_ordered_skill"]:
    print("  skill players Underdog does not rank, ordered on ESPN ADP instead: "
          + ", ".join(DIAG["espn_ordered_skill"]))
print(f"\ncross-position curve, {CURVE_SEASONS[0]}-{CURVE_SEASONS[-1]} "
      f"(overall pick the Nth at each position actually went):")
print("       " + "".join(f"{p:>8}" for p in ["QB", "RB", "WR", "TE", "K", "DEF"]))
for r in (1, 2, 3, 5, 8, 12):
    print(f"  {('#' + str(r)):>4} " + "".join(
        f"{(round(CURVE[p][r]) if r in CURVE.get(p, {}) else '-'):>8}"
        for p in ["QB", "RB", "WR", "TE", "K", "DEF"]))

print(f"\n{len(skill)} skill players, {len(stream)} K/DEF, {len(board)} on the board")
print(f"QBs inside rounds 1-3 on this board: {qb_top3}   "
      f"(the room historically takes {qbcum[2]} by then)")
print("\nround 1 as this board has it:")
for p in board[:12]:
    print(f"  {p['rd']}.{p['pk']:02}  {p['n']:<24}{p['pos']}{p['prank']:<3} "
          f"pick {p['pick']:>6}   ESPN {p['espnRank']:>3} ({p['gap']:+})")
print(f"\nwrote {path}  ({os.path.getsize(path) / 1e3:.0f}KB)")
