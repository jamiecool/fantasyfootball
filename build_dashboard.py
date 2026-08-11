"""Generate a self-contained localhost dashboard of the key datasets.

Reads cleandata/fantasy.db, embeds the data as JSON, and writes
cleandata/dashboard.html -- no external libraries, no network, no build step.
Charts are inline SVG drawn by a small amount of vanilla JS.

Run:
    python build_dashboard.py
    python serve.py
    # then open http://localhost:8000/dashboard.html
"""
import json
import os
import sqlite3

import numpy as np
import pandas as pd

from strategy_rules import RULES

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "cleandata")
con = sqlite3.connect(os.path.join(OUT, "fantasy.db"))
D = {}

# Optional tables come from LIVE feeds, which build_all.py only runs with
# --refresh. A fresh clone therefore has a database without them, and an
# unguarded read there is the difference between a new collaborator getting a
# working dashboard and getting a stack trace.
_HAVE = {r[0] for r in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table'")}


def optional(table, sql, columns):
    """Query `table` if it exists, else an empty frame with these columns."""
    if table in _HAVE:
        return pd.read_sql(sql, con)
    print(f"  (no {table} table -- run: python build_all.py --refresh)")
    return pd.DataFrame(columns=columns)

# ---- 1. the 2026 board: price, projection, value ---------------------------
proj = pd.read_sql("""SELECT player_key, player_name, position, nfl_team,
                             proj_points FROM projections WHERE season = 2026""", con)
board = pd.read_csv(os.path.join(OUT, "analysis", "board_2026.csv"))
# Underdog re-prices continuously, so its ADP movement is the fastest signal we
# have on which way the room is drifting. FFC sets the level; Underdog the trend.
mv = pd.read_sql("""SELECT player_key, adp_delta FROM preseason_adp
                    WHERE season = 2026 AND source = 'underdog'""", con)
board = board.merge(mv.drop_duplicates("player_key"), on="player_key", how="left")
b = board.merge(proj[["player_key", "proj_points"]], on="player_key", how="left")
SL = {"QB": 12, "RB": 24, "WR": 36, "TE": 12, "K": 12, "DEF": 12}
rep = {p: (b[b.position == p].nlargest(n, "proj_points").proj_points.min()
           if (b.position == p).sum() >= n else 0) for p, n in SL.items()}
b["par"] = (b["proj_points"] - b["position"].map(rep)).clip(lower=0).round(1)
b["ppd"] = (b["par"] / b["est_price"]).round(2)

# STRAIGHT MARKET ORDERING. This used to blend 75% market rank with 25% of
# Sleeper's projection rank; Jamie's call to drop the model entirely, and the
# measurement agrees -- two independent markets agree with each other at rho
# 0.95 while either agrees with Sleeper at 0.65-0.72, so the model was the
# outlier. The badge is now purely Underdog's ordering within position.
b = b.sort_values("adp_rank")
b["posrank"] = b.groupby("position").cumcount() + 1          # market rank, WR8
b["projrank"] = b.groupby("position")["proj_points"].rank(
    ascending=False, method="first").fillna(0).astype(int)   # kept for analytics only
b["blendrank"] = b["posrank"]

# ---- Yahoo: the market our leaguemates actually stare at while bidding ------
# We draft in the Yahoo app, so Yahoo's ADP is the room's anchor. Where our
# board and Yahoo disagree is where the room is likely to misprice a player
# relative to what he should cost here.
ydf = optional("yahoo_adp",
               "SELECT player_key, yahoo_rank, average_cost, percent_drafted"
               " FROM yahoo_adp",
               ["player_key", "yahoo_rank", "average_cost", "percent_drafted"]
               ).drop_duplicates("player_key")
b = b.merge(ydf, on="player_key", how="left")
b["yahoo_rank"] = b["yahoo_rank"].fillna(0).astype(int)
b["yahoo_cost"] = b["average_cost"].fillna(0).round(1)
# ---- Vegas: how good is the offence he plays in ----------------------------
# Explicitly NOT part of pricing or ordering -- ADP already contains this, and
# rule 4 says the market beats our re-derivation of it. It rides along as a
# visual check while scanning the board: is this a good player on a good team?
vt = optional("vegas_team", "SELECT * FROM vegas_team",
              ["team", "pts_per_game", "playoff_pts", "week_15", "week_16",
               "week_17", "vegas_rank"])


def vegas_tiers(df):
    """Diverging tiers -3..+3 around the league, and a PER-GAME playoff number.

    playoff_pts as published is the sum of weeks 15, 16 and 17, which is not
    comparable to the points-per-game column sitting next to it. Averaging the
    three makes both columns the same unit, so 26.1 season against 26.3 playoff
    reads directly.
    """
    wk = [c for c in ("week_15", "week_16", "week_17") if c in df.columns]
    df["playoff_avg"] = (df[wk].mean(axis=1) if wk
                         else df["playoff_pts"] / 3).round(1)
    for src, dest in (("pts_per_game", "yr_tier"), ("playoff_avg", "post_tier")):
        # 7 buckets so the middle of the league reads as neutral rather than
        # being forced into a colour it has not earned
        df[dest] = pd.qcut(df[src].rank(method="first"), 7,
                           labels=[-3, -2, -1, 0, 1, 2, 3]).astype(int)
    return df


vt = vegas_tiers(vt)
b = b.merge(vt[["team", "pts_per_game", "playoff_pts", "playoff_avg", "yr_tier",
                "post_tier", "vegas_rank"]].rename(columns={"team": "nfl_team"}),
            on="nfl_team", how="left")
for c, d in [("pts_per_game", 0.0), ("playoff_pts", 0.0), ("playoff_avg", 0.0),
             ("yr_tier", 0), ("post_tier", 0), ("vegas_rank", 0)]:
    b[c] = b[c].fillna(d)
for c in ("yr_tier", "post_tier", "vegas_rank"):
    b[c] = b[c].astype(int)

# ---- fair value (see build_fair_prices.py) ---------------------------------
# What each player is worth if every dollar bought the same production above
# replacement, as against est_price which is what the room will actually pay.
_fp = os.path.join(OUT, "analysis", "fair_prices_2026.csv")
if os.path.exists(_fp):
    fair = pd.read_csv(_fp)[["player_key", "fair_price", "fair_gap", "exp_par",
                             "peer_n", "peer_lo", "peer_hi", "peers"]]
    b = b.merge(fair.drop_duplicates("player_key"), on="player_key", how="left")
else:
    b["fair_price"], b["fair_gap"], b["exp_par"] = b["est_price"], 0, 0.0
    b["peer_n"], b["peer_lo"], b["peer_hi"], b["peers"] = 1, 0, 0, ""
b["fair_price"] = b["fair_price"].fillna(b["est_price"]).astype(int)
b["fair_gap"] = b["fair_gap"].fillna(0).astype(int)
b["exp_par"] = b["exp_par"].fillna(0).round(0).astype(int)
# how many players the fit cannot tell apart from this one -- 181 of 192 sit in
# a group of 2+, so the gap is mostly a WITHIN-TIER statement and has to say so
for c, d in [("peer_n", 1), ("peer_lo", 0), ("peer_hi", 0)]:
    b[c] = b[c].fillna(d).astype(int)
b["peers"] = b["peers"].fillna("")

b["move"] = b["adp_delta"].fillna(0).round(1) if "adp_delta" in b else 0.0
D["board"] = b.nsmallest(400, "adp_rank")[
    ["adp_rank", "player_name", "player_key", "position", "posrank", "projrank",
     "blendrank", "move", "nfl_team", "adp", "est_price", "proj_points",
     "yahoo_rank", "yahoo_cost", "pts_per_game", "playoff_pts", "playoff_avg",
     "yr_tier", "post_tier", "vegas_rank",
     "fair_price", "fair_gap", "exp_par",
     "peer_n", "peer_lo", "peer_hi", "peers"]].fillna(0).to_dict("records")

# ---- 3. positional share of spend, by season -------------------------------
sp = pd.read_sql("""SELECT season, position, SUM(price) s FROM draft_picks
                    GROUP BY season, position""", con)
tot = sp.groupby("season")["s"].transform("sum")
sp["pct"] = (100 * sp["s"] / tot).round(1)
D["posshare"] = sp.pivot(index="season", columns="position",
                         values="pct").fillna(0).reset_index().to_dict("records")

# ---- 4. value returned per dollar, by price tier ---------------------------
d = pd.read_sql("""SELECT d.season, d.price, d.position, COALESCE(f.points,0) pts
                   FROM draft_picks d LEFT JOIN final_ranks f
                   ON f.season=d.season AND f.player_key=d.player_key
                   WHERE d.position IN ('QB','RB','WR','TE')""", con)
fr = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)
SLOT = {"QB": 1, "RB": 2, "WR": 3, "TE": 1}
r2 = {}
for (s, p), g in fr.groupby(["season", "position"]):
    if p in SLOT:
        n = (10 if s == 2020 else 12) * SLOT[p]
        row = g[g.pos_rank == n]
        r2[(s, p)] = row.points.iloc[0] if len(row) else 0
