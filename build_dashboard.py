"""Generate a self-contained localhost dashboard of the key datasets.

Reads cleandata/fantasy.db, embeds the data as JSON, and writes
cleandata/dashboard.html -- no external libraries, no network, no build step.
Charts are inline SVG drawn by a small amount of vanilla JS.

Run:
    python build_dashboard.py
    python -m http.server 8000 --directory cleandata
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

# The board's job is "what will the room pay", so ADP carries the ranking and
# projections only nudge it. Weight reflects what we measured: two independent
# markets agree with each other at rho 0.95 while either agrees with Sleeper's
# model at only 0.65-0.72, so the model is the outlier and gets the small share.
ADP_WEIGHT = 0.75
b = b.sort_values("adp_rank")
b["posrank"] = b.groupby("position").cumcount() + 1          # market rank, QB3
b["projrank"] = b.groupby("position")["proj_points"].rank(
    ascending=False, method="first").fillna(0).astype(int)   # model rank
b["blend"] = (ADP_WEIGHT * b["posrank"] + (1 - ADP_WEIGHT) * b["projrank"])
b["blendrank"] = b.groupby("position")["blend"].rank(method="first").astype(int)
b["move"] = b["adp_delta"].fillna(0).round(1) if "adp_delta" in b else 0.0
D["board"] = b.nsmallest(400, "adp_rank")[
    ["adp_rank", "player_name", "position", "posrank", "projrank", "blendrank",
     "move", "nfl_team", "adp", "est_price", "proj_points"]].fillna(0).to_dict("records")

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
mk = pd.read_sql("""SELECT player_name, position, source, adp FROM preseason_adp
                    WHERE season=2026 AND scoring_format='half-ppr'""", con)
piv = mk.pivot_table(index=["player_name", "position"], columns="source",
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
        SELECT d.nomination_order nom, d.price, d.player_name, d.position, d.nfl_team,
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
html = html.replace("__DATA__", json.dumps(D, default=str))
path = os.path.join(OUT, "dashboard.html")
with open(path, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {path}")
print("\nserve it with:")
print("  python -m http.server 8000 --directory cleandata")
print("  open http://localhost:8000/dashboard.html")
