"""Perennial Push draft board: Value Based Drafting from this league's own history.

Method (settled 2026-09-04 after reviewing Bryant's VBD, FantasyPros VORP/VOLS/VONA,
Subvertadown's baseline guide and Footballguys' superflex QB work):

  1. PROJECTION for a positional slot = what the Nth player TAKEN at that position
     actually scored, averaged over the last three seasons under this league's
     scoring. Nth-TAKEN, not Nth-FINISHER: the average of the finishers is an
     order statistic (the luckiest player's total), the average of the Nth taken is
     the expected value of the slot you are actually drafting. Three seasons give
     three observations per slot, far too jagged to use raw, so each position's
     curve is a least-squares fit of points = a + b*ln(rank) + c*rank over every
     (rank, points) pair in the window -- the standard smooth, decaying shape of a
     positional curve -- checked monotone (falls back to an isotonic fit if not).
     The R^2 of that fit is printed: it is how much of the scoring this room's
     draft order actually explains at that position. No outside projection feed.
  2. BASELINE per position = Bryant's draft-demand rule: how many of that position
     this room takes within the first BASELINE_PICKS picks, averaged across the
     seasons. The projection of that slot is zero value. This is neither
     worst-starter nor waiver-wire; it is the room's own scarcity, and it carries
     superflex and FLEX automatically (a 2-QB room takes ~23 QBs in the top 100).
     K and D/ST are not valued: the room takes ~0 of them in the top 100, so their
     baseline is their own #1 -- they are listed at the bottom as late fill.
  3. ORDERING within a position is Underdog's 2026 ADP. Whoever Underdog has as RB3
     gets the RB3 slot projection. Underdog carries no K/DEF; those two use ESPN.
  4. VALUE = slot projection minus baseline projection; the board ranks on value.

Run:  python build_ppp_vor_board.py     -> cleandata/analysis/ppp_vor_board.csv
"""
import csv
import math
import os
import re
import statistics as st
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
PPP = os.path.join(ROOT, "rawdata", "ppp")
UNDERDOG = os.path.join(ROOT, "rawdata", "underdog", "underdog_adp_2026.csv")
ESPN_BOARD = os.path.join(PPP, "board2026.psv")
OUT = os.path.join(ROOT, "cleandata", "analysis", "ppp_vor_board.csv")

SEASONS = [2023, 2024, 2025]          # "the last three years"
TEAMS = 12
ROUNDS = 18
BASELINE_PICKS = 100                  # Bryant's draft-demand horizon
VALUED = ["QB", "RB", "WR", "TE"]
FILL = ["K", "DEF"]                   # listed, not valued
POSITIONS = VALUED + FILL

try:                                  # the repo's shared normaliser
    from ppp_board import player_key
    KEY_SRC = "ppp_board.player_key"
except Exception:                     # noqa: BLE001
    def player_key(name):
        n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
        n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", n)
        return re.sub(r"[^a-z]", "", n)
    KEY_SRC = "local copy of build_clean_data.player_key (no aliases)"


def isotonic_decreasing(y):
    """Pool-adjacent-violators: closest non-increasing sequence to y (least squares)."""
    blocks = [[v, 1] for v in y]                    # [mean, count]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] < blocks[i + 1][0]:         # violation: later block higher
            m, n = blocks[i], blocks[i + 1]
            merged = [(m[0] * m[1] + n[0] * n[1]) / (m[1] + n[1]), m[1] + n[1]]
            blocks[i:i + 2] = [merged]
            i = max(i - 1, 0)
        else:
            i += 1
    out = []
    for m, n in blocks:
        out.extend([m] * n)
    return out


def lstsq(X, y):
    """Ordinary least squares via normal equations (tiny systems, no numpy needed)."""
    n = len(X[0])
    A = [[sum(X[k][i] * X[k][j] for k in range(len(X))) for j in range(n)] for i in range(n)]
    b = [sum(X[k][i] * y[k] for k in range(len(X))) for i in range(n)]
    for i in range(n):
        piv = A[i][i]
        A[i] = [v / piv for v in A[i]]
        b[i] /= piv
        for k in range(n):
            if k != i:
                f = A[k][i]
                A[k] = [vk - f * vi for vk, vi in zip(A[k], A[i])]
                b[k] -= f * b[i]
    return b