d["par"] = [max(0, x.pts - r2.get((x.season, x.position), 0)) for x in d.itertuples()]
T, L = [0, 2, 5, 10, 20, 35, 100], ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]
d["tier"] = pd.cut(d["price"], bins=T, labels=L)
g = d.groupby("tier", observed=True).agg(picks=("price", "size"),
                                         spend=("price", "sum"), par=("par", "sum"))
g["ratio"] = ((100 * g.par / g.par.sum()) / (100 * g.spend / g.spend.sum())).round(2)
D["tiervalue"] = g.reset_index().rename(columns={"tier": "label"})[
    ["label", "picks", "ratio"]].to_dict("records")

# ---- 5. startable rate, position x tier ------------------------------------
d2 = pd.read_sql("""SELECT d.season, d.price, d.position, f.pos_rank
                    FROM draft_picks d LEFT JOIN final_ranks f
                    ON f.season=d.season AND f.player_key=d.player_key
                    WHERE d.position IN ('QB','RB','WR','TE')""", con)
teams = d2["season"].map(lambda s: 10 if s == 2020 else 12)
d2["need"] = teams * d2["position"].map(SLOT)
d2["ok"] = d2["pos_rank"].notna() & (d2["pos_rank"] <= d2["need"])
d2["tier"] = pd.cut(d2["price"], bins=T, labels=L)
st = d2.groupby(["position", "tier"], observed=True).agg(
    n=("ok", "size"), rate=("ok", "mean")).reset_index()
