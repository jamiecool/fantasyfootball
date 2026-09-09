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
import csv
import json
import os
import statistics as st
from collections import defaultdict

from ppp_board import build_board, extend, player_key

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "rawdata", "ppp")
OUT = os.path.join(ROOT, "cleandata", "analysis")

SEASONS = [2021, 2022, 2023, 2024, 2025]      # played seasons: everything measured comes from these
# The season just drafted (fetch_ppp_draft.py). Its picks are shown on Past drafts and
# judged against ESPN's list, but it has no points yet, so it stays out of every curve,
# replacement level, ratio and round mean -- the same split PBAFFL's draft_current makes.
CURRENT = 2026
ALL_SEASONS = SEASONS + ([CURRENT] if os.path.exists(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "rawdata", "ppp", f"draft{CURRENT}.psv")) else [])
TEAMS = {2021: 14, 2022: 12, 2023: 12, 2024: 12, 2025: 12, 2026: 12}
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
for y in ALL_SEASONS:
    for p in rows(src(f"draft{y}.psv")):
        picks.append(dict(
            s=y, o=int(p[0]), rd=int(p[1]), sl=int(p[2]), tm=int(p[3]), pid=p[4],
            n=p[6], pos=p[7],
            act=float(p[8]) if p[8] else None,
            prj=float(p[9]) if p[9] else None))
print(f"{len(picks)} picks across {len(ALL_SEASONS)} seasons"
      + (f" (the {CURRENT} draft is shown but not measured)" if CURRENT in ALL_SEASONS else ""))


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

# ---- 4b. the value pivot: value over draft demand --------------------------
# A SECOND VIEW OF THE SAME BOARD, not a replacement for the pick curve. The pick
# curve says where this room takes a slot; build_ppp_vor_board.py says what that
# slot has been worth in points over the slot the room drafts to inside the first
# 100 picks (QB23 / RB28 / WR40 / TE8). Both order within a position on Underdog,
# so the two pivots disagree only on cross-position weighting -- which is the
# whole question, and why it is a toggle rather than a new column.
#
# Read from the CSV rather than imported: build_ppp_vor_board.py is a script and
# importing it re-runs it as a side effect (the same reason ppp_board.py copies
# player_key instead of importing build_clean_data). build_all.py runs it one
# stage earlier; if the file is missing the pivot is simply absent from the page.
VB_PATH = os.path.join(ROOT, "cleandata", "analysis", "ppp_vor_board.csv")
VB_FIELDS = ("vbPr", "vbProj", "vbVal", "vbRank", "vbRd", "vbPk", "vbGap")
for p in board:
    for k in VB_FIELDS:
        p[k] = None
vb_meta = None
if os.path.exists(VB_PATH):
    with open(VB_PATH, encoding="utf-8") as f:
        vb_rows = [r for r in csv.DictReader(f) if r["pos"] in SKILL and r["value"] != ""]
    vb = {}
    for r in vb_rows:
        k = player_key(r["player"])
        if k in vb:                                # trap 1
            raise SystemExit(f"name collision in ppp_vor_board.csv, refusing to join: {r['player']}")
        vb[k] = r
    by_key = {p["key"]: p for p in board}
    vb_unmatched = []
    for k, r in vb.items():
        p = by_key.get(k)
        if p is None:                              # Underdog ranks him, ESPN's pool does not have him
            vb_unmatched.append(r["player"])       # -- so he cannot be drafted here anyway
            continue
        p["vbPr"] = int(r["pos_rank"])
        p["vbProj"] = float(r["proj"])
        p["vbVal"] = float(r["value"])
    # Ranked densely inside the ESPN pool, exactly as `rank` and `espnRank` are, so
    # the value pivot's Move column is the same like-for-like comparison: valued
    # skill players by value, then the skill players Underdog ranks past this
    # league's draft history (no slot to project), then K/DEF as fill in pick order.
    _tp = TEAMS[max(SEASONS)]
    for i, p in enumerate(sorted(board, key=lambda p: (p["vbVal"] is None, p["pos"] not in SKILL,
                                                       -(p["vbVal"] or 0), p["rank"])), 1):
        p["vbRank"] = i
        p["vbRd"] = (i - 1) // _tp + 1
        p["vbPk"] = (i - 1) % _tp + 1
        p["vbGap"] = p["espnRank"] - i
    vb_meta = dict(
        baseline={r["pos"]: dict(rank=int(r["baseline_rank"]), pts=float(r["baseline_pts"]))
                  for r in vb_rows},
        matched=len(vb) - len(vb_unmatched), unmatched=vb_unmatched,
        # the VOR script's window is its own SEASONS constant; it matches CURVE_SEASONS
        # today, and the page labels the pivot with this value
        seasons=CURVE_SEASONS)

