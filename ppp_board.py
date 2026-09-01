"""The 2026 Perennial Push board, built the way every board in this repo is built.

THE SETTLED METHOD (CLAUDE.md, "How the 2026 board is priced"), which is about the
two jobs a board does and refusing to let one source do both:

  1. ORDERING WITHIN A POSITION -> Underdog ADP. Sharp money, continuously
     repriced, moves first. Jamie's call from years of watching it.
  2. WEIGHTING ACROSS POSITIONS -> this league's OWN last-3-years draft history.
     For PBAFFL that is a price curve (RB1 = $66, QB1 = $36). This is a snake
     draft, so the analogue is a PICK curve: where did the Nth-best player at
     each position actually go, 2023-25?
  3. K and DEF -> ESPN's own ADP. Underdog carries neither (trap 8).

NO PROJECTION ENTERS THE ORDERING. Dropped repo-wide 2026-08-11: one algorithm is
not a market. Two independent markets agree with each other at rho 0.95 while
either agrees with a projection model at 0.65-0.72, so the model is the outlier.
ESPN's projection rides along as an informational column, exactly as Sleeper's
does on the PBAFFL board, and never touches the sort.

WHY THIS MATTERS MORE HERE THAN IT DID FOR PBAFFL. This league is SUPERFLEX, and
the previous version of this board tried to capture that by asserting a starter
requirement (QB = 2.0 per team) and deriving value from it. The league's own draft
history states the same fact directly and without the assumption: QB1 goes at
overall pick 2 here and QB5 at pick 10, where RB5 goes at 20. The format is
measured, not modelled. That is the whole argument for half 2 of the method.

Underdog being a 1QB best-ball format is therefore not a problem: we take only
"who is the better quarterback" from it, never "what is a quarterback worth here".
"""
import os
import re
import sqlite3
import statistics as st
import unicodedata
from collections import defaultdict

import numpy as np
from sklearn.isotonic import IsotonicRegression

# Copied, not imported: build_clean_data.py is a script and importing it rebuilds
# the entire database as a side effect.
PLAYER_ALIASES = {
    "robbiechosen": "robbyanderson", "stevenhauschka": "stephenhauschka",
    "elijahmitchell": "elimitchell", "kennygainwell": "kennethgainwell",
    "joshpalmer": "joshuapalmer", "chigokonkwo": "chigoziemokonkwo",
    "mikebadgley": "michaelbadgley", "marquisebrown": "hollywoodbrown",
}


def player_key(name):
    """Match key for a player across sources: fold accents, drop Jr/Sr/III."""
    n = unicodedata.normalize("NFKD", str(name).strip())
    n = n.encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", n)
    n = re.sub(r"[^a-z]", "", n)
    return PLAYER_ALIASES.get(n, n)


def pick_curves(picks, seasons, rounds, teams_per):
    """Where the Nth-best player at each position actually went, by overall pick.

    This is the cross-position half of the method: it is what makes a QB and an
    RB of the same positional rank comparable, and it is the ONLY thing in the
    board that knows this league is superflex.

    MONOTONE, BUT DELIBERATELY NOT SMOOTHED, and the distinction matters.

    The PBAFFL price curve is smoothed before fitting because each of its ADP
    ranks has only ~3 noisy observations. This curve does not need it, for a
    structural reason: position rank here is *defined* by draft order within a
    season, so pick(pos, rank) is strictly increasing inside every season, and a
    median across increasing sequences comes out increasing too. Measured: only
    4 inversions across 224 position-ranks, and every one sits in the ragged tail
    where a season did not draft that deep and the cell holds n<3.

    So IsotonicRegression is kept -- it repairs exactly those four tail cells and
    is a no-op everywhere else -- and pre-smoothing is not. A centred 3-wide mean
    was tried and rejected: on a curve this steep at the top it has no left
    neighbour at rank 1 and averages the first player at a position with the
    second, which moved RB1 from pick 2 to pick 6.5 and TE1 from 31 to 40. That
    is a whole round of error on the most consequential point of the curve, in
    exchange for suppressing curvature that is real rather than noise.

    Still NEVER np.maximum.accumulate for the monotone step -- a running extremum
    drags every later point up to any single spike. That is trap 9, which
    flattened eight ADP ranks to one price on the PBAFFL board.
    """
    by_rank = defaultdict(list)
    for y in seasons:
        seen = defaultdict(int)
        for p in sorted((p for p in picks if p["s"] == y), key=lambda x: x["o"]):
            seen[p["pos"]] += 1
            by_rank[(p["pos"], seen[p["pos"]])].append(p["o"])

    curves = {}
    for pos in {k[0] for k in by_rank}:
        ranks = sorted(r for (q, r) in by_rank if q == pos)
        raw = [st.median(by_rank[(pos, r)]) for r in ranks]
        fitted = IsotonicRegression(increasing=True).fit_transform(ranks, raw)
        curves[pos] = dict(zip(ranks, (round(float(v), 1) for v in fitted)))
    return curves