st["rate"] = (100 * st["rate"]).round(0)
st["tier"] = st["tier"].astype(str)
D["startable"] = st.to_dict("records")

# ---- 6. where the two markets disagree -------------------------------------
mk = pd.read_sql("""SELECT player_name, player_key, position, source, adp
                    FROM preseason_adp
                    WHERE season=2026 AND scoring_format='half-ppr'""", con)
piv = mk.pivot_table(index=["player_name", "player_key", "position"], columns="source",
                     values="adp", aggfunc="min").reset_index()
if {"ffc", "underdog"} <= set(piv.columns):
    piv = piv.dropna(subset=["ffc", "underdog"])
    piv["gap"] = (piv["underdog"] - piv["ffc"]).round(1)
    D["markets"] = piv[piv.ffc <= 120].to_dict("records")
else:
    D["markets"] = []

# ---- 7. every season's draft, with how each pick turned out ----------------
SLOT_ALL = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}
MED_SLOT = {"QB": 0.5, "RB": 1.0, "WR": 1.5, "TE": 0.5, "K": 0.5, "DEF": 0.5}
SEASONS = [int(s) for s in pd.read_sql(
    "SELECT DISTINCT season FROM draft_picks ORDER BY season DESC", con).season]
fr_all = pd.read_sql("SELECT season,position,pos_rank,points FROM final_ranks", con)
stand = pd.read_sql("SELECT season,franchise,rank,wins,losses,points_for,finish "
                    "FROM standings", con)
