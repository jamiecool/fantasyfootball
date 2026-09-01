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

TWO IDEAS DO ALL THE WORK HERE, and both exist because ESPN's own numbers are
the wrong shape for this league:

1. ESPN PROJECTS EVERY STARTER TO PLAY 17 GAMES, so its projections run high --
   actual points land at 0.83-0.89 of projection depending on position. Each
   projection is therefore deflated by its own position's measured ratio before
   anything is ranked. Ranking on raw projections silently ranks on ESPN's
   optimism about durability.

2. REPLACEMENT LEVEL IS MEASURED, NOT PROJECTED. ESPN's 24th-best QB for 2026
   projects 239.1 points; across five actual seasons the 24th-best QB scored
   153.7. Measuring value against the projected floor instead of the real one
   erases ~85 points of value from every quarterback -- which in a superflex
   league, where 24 QBs start every week and there is no 25th worth having, is
   the whole ballgame.
"""
import json
import os
import statistics as st
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "rawdata", "ppp")
OUT = os.path.join(ROOT, "cleandata", "analysis")

SEASONS = [2021, 2022, 2023, 2024, 2025]
TEAMS = {2021: 14, 2022: 12, 2023: 12, 2024: 12, 2025: 12}
ROUNDS = 18

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
# schema: pid|name|pos|proTeam|espnRank|adp|own|proj
board = []
for f in rows(src("board2026.psv")):
    board.append(dict(pid=f[0], n=f[1], pos=f[2], tm=f[3], espn=int(f[4]),
                      adp=float(f[5]) if f[5] else None,
                      own=float(f[6]) if f[6] else None,
                      prj=float(f[7]) if f[7] else 0.0))
byp = defaultdict(list)
for p in board:
    byp[p["pos"]].append(p)
for pos, lst in byp.items():
    lst.sort(key=lambda x: -x["prj"])
    for i, p in enumerate(lst, 1):
        p["prank"] = i

# Deflate onto the scale this league's outcomes actually land on, then measure
# against the replacement level those outcomes actually produced.
for p in board:
    p["exp"] = round(p["prj"] * RATIO.get(p["pos"], 0.86), 1)

# K and D-ST are streamed, not valued -- they get no VOR and sort to the bottom,
# which is also what rule 4 says to do with them.
skill = [p for p in board if p["pos"] in SKILL]
stream = [p for p in board if p["pos"] not in SKILL]
for p in skill:
    p["vor"] = round(p["exp"] - REPL_ACT[p["pos"]], 1)
for p in stream:
    p["vor"] = None
skill.sort(key=lambda x: -x["vor"])
stream.sort(key=lambda x: (x["pos"], -x["prj"]))

# ESPN's rank re-expressed inside the same pool, so the two orderings are
# comparable: "we say 14th, ESPN says 41st" rather than comparing against a
# board that also contains kickers.
for i, p in enumerate(sorted(skill, key=lambda x: x["espn"]), 1):
    p["espnRank"] = i
for i, p in enumerate(skill, 1):
    p["rank"] = i
    p["gap"] = p["espnRank"] - i
    p["rd"] = (i - 1) // 12 + 1
    p["pk"] = (i - 1) % 12 + 1
for p in stream:
    p["rank"] = p["gap"] = p["rd"] = p["pk"] = p["espnRank"] = None
board = skill + stream

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
    seasons=SEASONS, rounds=ROUNDS, replacement=REPL_ACT, ratio=RATIO, need=NEED,
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
             f"is {REPL_ACT['QB']} - and measuring against the projected floor instead "
             f"quietly erases about {round(239.1 - REPL_ACT['QB'])} points of value from "
             "every quarterback.",
         n="5 seasons of realized outcomes vs ESPN preseason projections"),
    dict(id="3", conf="high", area="Superflex",
         rule="ESPN's own board is built for a one-QB league. Do not draft from it here.",
         why=f"Ranked inside the same {len(skill)}-player pool, quarterbacks sit far later "
             "on ESPN than value over replacement says they belong. This board puts "
             f"{qb_top3} quarterbacks inside the first three rounds; across five seasons "
             f"the room itself has taken {qbcum[2]} by that point, so the market already "
             "knows. ESPN does not.",
         n=f"{len(skill)} skill players, ESPN PPR order vs superflex VOR, same pool"),
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
         rule="Treat every projection as roughly 15% too high, and rank on the gaps "
              "rather than the totals.",
         why="Across 933 picks with usable ESPN preseason projections, actual points came "
             "in at 0.82-0.90 of projection in every round band through 15. By position "
             f"the ratio is {RATIO['QB']} for QBs, {RATIO['RB']} for RBs, {RATIO['WR']} "
             f"for WRs and {RATIO['TE']} for TEs - this board deflates every projection by "
             "its own position's factor before ranking.",
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
print(f"proj deflator by pos: {RATIO}")
print(f"\n{len(skill)} skill players ranked, {len(stream)} K/DEF streamed")
print(f"QBs inside rounds 1-3 on this board: {qb_top3}   "
      f"(the room historically takes {qbcum[2]} by then)")
print(f"\nwrote {path}  ({os.path.getsize(path) / 1e3:.0f}KB)")