def extend(curve, rank, last_n=6):
    """Implied pick for a position rank deeper than the league has ever drafted.

    Underdog ranks 100 WRs; this league has never taken more than ~77 in a
    season, so the tail has no observations. Rather than drop those players --
    they are real waiver-round names and belong on the board -- extend the curve
    linearly at the slope of its last few points. They land past pick 216 and
    sort themselves out below the draftable pool, which is the honest answer.
    """
    if rank in curve:
        return curve[rank]
    ks = sorted(curve)
    if rank < ks[0]:
        return curve[ks[0]]
    tail = ks[-last_n:]
    if len(tail) < 2:
        return curve[ks[-1]]
    slope = (curve[tail[-1]] - curve[tail[0]]) / (tail[-1] - tail[0])
    return round(curve[ks[-1]] + slope * (rank - ks[-1]), 1)


def load_adp(db_path, season=2026):
    """Underdog for skill ordering; ESPN's own ADP is read from the board file.

    Returns {player_key: pos_rank}. Underdog carries QB/RB/WR/TE only -- it is a
    best-ball format with no kickers or defences at all (trap 8), which is why
    K and DEF are ordered from ESPN instead.
    """
    if not os.path.exists(db_path):
        return {}
    con = sqlite3.connect(db_path)
    have = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    if "preseason_adp" not in have:
        return {}
    out = {}
    for key, pos, adp in con.execute(
            "SELECT player_key, position, adp FROM preseason_adp"
            " WHERE season=? AND source='underdog' AND adp IS NOT NULL", (season,)):
        # keep the sharpest (lowest) ADP if a key somehow appears twice
        if key not in out or adp < out[key][1]:
            out[key] = (pos, adp)
    con.close()
    return out


def build_board(board_rows, picks, seasons, rounds, teams_per, db_path):
    """Apply the settled method. Returns (board, diagnostics)."""
    curves = pick_curves(picks, seasons, rounds, teams_per)
    ud = load_adp(db_path)

    board = []
    for f in board_rows:
        board.append(dict(pid=f[0], n=f[1], pos=f[2], tm=f[3], espn=int(f[4]),
                          adp=float(f[5]) if f[5] else None,
                          own=float(f[6]) if f[6] else None,
                          prj=float(f[7]) if f[7] else 0.0,
                          key=player_key(f[1])))

    # trap 1: never join on a folded name without checking it collides with nobody
    seen = defaultdict(list)
    for p in board:
        seen[p["key"]].append(p)
    collisions = {k: v for k, v in seen.items() if len(v) > 1}
    if collisions:
        raise SystemExit("name collision in the ESPN pool, refusing to join: "
                         + "; ".join(f"{k}: {[x['n'] for x in v]}"
                                     for k, v in collisions.items()))

    # ---- ordering WITHIN each position ------------------------------------
    # Underdog where it has him, ESPN's own ADP otherwise. Ranked densely inside
    # the ESPN pool, because the curve asks "the Nth back taken IN THIS LEAGUE" --
    # an Underdog back who is not on ESPN's board never gets taken here at all.
    SKILL = {"QB", "RB", "WR", "TE"}
    by_pos = defaultdict(list)
    for p in board:
        p["udAdp"] = ud[p["key"]][1] if (p["key"] in ud and p["pos"] in SKILL) else None
        p["src"] = "underdog" if p["udAdp"] is not None else "espn"
        by_pos[p["pos"]].append(p)

    for pos, lst in by_pos.items():
        # Underdog-ranked players first in ADP order, then anyone it does not
        # carry, in ESPN ADP order behind them. A player Underdog declines to
        # rank is one the sharp market is not drafting.
        withud = sorted((p for p in lst if p["udAdp"] is not None),
                        key=lambda x: x["udAdp"])
        without = sorted((p for p in lst if p["udAdp"] is None),
                         key=lambda x: (x["adp"] if x["adp"] is not None else 9e9,
                                        x["espn"]))
        for i, p in enumerate(withud + without, 1):
            p["prank"] = i

    # ---- weighting ACROSS positions ---------------------------------------
    for p in board:
        c = curves.get(p["pos"])
        p["pick"] = extend(c, p["prank"]) if c else None

    board.sort(key=lambda p: (p["pick"] is None, p["pick"], p["espn"]))
    for i, p in enumerate(board, 1):
        p["rank"] = i
        p["rd"] = (i - 1) // teams_per + 1
        p["pk"] = (i - 1) % teams_per + 1

    # ESPN's own order re-expressed inside the same pool, so "we say 2nd, ESPN
    # says 26th" is a like-for-like comparison rather than a rank measured
    # against a board that also contains kickers.
    for i, p in enumerate(sorted(board, key=lambda x: x["espn"]), 1):
        p["espnRank"] = i
    for p in board:
        p["gap"] = p["espnRank"] - p["rank"]

    diag = dict(
        curves={k: v for k, v in sorted(curves.items())},
        n_underdog=sum(1 for p in board if p["src"] == "underdog"),
        n_espn=sum(1 for p in board if p["src"] == "espn"),
        espn_ordered_skill=[p["n"] for p in board
                            if p["src"] == "espn" and p["pos"] in SKILL],
    )
    return board, diag