D["draft"], D["draft_teams"] = {}, {}

for season in SEASONS:
    teams_n = 10 if season == 2020 else 12
    dr = pd.read_sql(f"""
        SELECT d.nomination_order nom, d.price, d.player_name, d.player_key,
               d.position, d.nfl_team,
               d.franchise, d.price_source, f.pos_rank, f.points, f.games
        FROM draft_picks d
        LEFT JOIN final_ranks f ON f.season = d.season AND f.player_key = d.player_key
        WHERE d.season = {season}
        ORDER BY d.price DESC, d.nomination_order
    """, con)
    if not len(dr):
        continue
    need = dr["position"].map(SLOT_ALL) * teams_n
    dr["startable"] = dr["pos_rank"].notna() & (dr["pos_rank"] <= need)
    dr["finish"] = [f"{r.position}{int(r.pos_rank)}" if pd.notna(r.pos_rank) else "—"
                    for r in dr.itertuples()]

    # EXPECTATION COMES FROM THE PRICE PAID. The room's own pricing is the bar:
    # the 3rd-most-expensive RB was bought to be about RB3. (An earlier version
    # bucketed price into six bands, so every $36+ player shared one expectation
    # -- Nacua, McCaffrey and Nabers all read "RB10/WR10" whatever was paid.)
    dr["exp_rank"] = dr.groupby("position")["price"].rank(ascending=False,
                                                          method="first")
    act = dr["pos_rank"].fillna(96)
    # rank gap taken BEFORE any bucketing, so a 1-rank move can't score the same
    # as an 11-rank move; kept as the auditable column
    dr["gap"] = (dr["exp_rank"] - act).round(0).astype(int)
    dr["exp_label"] = [f"{r.position}{int(round(r.exp_rank))}" for r in dr.itertuples()]

    # Shade by PRODUCTION gained, not rank: RB1->RB6 is 80 points while
    # RB50->RB55 is 6. Expected production = what the player who actually
    # finished at your price rank scored that season; normalised by the
    # position's median starter so every position lands on one scale.
    fs = fr_all[fr_all.season == season]
    cp = {(r.position, int(r.pos_rank)): r.points for r in fs.itertuples()}
    med = {p: cp.get((p, int(round(MED_SLOT[p] * teams_n))), np.nan) for p in SLOT_ALL}

    def points_at(pos, rank, _cp=cp):
        r = int(round(rank))
        while r > 0:
            if (pos, r) in _cp:
                return _cp[(pos, r)]
            r -= 1                    # deeper than anyone ranked -> nearest above
        return 0.0

    dr["exp_points"] = [points_at(r.position, r.exp_rank) for r in dr.itertuples()]
    dr["val"] = ((dr["points"] - dr["exp_points"]) / dr["position"].map(med)) \
        .replace([np.inf, -np.inf], np.nan).fillna(0).round(2)
    # one shade step = 0.2 of a median starter's output
    dr["delta"] = np.clip(np.round(dr["val"] / 0.2), -3, 3).astype(int)
    dr["points"] = dr["points"].fillna(0).round(0)
    dr["games"] = dr["games"].fillna(0).astype(int)
    dr["nom"] = dr["nom"].fillna(0).astype(int)
    D["draft"][str(season)] = dr.drop(columns=["pos_rank", "exp_points"]) \
        .fillna("").to_dict("records")

    team = (dr.groupby("franchise")
            .agg(picks=("price", "size"), spend=("price", "sum"),
                 pts=("points", "sum"), starters=("startable", "sum"),
                 top=("price", "max")).reset_index())
    team = team.merge(stand[stand.season == season].drop(columns=["season"]),
                      on="franchise", how="left").sort_values("spend", ascending=False)
    D["draft_teams"][str(season)] = team.fillna("").to_dict("records")

D["starters"] = STARTERS_CFG = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "K": 1, "DEF": 1}
D["budget"], D["spots"] = 200, 16
_ps = pd.read_sql("""SELECT position, SUM(price) s FROM draft_picks
                     WHERE season BETWEEN 2023 AND 2025 GROUP BY position""", con)