# ---- 4c. the Yahoo pivot: same pick curve, Yahoo's analysts ordering within position
# The settled method's half 1 is "Underdog orders within a position" -- Jamie's call,
# and unverifiable here (no historical Underdog ADP). This pivot swaps ONLY that half
# for Yahoo's six-analyst consensus (fetch_yahoo_rankings.py) and keeps half 2, the
# league's own pick curve, exactly as it is. So pick and Yahoo pivots differ only where
# the two markets disagree about who is the better player at a position -- which is the
# question the toggle exists to show. Yahoo also ranks K and D/ST, which Underdog does
# not, so those follow Yahoo here where ESPN's ADP orders them on the other pivots.
# Yahoo's list is a 1-QB ranking: its overall order is never used for anything.
YH_PATH = os.path.join(ROOT, "rawdata", "yahoo", "yahoo_consensus_ppr_2026.csv")
YH_META = os.path.join(ROOT, "rawdata", "yahoo", "yahoo_consensus_ppr_2026.meta.json")
YH_FIELDS = ("yhEcr", "yhPr", "yhSrc", "yhPick", "yhRank", "yhRd", "yhPk", "yhGap")
for p in board:
    for k in YH_FIELDS:
        p[k] = None
yh_meta = None
if os.path.exists(YH_PATH):
    # ESPN and FantasyPros spell three team codes differently; D/ST keys are def_<espn code>
    TEAM_ALIAS = {"JAC": "JAX", "WAS": "WSH", "LA": "LAR"}
    yh = {}
    with open(YH_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["position"] == "DST":
                k = "def_" + TEAM_ALIAS.get(r["team"], r["team"]).lower()
            else:
                k = player_key(r["player_name"])
            if k in yh:                            # trap 1
                raise SystemExit(f"name collision in {os.path.basename(YH_PATH)}, refusing to join: "
                                 f"{r['player_name']} / {yh[k]['player_name']}")
            yh[k] = r
    by_key = {p["key"]: p for p in board}
    for k, r in yh.items():
        if k in by_key:
            by_key[k]["yhEcr"] = int(r["rank"])
    yh_unmatched = [r["player_name"] for k, r in yh.items()
                    if k not in by_key and int(r["rank"]) <= 200]
    # Dense rank inside the ESPN pool, Yahoo-ranked first in ECR order, then anyone
    # Yahoo does not carry in ESPN ADP order behind them -- the same rule build_board()
    # applies to Underdog, so the two pivots are built identically apart from the source.
    yh_by_pos = defaultdict(list)
    for p in board:
        yh_by_pos[p["pos"]].append(p)
    for pos, lst in yh_by_pos.items():
        ranked = sorted((p for p in lst if p["yhEcr"] is not None), key=lambda x: x["yhEcr"])
        rest = sorted((p for p in lst if p["yhEcr"] is None),
                      key=lambda x: (x["adp"] if x["adp"] is not None else 9e9, x["espn"]))
        for i, p in enumerate(ranked + rest, 1):
            p["yhPr"] = i
            p["yhSrc"] = "yahoo" if p["yhEcr"] is not None else "espn"
        c = DIAG["curves"].get(pos)                # CURVE is only assembled further down
        for p in lst:
            p["yhPick"] = extend(c, p["yhPr"]) if c else None
    _tp = TEAMS[max(SEASONS)]
    for i, p in enumerate(sorted(board, key=lambda p: (p["yhPick"] is None, p["yhPick"], p["espn"])), 1):
        p["yhRank"] = i
        p["yhRd"] = (i - 1) // _tp + 1
        p["yhPk"] = (i - 1) % _tp + 1
        p["yhGap"] = p["espnRank"] - i
    meta = json.load(open(YH_META, encoding="utf-8")) if os.path.exists(YH_META) else {}
    yh_meta = dict(
        experts=meta.get("experts"), updated=meta.get("last_updated"),
        fetched=meta.get("fetched_on"), listed=len(yh),
        matched=sum(1 for p in board if p["yhEcr"] is not None),
        unranked_skill=[p["n"] for p in board if p["yhEcr"] is None and p["pos"] in SKILL
                        and p["rank"] <= 150],
        unmatched=yh_unmatched)

# ---- 4d. preseason superflex lists, per season -------------------------------
# What the room was looking at when it drafted: ESPN's published superflex list
# (recovered from the Wayback Machine, 2021/2023/2025 so far -- the 2022 and 2024
# pages are blocked/offline) and FantasyPros' superflex (OP) consensus for every
# season. Past drafts shows each pick against them: pick minus list rank, so a
# positive number is a player who FELL past where the list had him.
ESP, ESP_SRC, FPC = {}, {}, {}
for _y in SEASONS:
    _f = os.path.join(ROOT, "rawdata", "espn", f"superflex_ranks_{_y}_espn.csv")
    if os.path.exists(_f):
        with open(_f, encoding="utf-8") as _fh:
            _rows = list(csv.DictReader(_fh))
        ESP[_y] = {player_key(r["player"]): int(r["rank"]) for r in _rows}
        ESP_SRC[_y] = _rows[0]["source"] if _rows else None
    _g = os.path.join(ROOT, "rawdata", "fantasypros", f"superflex_ecr_{_y}__preseason.json")
    if os.path.exists(_g):
        _j = json.load(open(_g, encoding="utf-8"))
        FPC[_y] = {player_key(p.get("player_name") or p.get("player_short_name")): p["rank_ecr"]
                   for p in _j["players"]
                   if p.get("rank_ecr") and (p.get("player_name") or p.get("player_short_name"))}
if CURRENT in ALL_SEASONS:
    _bp = os.path.join(ROOT, "rawdata", "ppp", f"board{CURRENT}.psv")
    with open(_bp, encoding="utf-8") as _fh:
        ESP[CURRENT] = {player_key(r[1]): int(r[4]) for r in csv.reader(_fh, delimiter="|")
                        if len(r) >= 5 and r[0].isdigit()}
    ESP_SRC[CURRENT] = f"espn superflex list, the draft-room order (board{CURRENT}.psv)"
print(f"\npreseason superflex lists: ESPN for {sorted(ESP)}, FantasyPros consensus for {sorted(FPC)}")

# autopicks, where ESPN recorded them (fetch_ppp_draft.py writes draft<y>_meta.json)
AUTO = {}
for _y in ALL_SEASONS:
    _m = os.path.join(ROOT, "rawdata", "ppp", f"draft{_y}_meta.json")
    if os.path.exists(_m):
        AUTO[_y] = json.load(open(_m, encoding="utf-8")).get("autopicks", {})

# ---- 4e. FAAB: waiver bids and free-agent adds, by season -------------------------
# fetch_ppp_faab.py writes faab<y>.psv. Each row is one transaction; the page groups a
# week's claims by the player added, so the winner and the bids that lost to him sit
# together, and reconstructs each team's remaining budget by subtracting winning bids.
FAAB_BUDGET = 200                                  # acquisitionSettings.acquisitionBudget
FAAB = {}
for _y in ALL_SEASONS:
    _f = os.path.join(ROOT, "rawdata", "ppp", f"faab{_y}.psv")
    if not os.path.exists(_f):
        continue
    _rows = []
    with open(_f, encoding="utf-8") as _fh:
        for r in csv.DictReader(_fh, delimiter="|"):
            _st = r["status"]
            kind = ("free" if r["type"] == "FREEAGENT" else
                    "won" if _st == "EXECUTED" else
                    "outbid" if _st == "FAILED_INVALIDPLAYERSOURCE" else
                    "cancelled" if _st == "CANCELED" else
                    "failed:" + _st.replace("FAILED_", "").lower())
            _rows.append(dict(sp=int(r["sp"]), k=kind, tm=int(r["teamId"]), bid=int(float(r["bid"] or 0)),
                              ts=int(float(r["processDate"] or 0)), tx=r["txId"], rel=r["relatedId"],
                              a=dict(pid=r["addPid"], n=r["addName"], pos=r["addPos"],
                                     key=player_key(r["addName"]) if r["addName"] else ""),
                              d=dict(n=r["dropName"], pos=r["dropPos"]) if r["dropName"] else None))
    FAAB[str(_y)] = dict(budget=FAAB_BUDGET, rows=_rows)
    print(f"FAAB {_y}: {len(_rows)} transactions, "
          f"{sum(1 for x in _rows if x['k'] == 'won')} winning bids, "
          f"{sum(1 for x in _rows if x['k'] == 'outbid')} outbid")

# ---- 5. teams and their drafts ---------------------------------------------
teams = {}
for f in rows(src("teams.psv")):
    if f[0] == "season":
        continue
    teams.setdefault(f[0], []).append(dict(
        id=int(f[1]), name=f[2], ab=f[3], own=f[4], w=int(f[5]), l=int(f[6]),
        pf=float(f[7]), seed=int(f[8]), fin=int(f[9])))
for y in ALL_SEASONS:
    haul, starters = defaultdict(float), defaultdict(int)
    for p in picks:
        if p["s"] == y and p["act"]:
            haul[p["tm"]] += p["act"]
            starters[p["tm"]] += p["st"]
    for t in teams[str(y)]:
        t["haul"] = round(haul[t["id"]], 1)
        t["startables"] = starters[t["id"]]

qb_top3 = len([p for p in skill if p["pos"] == "QB" and p["rank"] <= 36])
# ESPN's own placement, on the list the draft room shows (espnRank is the SUPERFLEX
# list since 2026-09-08 -- see fetch_espn_league.RANK_TYPE)
espn_qb_top3 = len([p for p in skill if p["pos"] == "QB" and p["espnRank"] <= 36])

D = dict(
    league=json.load(open(src("league.json"), encoding="utf-8")),
    seasons=ALL_SEASONS, current=CURRENT if CURRENT in ALL_SEASONS else None,
    curveSeasons=CURVE_SEASONS, rounds=ROUNDS,
    replacement=REPL_ACT, ratio=RATIO, need=NEED, curves=DIAG["curves"],
    nUnderdog=DIAG["n_underdog"], nEspn=DIAG["n_espn"],
    qbTop3=qb_top3, qbcum=qbcum, board=board, vb=vb_meta, yh=yh_meta, rdstat=rdstat, posband=posband,
    qbedge=qbedge, poscount=poscount, bands=[f"{a}-{b}" for a, b in BANDS],
    # `key` is the folded player_key, carried so a name in the past-drafts and
    # roster views opens the same profile card the board does. Defences get the
    # plain fold and simply never resolve -- nflverse has no D/ST stat lines, so
    # the page falls back to plain text for them, which is the right answer.
    draft={str(y): [dict(o=p["o"], rd=p["rd"], pk=p["sl"], tm=p["tm"], n=p["n"],
                         pos=p["pos"], act=p["act"], prj=p["prj"], fin=p["fin"],
                         st=p["st"], vor=p["vor"], key=player_key(p["n"]),
                         auto=AUTO.get(y, {}).get(str(p["o"])),
                         # preseason superflex list ranks, for the "vs ESPN" column
                         esp=ESP.get(y, {}).get(player_key(p["n"])),
                         fpc=FPC.get(y, {}).get(player_key(p["n"])))
                    for p in picks if p["s"] == y] for y in ALL_SEASONS},
    lists={str(y): dict(espn=ESP_SRC.get(y), fp=y in FPC) for y in ALL_SEASONS},
    faab=FAAB,
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
         rule="The draft room shows ESPN's SUPERFLEX list. Read it as the room's anchor, "
              "not as a valuation.",
         why="ESPN keeps four ranking lists and the draft tool shows the one that matches the "
             "league's format; for this league that is SUPERFLEX (Allen 1, Daniels 3, Lamar 5, "
             f"Gibbs 7), not the one-QB PPR list. Inside this {len(board)}-player pool ESPN's "
             f"superflex list has {espn_qb_top3} quarterbacks in the first three rounds; this "
             f"board has {qb_top3}; the room itself has taken {qbcum[2]} by that point. "
             "The list is what the other eleven coaches are looking at, so it is the best "
             "read on when a quarterback will actually go -- but it is ESPN's projection "
             "spread, and this league's own outcomes say QB5-24 do not separate. Use it to "
             "time the pick, not to price it.",
         n=f"{sum(len(v) for v in CURVE.values())} position-rank observations, "
           f"{len(CURVE_SEASONS)} seasons; ESPN SUPERFLEX list from board2026.psv"),
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

if vb_meta:
    print(f"\nvalue pivot: {vb_meta['matched']} valued players joined from ppp_vor_board.csv, "
          f"baselines " + " ".join(f"{p}{v['rank']}" for p, v in vb_meta["baseline"].items()))
    if vb_meta["unmatched"]:
        print("  ranked by Underdog but not in ESPN's pool (undraftable here): "
              + ", ".join(vb_meta["unmatched"]))
    vtop = sorted((p for p in skill if p["vbVal"] is not None), key=lambda p: p["vbRank"])[:36]
    print("  first three rounds by value: "
          + ", ".join(f"{sum(1 for p in vtop if p['pos'] == q)} {q}" for q in ["QB", "RB", "WR", "TE"])
          + f"   (pick curve: {qb_top3} QB)")
else:
    print("\n  (no ppp_vor_board.csv -- run: python build_ppp_vor_board.py; the value pivot is hidden)")

if yh_meta:
    print(f"\nyahoo pivot: {yh_meta['matched']} of {len(board)} board players carry a Yahoo rank "
          f"({yh_meta['experts']} analysts, rankings updated {yh_meta['updated']}, fetched {yh_meta['fetched']})")
    if yh_meta["unranked_skill"]:
        print("  board skill players inside the top 150 that Yahoo does not rank (ordered on ESPN ADP): "
              + ", ".join(yh_meta["unranked_skill"]))
    if yh_meta["unmatched"]:
        print("  Yahoo top-200 names not in ESPN's pool (check spelling if a starter is here): "
              + ", ".join(yh_meta["unmatched"]))
    moved = sorted((p for p in board if p["yhRank"] is not None and p["pos"] in SKILL and p["rank"] <= 60),
                   key=lambda p: -abs(p["yhRank"] - p["rank"]))[:8]
    print("  biggest Underdog-vs-Yahoo moves inside the top 60: "
          + ", ".join(f"{p['n']} {p['pos']}{p['prank']}->{p['pos']}{p['yhPr']} (#{p['rank']}->#{p['yhRank']})"
                      for p in moved))                # ASCII arrows: the Windows console is cp1252
else:
    print("\n  (no yahoo_consensus_ppr_2026.csv -- run: python fetch_yahoo_rankings.py; the Yahoo pivot is hidden)")

print(f"\n{len(skill)} skill players, {len(stream)} K/DEF, {len(board)} on the board")
print(f"QBs inside rounds 1-3 on this board: {qb_top3}   "
      f"(the room historically takes {qbcum[2]} by then)")
print("\nround 1 as this board has it:")
for p in board[:12]:
    print(f"  {p['rd']}.{p['pk']:02}  {p['n']:<24}{p['pos']}{p['prank']:<3} "
          f"pick {p['pick']:>6}   ESPN {p['espnRank']:>3} ({p['gap']:+})")
print(f"\nwrote {path}  ({os.path.getsize(path) / 1e3:.0f}KB)")