def fit_curve(points, n):
    """Smooth decaying positional curve through (rank, pts) pairs; returns ([pred 1..n], R^2)."""
    feat = lambda r: [1.0, math.log(r), float(r)]
    X = [feat(r) for r, _ in points]
    y = [v for _, v in points]
    c = lstsq(X, y)
    pred = [sum(a * f for a, f in zip(c, feat(r))) for r in range(1, n + 1)]
    ybar = st.mean(y)
    r2 = 1 - sum((v - sum(a * f for a, f in zip(c, feat(r)))) ** 2 for r, v in points) / \
        sum((v - ybar) ** 2 for v in y)
    if any(pred[i] < pred[i + 1] for i in range(n - 1)):
        pred = isotonic_decreasing(pred)
    return pred, r2


# ---- 1. slot projections: what the Nth player TAKEN at each position scored ---
taken = defaultdict(list)                          # (pos, rank) -> [pts per season]
demand = defaultdict(list)                         # pos -> [count in first BASELINE_PICKS per season]
for season in SEASONS:
    picks = defaultdict(list)                      # pos -> [(overall, pts)]
    with open(os.path.join(PPP, f"draft{season}.psv"), encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if len(p) < 9 or p[8] == "" or not p[0].isdigit():
                continue
            picks[p[7]].append((int(p[0]), float(p[8])))
    for pos in POSITIONS:
        lst = sorted(picks.get(pos, []))
        demand[pos].append(sum(1 for ov, _ in lst if ov <= BASELINE_PICKS))
        for rank, (_, pts) in enumerate(lst, 1):
            taken[(pos, rank)].append(pts)

raw = {}
slot = {}
depth = {}
fit_r2 = {}
for pos in POSITIONS:
    n = max((r for (p, r) in taken if p == pos), default=0)
    # fit only over ranks every season reached, so the tail is not one season's stragglers
    n = max((r for r in range(1, n + 1) if len(taken[(pos, r)]) == len(SEASONS)), default=0)
    depth[pos] = n
    for r in range(1, n + 1):
        raw[(pos, r)] = st.mean(taken[(pos, r)])
    pts_pairs = [(r, v) for r in range(1, n + 1) for v in taken[(pos, r)]]
    pred, fit_r2[pos] = fit_curve(pts_pairs, n)
    for r, v in enumerate(pred, 1):
        slot[(pos, r)] = v

BASELINE = {pos: max(1, round(st.mean(demand[pos]))) for pos in VALUED}


def proj(pos, rank):
    return slot.get((pos, rank))


def base(pos):
    return proj(pos, BASELINE[pos])


# ---- 2. ordering: Underdog within position; ESPN for K and D/ST -------------
order = defaultdict(list)                          # pos -> [(sort_key, name, source)]
with open(UNDERDOG, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if r["adp"] in ("", "None"):
            continue
        order[r["position"].upper()].append((float(r["adp"]), r["player_name"], "underdog"))
espn_rank = {}
with open(ESPN_BOARD, encoding="utf-8") as f:
    for line in f:
        p = line.rstrip("\n").split("|")
        if len(p) < 5:
            continue
        espn_rank[player_key(p[1])] = int(p[4]) if p[4] else None
        if p[2] in FILL and p[4]:
            order[p[2]].append((int(p[4]), p[1], "espn"))

# ---- 3. value over baseline --------------------------------------------------
rows = []
for pos in POSITIONS:
    for rank, (_, name, src) in enumerate(sorted(order[pos]), 1):
        pr = proj(pos, rank)
        v = None if (pr is None or pos in FILL) else pr - base(pos)
        rows.append({
            "player": name, "pos": pos, "pos_rank": rank, "order_source": src,
            "proj": None if pr is None else round(pr, 1),
            "proj_raw": None if (pos, rank) not in raw else round(raw[(pos, rank)], 1),
            "baseline_rank": BASELINE.get(pos),
            "baseline_pts": None if pos in FILL else round(base(pos), 1),
            "value": None if v is None else round(v, 1),
            "espn_rank": espn_rank.get(player_key(name)),
        })
board = sorted([r for r in rows if r["value"] is not None], key=lambda r: (-r["value"], r["pos_rank"]))
fill = [r for r in rows if r["pos"] in FILL and r["pos_rank"] <= TEAMS]
beyond = [r for r in rows if r["pos"] in VALUED and r["value"] is None]
for i, r in enumerate(board + fill, 1):
    r["board_rank"] = i
    r["rd_pk"] = f"{(i - 1) // TEAMS + 1}.{(i - 1) % TEAMS + 1:02d}"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
cols = ["board_rank", "rd_pk", "player", "pos", "pos_rank", "proj", "value", "baseline_rank",
        "baseline_pts", "proj_raw", "order_source", "espn_rank"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    w.writerows(board + fill)

# ---- 4. report -----------------------------------------------------------
print(f"seasons {SEASONS}   projection = smooth fit of Nth-taken scoring   "
      f"baseline = taken in first {BASELINE_PICKS} picks   ordering: Underdog (K/DEF: ESPN)")
print(f"name key: {KEY_SRC}")
print(f"wrote {os.path.relpath(OUT, ROOT)}  ({len(board)} valued + {len(fill)} K/DEF fill; "
      f"{len(beyond)} Underdog players ranked past this league's draft history)\n")

print("DRAFT DEMAND -- how many of each position this room takes in the first "
      f"{BASELINE_PICKS} picks (this sets the baseline)")
print(f"{'':>5}" + "".join(f"{s:>7}" for s in SEASONS) + f"{'base':>7}{'base pts':>10}{'fit R2':>8}{'depth':>7}")
for pos in POSITIONS:
    b = BASELINE.get(pos)
    bp = f"{base(pos):>10.0f}" if pos in VALUED else f"{'n/a':>10}"
    print(f"{pos:>5}" + "".join(f"{d:>7}" for d in demand[pos]) + f"{(b if b else '-'):>7}" + bp
          + f"{fit_r2.get(pos, 0):>8.2f}{depth[pos]:>7}")

print("\nPOSITIONAL CURVE -- expected points of the Nth player taken (smoothed), and value over baseline")
ranks = [1, 2, 3, 5, 8, 12, 16, 20, 24, 30, 36, 48]
print(f"{'':>5}" + "".join(f"{('#' + str(r)):>7}" for r in ranks))
for pos in VALUED:
    print(f"{pos:>5}" + "".join(f"{proj(pos, r):>7.0f}" if proj(pos, r) is not None else f"{'-':>7}" for r in ranks))
print()
print(f"{'':>5}" + "".join(f"{('V#' + str(r)):>7}" for r in ranks))
for pos in VALUED:
    print(f"{pos:>5}" + "".join(f"{proj(pos, r) - base(pos):>+7.0f}" if proj(pos, r) is not None else f"{'-':>7}" for r in ranks))

print("\nWHERE THE BOARD PUTS EACH POSITION (vs where Underdog's own ADP puts them)")
ud = sorted([r for r in rows if r["order_source"] == "underdog"],
            key=lambda r: [k for k in order[r["pos"]] if k[1] == r["player"]][0][0])
print(f"{'rounds':>8}" + "".join(f"{p:>5}" for p in VALUED) + "   |" + "".join(f"{p:>5}" for p in VALUED) + "  (Underdog)")
for lo, hi in [(1, 2), (3, 4), (5, 6), (7, 9), (10, 12), (13, 15), (16, 18)]:
    seg = [r for r in board if lo <= (r["board_rank"] - 1) // TEAMS + 1 <= hi]
    useg = ud[(lo - 1) * TEAMS: hi * TEAMS]
    print(f"{f'{lo}-{hi}':>8}" + "".join(f"{sum(1 for r in seg if r['pos'] == p):>5}" for p in VALUED)
          + "   |" + "".join(f"{sum(1 for r in useg if r['pos'] == p):>5}" for p in VALUED))

print("\nTOP 36 BY VALUE OVER BASELINE")
for r in board[:36]:
    e = f"ESPN #{r['espn_rank']}" if r["espn_rank"] else ""
    print(f"  {r['rd_pk']}  {r['player']:<24}{r['pos']:>3}{r['pos_rank']:<3} proj {r['proj']:>6.1f}  "
          f"value {r['value']:>+6.1f}  {e}")

print(f"\nSENSITIVITY: baseline horizon (first N picks) -> first three rounds' mix")
for N in (80, 100, 120):
    alt = {}
    for pos in VALUED:
        cnt = []
        for season in SEASONS:
            with open(os.path.join(PPP, f"draft{season}.psv"), encoding="utf-8") as f:
                cnt.append(sum(1 for line in f
                               if (p := line.rstrip("\n").split("|"))[0].isdigit()
                               and int(p[0]) <= N and p[7] == pos))
        alt[pos] = max(1, min(depth[pos], round(st.mean(cnt))))
    def v(r):
        pr = proj(r["pos"], r["pos_rank"])
        return None if pr is None else pr - proj(r["pos"], alt[r["pos"]])
    ab = sorted([r for r in rows if r["pos"] in VALUED and v(r) is not None], key=lambda r: -v(r))[:36]
    print(f"  N={N:<4} baselines " + " ".join(f"{p}{alt[p]}" for p in VALUED) +
          "  -> " + ", ".join(f"{sum(1 for r in ab if r['pos'] == p)} {p}" for p in VALUED))