D["league_pos_share"] = {r.position: round(100 * r.s / _ps.s.sum(), 1)
                         for r in _ps.itertuples()}

D["seasons_list"] = SEASONS
D["last_season"] = SEASONS[0]

# ---- 9. strategy rules (content lives in strategy_rules.py) ---------------
D["rules"] = RULES

# ---- 10. NFL stats: every game line, scored under THIS league --------------
# Published stat sites show points under their own default scoring, which is not
# this league's -- interceptions here are -2, not -1, and receptions are 0.5.
# These come from build_clean_data.py's league_points(), so the number in the
# game log is the number the player actually banked for whoever started him.
#
# Nested player-season -> games rather than a flat row list: the flat form
# repeats a player index on all 55k rows for no gain. Points are rounded to 1dp
# and stats are ints, which is what keeps this near 2.5MB instead of 8.
WK_COLS = ["cmp", "att", "pass_yd", "pass_td", "int", "car", "rush_yd", "rush_td",
           "tgt", "rec", "rec_yd", "rec_td", "st_td", "fum_lost", "two_pt",
           "fg", "fg_att", "fg_long", "pat"]
pw = pd.read_sql("SELECT * FROM player_weeks", con)
_price = pd.read_sql("""SELECT season, player_key, price, franchise
                        FROM draft_picks""", con)
_price = {(r.season, r.player_key): (int(r.price), r.franchise)
          for r in _price.itertuples()}
_rank = pd.read_sql("""SELECT season, player_key, pos_rank, overall_rank
                       FROM final_ranks""", con)
_rank = {(r.season, r.player_key): (int(r.pos_rank), int(r.overall_rank))
         for r in _rank.itertuples()}

TEAMS = sorted(set(pw["opponent"].dropna().astype(str)) | set(pw["nfl_team"].dropna().astype(str)))
TIDX = {t: i for i, t in enumerate(TEAMS)}
ps_rows = []
for (season, key), g in pw.groupby(["season", "player_key"], sort=False):
    g = g.sort_values("week")
    first = g.iloc[0]
    price, franchise = _price.get((season, key), (None, ""))
    pos_rank, ovr = _rank.get((season, key), (None, None))
    games = [[int(r.week), TIDX.get(r.opponent, -1), round(float(r.points), 1)]
             + [int(getattr(r, c)) for c in WK_COLS] for r in g.itertuples()]
    ps_rows.append([first.player_name, first.position, first.nfl_team, int(season),
                    price, franchise, pos_rank, ovr, games, key])
# heaviest scorers first so the default view needs no sort pass
ps_rows.sort(key=lambda r: -sum(x[2] for x in r[8]))

# Boom / bust thresholds, derived rather than assumed. 20 points is a big week
# for a tight end and a mediocre one for a quarterback, so a single cutoff would
# paint QB logs green and TE logs red for nothing. Measure the weekly
# distribution of STARTER-QUALITY players at each position -- boom is the top
# 15% of their weeks, bust the bottom 25% -- and every position is judged
# against the players you would actually have started there.
STARTABLE_N = {"QB": 12, "RB": 24, "WR": 36, "TE": 12, "K": 12}
_startable = {(s, k) for (s, k), (pr, _o) in _rank.items()}
_pr = {(s, k): pr for (s, k), (pr, _o) in _rank.items()}
pw["_pr"] = [_pr.get((r.season, r.player_key), 999) for r in pw.itertuples()]
_st = pw[pw["_pr"] <= pw["position"].map(STARTABLE_N).fillna(0)]
THRESH = {p: [round(float(g["points"].quantile(0.85)), 1),
              round(float(g["points"].quantile(0.25)), 1)]
          for p, g in _st.groupby("position") if len(g) >= 200}
print("\nboom/bust thresholds from starter-quality weeks (p85 / p25):")
for p, (b, u) in sorted(THRESH.items()):
    n = int((_st["position"] == p).sum())
    print(f"  {p:3} boom >= {b:5.1f}   bust <= {u:5.1f}   ({n:,} weeks)")

D["wk"] = {"cols": WK_COLS, "teams": TEAMS, "ps": ps_rows, "thresh": THRESH,
           "seasons": sorted({int(s) for s in pw["season"].unique()}, reverse=True)}

# ---- 11. Vegas page --------------------------------------------------------
_vt = optional("vegas_team", "SELECT * FROM vegas_team ORDER BY vegas_rank",
               ["team", "pts_per_game", "playoff_pts", "week_15", "week_16",
                "week_17", "vegas_rank"])
_vt = vegas_tiers(_vt) if len(_vt) else _vt.assign(playoff_avg=0, yr_tier=0, post_tier=0)
_bd = pd.DataFrame(D["board"])
# how many draftable players each offence actually supplies, so the page answers
# "who does this get me" rather than just ranking teams
_cnt = _bd[_bd.est_price >= 3].groupby("nfl_team").size().rename("draftable")
_top = (_bd.sort_values("est_price", ascending=False)
        .groupby("nfl_team").head(3)
        .groupby("nfl_team")
        .apply(lambda g: ", ".join(f"{r.player_name} ({r.position}, ${r.est_price})"
                                   for r in g.itertuples()), include_groups=False)
        .rename("top_players"))
_vt = _vt.merge(_cnt, left_on="team", right_index=True, how="left")          .merge(_top, left_on="team", right_index=True, how="left")
_vt["draftable"] = _vt["draftable"].fillna(0).astype(int)
_vt["top_players"] = _vt["top_players"].fillna("—")
D["vegas"] = _vt.fillna(0).to_dict("records")
D["vegas_weeks"] = optional(
    "vegas_team_week",
    "SELECT week, team, opponent, is_home, spread_line, total_line, implied_total"
    " FROM vegas_team_week WHERE season = 2026 ORDER BY week, implied_total DESC",
    ["week", "team", "opponent", "is_home", "spread_line", "total_line",
     "implied_total"]).to_dict("records")

# ---- 12. dead zones by position (see analyze_dead_zones.py) ----------------
_dz = os.path.join(OUT, "analysis", "dead_zones.csv")
# .where on a float column hands NaN straight back, which serialises to the
# JS literal NaN and renders as "NaN" -- cast to object first so it is null
D["deadzones"] = (pd.read_csv(_dz).astype(object).where(lambda d: d.notna(), None)
                  .to_dict("records") if os.path.exists(_dz) else [])
D["deadzone_bands"] = ["$1-2", "$3-5", "$6-10", "$11-20", "$21-35", "$36+"]

# ---- 8. headline numbers ---------------------------------------------------
adp_real = pd.read_sql("""SELECT p.season,p.adp,f.overall_rank fr FROM v_preseason p
    JOIN final_ranks f ON f.season=p.season AND f.player_key=p.player_key
    WHERE p.season BETWEEN 2017 AND 2025""", con)
rho = np.mean([g.adp.corr(g.fr, method="spearman")
               for _, g in adp_real.groupby("season")])
D["stats"] = {
    "adp_vs_reality": round(rho, 2),
    "seasons": int(pd.read_sql("SELECT COUNT(*) n FROM seasons", con).n[0]),
    "picks": int(pd.read_sql("SELECT COUNT(*) n FROM draft_picks", con).n[0]),
    "board_players": int(len(board)),
}

html = open(os.path.join(ROOT, "dashboard_template.html"), encoding="utf-8").read()
# compact separators -- 55k game lines make the default ", " / ": " padding
# worth ~2MB of pure whitespace
html = html.replace("__DATA__", json.dumps(D, default=str, separators=(",", ":")))
path = os.path.join(OUT, "dashboard.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {path}")
print("\nserve it with:")
print("  python serve.py")
print("  open http://localhost:8000/dashboard.html")
print("\n(serve.py disables caching; plain http.server lets Chrome answer F5")
print(" from memory, so a rebuilt dashboard silently does not appear)")
