"""Normalize 9 seasons of PBFFL auction-draft results into a clean SQLite DB.

Every season was kept in a differently-shaped workbook. This script reads them
all, reconciles them onto one schema, and writes:

    cleandata/fantasy.db        SQLite (primary, analysis-ready)
    cleandata/csv/*.csv         same tables as text (git-diffable, eyeballable)
    cleandata/parquet/*.parquet same tables for fast pandas/Arrow loads
    cleandata/franchise_map.csv EDITABLE team-identity mapping (see README)

Run:  python build_clean_data.py
"""
import glob
import json
import os
import re
import sqlite3
import unicodedata

import pandas as pd
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "rawdata", "historicalresults")
RAW25 = os.path.join(ROOT, "rawdata", "2025rawhtml")
OUT = os.path.join(ROOT, "cleandata")

BUDGET = 200          # auction budget per team per season
ROSTER_SLOTS = 16     # draft picks per team


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def clean_str(s):
    """Normalize whitespace and curly punctuation."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).replace("’", "'").replace("‘", "'")
    s = s.replace("“", '"').replace("”", '"').replace("–", "-")
    return re.sub(r"\s+", " ", s).strip()


# Same human, different name in Yahoo vs nflverse (or across Yahoo's own years).
# Each was verified by hand against the season's stat line; keys are on the
# left, the surviving canonical key on the right.
PLAYER_ALIASES = {
    "robbiechosen": "robbyanderson",      # legally renamed 2022; nflverse backdates it
    "stevenhauschka": "stephenhauschka",
    "elijahmitchell": "elimitchell",
    "kennygainwell": "kennethgainwell",   # Yahoo itself uses both spellings
    "joshpalmer": "joshuapalmer",
    "chigokonkwo": "chigoziemokonkwo",
    "mikebadgley": "michaelbadgley",
    "marquisebrown": "hollywoodbrown",
}


def player_key(name):
    """Match key for a player across seasons: fold accents, drop Jr/Sr/III."""
    n = unicodedata.normalize("NFKD", clean_str(name)).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", n)
    n = re.sub(r"[^a-z]", "", n)
    return PLAYER_ALIASES.get(n, n)


def team_key(name):
    """Match key for a fantasy team name, tolerant of Yahoo's truncation."""
    n = clean_str(name).lower().rstrip(". ")
    n = re.sub(r"[^a-z0-9 ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


# position may be multi-valued, e.g. 'Taysom Hill (NO - QB,TE)'
PLAYER_RE = re.compile(
    r"^(.*?)\s*\(\s*([A-Za-z]{2,3})\s*-\s*([A-Za-z]{1,3}(?:\s*[,/]\s*[A-Za-z]{1,3})*)\s*\)\s*$")


def split_player(raw):
    """'Saquon Barkley (NYG - RB)' -> ('Saquon Barkley', 'NYG', 'RB')."""
    s = clean_str(raw)
    m = PLAYER_RE.match(s)
    if m:
        return m.group(1).strip(), m.group(2).upper(), m.group(3).upper().replace(" ", "")
    return s, "", ""


# NFL relocations, so a club joins to itself across seasons
NFL_MOVES = {"OAK": "LV", "SD": "LAC", "STL": "LAR"}


# --------------------------------------------------------------------------
# per-season readers  ->  DataFrame[player_raw, price, team_raw, order, pos_col]
# --------------------------------------------------------------------------
def read_generic(fn, sheet, header, cols, **kw):
    df = pd.read_excel(os.path.join(SRC, fn), sheet_name=sheet, header=header)
    out = pd.DataFrame()
    for tgt, src in cols.items():
        out[tgt] = df.iloc[:, src] if isinstance(src, int) else df[src]
    return out


def read_2018():
    """2018 wraps the '(Tm - Pos)' fragment onto a second row; stitch pairs."""
    df = pd.read_excel(os.path.join(SRC, "2018 pbaffl results.xlsx"), header=None)
    rows = []
    for i in range(len(df)):
        if pd.isna(df.iat[i, 0]):
            continue
        name = clean_str(df.iat[i, 1])
        if i + 1 < len(df) and pd.isna(df.iat[i + 1, 0]):
            name = f"{name} {clean_str(df.iat[i + 1, 1])}".strip()
        rows.append({"order": df.iat[i, 0], "player_raw": name,
                     "price": df.iat[i, 2], "team_raw": df.iat[i, 3]})
    return pd.DataFrame(rows)


READERS = {
    2017: lambda: read_generic("2017 draft results.xlsx", "Sheet1", None,
                               {"order": 0, "player_raw": 1, "price": 2, "team_raw": 3}),
    2018: read_2018,
    2019: lambda: read_generic("2019 PBFFL Draft Results.xlsx", "Sheet1", 0,
                               {"order": 0, "player_raw": 1, "price": 2, "team_raw": 3}),
    2020: lambda: read_generic("2020 Results.xlsx", "Sheet1", 0,
                               {"order": 0, "player_raw": 1, "price": 2, "team_raw": 3}),
    2021: lambda: read_generic("2021 Draft Results.xlsx", "Sheet1", 0,
                               {"order": 0, "player_raw": 1, "price": 2, "team_raw": 3}),
    2022: lambda: read_generic("2022 Draft Results.xlsx", "Sheet1", 0,
                               {"order": 0, "player_raw": 1, "price": 2, "team_raw": 3}),
    2023: lambda: read_generic("2023 Draft Results.xlsx", "Sheet1", 0,
                               {"order": 0, "player_raw": 2, "price": 5, "team_raw": 6}),
    # 2024: use 'Slot', not 'Pick #'. 'Pick #' correlates 1.000 with price rank
    # (it is just a rank); 'Slot' correlates 0.77, matching the nomination
    # sequence seen in every other season.
    2024: lambda: read_generic("2024 Results.xlsx", "Sheet1", 0,
                               {"order": 0, "player_raw": 5, "price": 6, "team_raw": 7}),
    2025: lambda: read_generic("2025 results.xlsx", "draft2025", 0,
                               {"order": 0, "player_raw": 2, "price": 1, "team_raw": 4,
                                "pos_given": 3, "price_source": 5}),
}

# Known source defects, fixed explicitly so they are auditable rather than silent.
FIXES = []


def load_season(year):
    df = READERS[year]().copy()
    df["season"] = year
    if "pos_given" not in df:
        df["pos_given"] = ""
    if "price_source" not in df:
        df["price_source"] = "actual"

    df["player_raw"] = df["player_raw"].map(clean_str)
    df["team_raw"] = df["team_raw"].map(clean_str)
    df = df[df["player_raw"] != ""]

    # 2025: my reconstruction emitted a phantom row for an empty draft slot.
    before = len(df)
    df = df[~df["player_raw"].str.contains("--empty--", na=False)]
    if len(df) < before:
        FIXES.append((year, "dropped phantom '--empty--' draft slot", before - len(df)))

    # 2023: one row's team cell was overwritten with the stray text 'u'.
    # Jamie's Team has 15 picks and every other team has 16, so it belongs there.
    if year == 2023:
        bad = df["team_raw"] == "u"
        if bad.any():
            df.loc[bad, "team_raw"] = "Jamie's Team"
            FIXES.append((year, "team cell 'u' -> Jamie's Team (only team short a pick)", int(bad.sum())))

    parsed = df["player_raw"].map(split_player)
    df["player_name"] = [p[0] for p in parsed]
    df["nfl_team"] = [p[1] for p in parsed]
    df["position"] = [p[2] for p in parsed]
    # 2025 carries position in its own column instead of inside the name string
    df["position"] = df.apply(
        lambda r: r["position"] or clean_str(r["pos_given"]).upper(), axis=1)

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df[df["price"].notna()]
    df["price"] = df["price"].astype(int)
    df["nomination_order"] = pd.to_numeric(df["order"], errors="coerce").astype("Int64")
    return df[["season", "nomination_order", "player_name", "nfl_team", "position",
               "price", "team_raw", "price_source"]]


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
picks = pd.concat([load_season(y) for y in sorted(READERS)], ignore_index=True)

# --- 2025 has no NFL team in the workbook; recover it from the parsed HTML ---
extracted = os.path.join(RAW25, "extracted.json")
if os.path.exists(extracted):
    ex = json.load(open(extracted, encoding="utf-8"))
    nfl = {player_key(p["player"]): p["nfl"].upper() for p in ex["draft"] if p.get("nfl")}
    m = (picks["season"] == 2025) & (picks["nfl_team"] == "")
    picks.loc[m, "nfl_team"] = picks.loc[m, "player_name"].map(
        lambda n: nfl.get(player_key(n), ""))
    # The 2025 workbook is my own price-sorted reconstruction, so its order
    # column is a rank. The real nomination sequence is in draftresults.html,
    # laid out as 16 nomination rounds of 12.
    seq = {player_key(p["player"]): (p["round"] - 1) * 12 + p["pick"]
           for p in ex["draft"] if p.get("round") and p.get("pick")}
    m25 = picks["season"] == 2025
    picks.loc[m25, "nomination_order"] = (
        picks.loc[m25, "player_name"]
        .map(lambda n: seq.get(player_key(n))).astype("Int64"))

picks["position_raw"] = picks["position"]
picks["position"] = (picks["position"].str.split(r"[,/]").str[0]
                     .replace({"DST": "DEF", "D": "DEF", "PK": "K"}))
picks["nfl_franchise"] = picks["nfl_team"].replace(NFL_MOVES)

# Defenses are labelled by city in 2017-24 ("Los Angeles") but by nickname in
# 2025 ("Broncos"), and a city can host two clubs. Key them off the NFL team
# abbreviation instead so a defense joins to itself across all nine seasons.
is_def = picks["position"] == "DEF"
picks.loc[is_def, "player_name"] = picks.loc[is_def, "nfl_franchise"] + " DEF"

picks["player_key"] = picks["player_name"].map(player_key)
picks.loc[is_def, "player_key"] = "def_" + picks.loc[is_def, "nfl_franchise"].str.lower()
picks["team_key"] = picks["team_raw"].map(team_key)

# --- franchise identity -----------------------------------------------------
# Yahoo truncates long team names ("Pooky and the Pum..."), so the same
# franchise appears under several spellings. Group names where one is a prefix
# of another. Genuine renames between seasons CANNOT be detected this way and
# are left as separate franchises for a human to merge in franchise_map.csv.
names = sorted(set(picks["team_key"]), key=len, reverse=True)
canon = {}
for n in names:
    for c in canon.values():
        if c.startswith(n):
            canon[n] = c
            break
    else:
        canon[n] = n

longest = {}
for k, c in canon.items():
    full = picks.loc[picks["team_key"] == k, "team_raw"]
    cand = max(full, key=len) if len(full) else k
    if len(cand) > len(longest.get(c, "")):
        longest[c] = cand
picks["franchise"] = picks["team_key"].map(lambda k: longest[canon[k]])

# A manager who renames their team between seasons is invisible to the rule
# above. cleandata/franchise_map.csv lets a human declare those links: fill in
# the `manager` column and re-run. Existing edits are always preserved.
MAP_PATH = os.path.join(OUT, "franchise_map.csv")
seen = picks[["season", "team_raw", "franchise"]].drop_duplicates()
if os.path.exists(MAP_PATH):
    prev = pd.read_csv(MAP_PATH, encoding="utf-8-sig").fillna("")
    prev["season"] = prev["season"].astype(int)
    seen = seen.merge(prev[["season", "team_raw", "manager"]],
                      on=["season", "team_raw"], how="left")
else:
    seen["manager"] = ""
seen["manager"] = seen["manager"].fillna("")
# where a manager is declared, it wins over the auto-detected label
declared = {(r.season, r.team_raw): r.manager.strip()
            for r in seen.itertuples() if str(r.manager).strip()}
if declared:
    picks["franchise"] = [
        declared.get((s, t), f)
        for s, t, f in zip(picks["season"], picks["team_raw"], picks["franchise"])]
    seen["franchise"] = [declared.get((r.season, r.team_raw), r.franchise)
                         for r in seen.itertuples()]

# --- derived analysis columns ----------------------------------------------
picks["price_rank"] = picks.groupby("season")["price"].rank(
    method="first", ascending=False).astype(int)
picks["pos_rank"] = picks.groupby(["season", "position"])["price"].rank(
    method="first", ascending=False).astype(int)
picks["price_share"] = (picks["price"] / BUDGET).round(4)
picks = picks.sort_values(["season", "price_rank"]).reset_index(drop=True)
picks.insert(0, "pick_id", range(1, len(picks) + 1))

DRAFT_COLS = ["pick_id", "season", "price_rank", "price", "price_share", "player_name",
              "player_key", "position", "position_raw", "pos_rank", "nfl_team",
              "nfl_franchise", "franchise", "team_raw", "nomination_order", "price_source"]
draft_picks = picks[DRAFT_COLS]

# --- franchise_seasons ------------------------------------------------------
fs = (picks.groupby(["season", "franchise"])
      .agg(picks_made=("price", "size"), spend=("price", "sum"),
           max_bid=("price", "max"), median_bid=("price", "median"),
           team_raw=("team_raw", "first"))
      .reset_index())
fs["unspent"] = BUDGET - fs["spend"]
fs["pct_on_top3"] = (
    picks.sort_values("price", ascending=False)
    .groupby(["season", "franchise"])["price"].apply(lambda s: s.head(3).sum())
    .reset_index(drop=True).values / BUDGET).round(4)

# --- seasons ----------------------------------------------------------------
seasons = (picks.groupby("season")
           .agg(teams=("franchise", "nunique"), picks=("price", "size"),
                total_spend=("price", "sum"), top_price=("price", "max"))
           .reset_index())
seasons["budget_per_team"] = BUDGET
seasons["roster_slots"] = ROSTER_SLOTS

# --- players ----------------------------------------------------------------
players = (picks.groupby("player_key")
           .agg(player_name=("player_name", lambda s: max(s, key=len)),
                seasons_drafted=("season", "nunique"),
                first_season=("season", "min"), last_season=("season", "max"),
                total_spent=("price", "sum"), avg_price=("price", "mean"),
                max_price=("price", "max"),
                positions=("position", lambda s: "/".join(sorted(set(x for x in s if x)))))
           .reset_index())
players["avg_price"] = players["avg_price"].round(2)
players = players.sort_values("total_spent", ascending=False).reset_index(drop=True)

# --- franchises -------------------------------------------------------------
franchises = (picks.groupby("franchise")
              .agg(seasons_played=("season", "nunique"),
                   first_season=("season", "min"), last_season=("season", "max"),
                   total_spend=("price", "sum"))
              .reset_index().sort_values("franchise"))

# --- alias map (editable by hand) ------------------------------------------
alias = seen.sort_values(["franchise", "season"]).reset_index(drop=True)
alias = alias[["season", "team_raw", "franchise", "manager"]]

# --- league settings + scoring rules (rawdata/scoringrules) -----------------
# The league's own Scoring & Settings page, parsed into tables so the rulebook
# is queryable next to the results instead of living in a saved web page. It is
# also the source of truth for scoring below -- nothing here is hardcoded twice.
RULES_DIR = os.path.join(ROOT, "rawdata", "scoringrules")
rules_html = sorted(glob.glob(os.path.join(RULES_DIR, "*.htm*"))) if os.path.isdir(RULES_DIR) else []
rules_tables, SCORING = {}, {}

if rules_html:
    rsoup = BeautifulSoup(open(rules_html[0], encoding="utf-8", errors="replace").read(), "lxml")
    grids = rsoup.find_all("table")

    def cells(tr):
        out = [re.sub(r"\s+", " ", c.get_text(" ", strip=True))
               for c in tr.find_all(["th", "td"])]
        return [c for c in out if c != ""]

    # first grid: league settings (Setting | Value)
    settings = [{"setting": c[0].rstrip(":"), "value": c[1]}
                for c in map(cells, grids[0].find_all("tr")) if len(c) >= 2]
    settings = [s for s in settings if s["setting"].lower() != "setting"]
    rules_tables["league_settings"] = pd.DataFrame(settings)

    # second grid: scoring, split into sections by its header rows
    SECTIONS = {"offense", "kickers", "defense/special teams"}
    scoring, section = [], ""
    for c in map(cells, grids[1].find_all("tr")):
        if not c:
            continue
        if c[0].lower() in SECTIONS:
            section = c[0]
            continue
        if len(c) < 2:
            continue
        # Yahoo appends "Yahoo Default" to the label and adds a third cell only
        # when the league has overridden the default (e.g. interceptions -2/-1).
        stat = re.sub(r"\s*Yahoo Default\s*$", "", c[0]).strip()
        league_val, default_val = c[1], (c[2] if len(c) > 2 else c[1])
        num = re.search(r"-?\d*\.?\d+", league_val)
        val = float(num.group()) if num else None
        rate = "per point" in league_val.lower()
        scoring.append({
            "category": section, "stat": stat,
            "league_value": league_val, "yahoo_default": default_val,
            "differs_from_default": league_val != default_val,
            "numeric_value": val,
            "basis": "yards_per_point" if rate else "points",
        })
        SCORING[stat.lower()] = val
    rules_tables["scoring_rules"] = pd.DataFrame(scoring)

    # roster construction -- needed for any lineup simulation
    slots = next((s["value"] for s in settings
                  if s["setting"].lower().startswith("roster position")), "")
    if slots:
        counts, order = {}, []
        for slot in [x.strip() for x in slots.split(",") if x.strip()]:
            if slot not in counts:
                counts[slot], _ = 0, order.append(slot)
            counts[slot] += 1
        rules_tables["roster_slots"] = pd.DataFrame([
            {"slot": s, "count": counts[s], "is_starter": s not in ("BN", "IR"),
             "sort_order": i} for i, s in enumerate(order)])

# --- final (end-of-season) fantasy ranks, 2017-2025 -------------------------
# Built from nflverse season stat lines (see fetch_nflverse.py) rather than a
# scraped ranking list, because a published ranking bakes in whoever's scoring
# settings produced it.
#
# nflverse's own `fantasy_points` was verified against the league rulebook and
# already matches it exactly for offence -- passing yds/25, pass TD 4,
# interceptions -2 (this league's override, NOT Yahoo's -1 default), rush and
# receiving yds/10, TDs 6, return TDs 6, 2PT 2, fumbles lost -2. It scores
# receptions at 0, so adding the league's per-reception value yields this
# league's scoring exactly. Kickers are absent from it and scored from the
# rulebook's FG distance bands below.
PPR_RATE = SCORING.get("receptions", 0.5)
FG_BANDS = [("fg_made_0_19", "field goals 0-19 yards", 3),
            ("fg_made_20_29", "field goals 20-29 yards", 3),
            ("fg_made_30_39", "field goals 30-39 yards", 3),
            ("fg_made_40_49", "field goals 40-49 yards", 4),
            ("fg_made_50_59", "field goals 50+ yards", 5),
            ("fg_made_60_", "field goals 50+ yards", 5)]
PAT_VALUE = SCORING.get("point after attempt made", 1)
NFLV = os.path.join(ROOT, "rawdata", "nflverse")


def season_results(year, drafted_keys=frozenset()):
    path = os.path.join(NFLV, f"stats_player_reg_{year}.csv")
    if not os.path.exists(path):
        return None
    d = pd.read_csv(path, low_memory=False)
    # Rank the usual fantasy positions, but never drop someone this league
    # actually drafted -- e.g. Travis Hunter is listed at CB in 2025 but was
    # drafted as a WR, and would otherwise vanish from the value join.
    d["_key"] = d["player_display_name"].map(player_key)
    d = d[d["position"].isin(["QB", "RB", "WR", "TE", "K"])
          | d["_key"].isin(drafted_keys)].copy()
    num = lambda c: pd.to_numeric(d.get(c), errors="coerce").fillna(0)

    # offence: nflverse fantasy_points scores receptions at 0, so add the
    # league's per-reception value to get this league's scoring exactly
    pts = num("fantasy_points") + num("receptions") * PPR_RATE
    # kickers are absent from fantasy_points; score them from the rulebook
    kick = num("pat_made") * PAT_VALUE
    for col, rule, fallback in FG_BANDS:
        kick = kick + num(col) * SCORING.get(rule, fallback)
    d["points"] = pts.where(d["position"] != "K", kick).round(2)

    out = pd.DataFrame({
        "season": year,
        "player_name": d["player_display_name"].map(clean_str),
        "position": d["position"],
        "nfl_team": d.get("recent_team", "").astype(str).str.upper(),
        "games": num("games").astype(int),
        "points": d["points"],
        "points_std": num("fantasy_points").round(2),
        "points_ppr": num("fantasy_points_ppr").round(2),
        "receptions": num("receptions").astype(int),
    })
    out["player_key"] = out["player_name"].map(player_key)
    out["nfl_franchise"] = out["nfl_team"].replace(NFL_MOVES)
    out = out.sort_values("points", ascending=False)
    # Distinct players can share a name -- WR Michael Thomas and DB Michael
    # Thomas both played 2017-2022, likewise QB and CB Lamar Jackson. Keep the
    # higher-scoring one so the fantasy-relevant player wins the join; dedupe
    # before ranking so the ranks themselves stay dense and correct.
    out = out.drop_duplicates(subset=["player_key"], keep="first")
    out["overall_rank"] = range(1, len(out) + 1)
    out["pos_rank"] = out.groupby("position")["points"].rank(
        method="first", ascending=False).astype(int)
    out["points_per_game"] = (out["points"] / out["games"].replace(0, pd.NA)).round(2)
    return out


drafted_by_season = picks.groupby("season")["player_key"].apply(frozenset).to_dict()
fr = [season_results(y, drafted_by_season.get(y, frozenset())) for y in range(2017, 2026)]
final_ranks = pd.concat([f for f in fr if f is not None], ignore_index=True) \
    if any(f is not None for f in fr) else pd.DataFrame()

tables = {"draft_picks": draft_picks, "franchise_seasons": fs, "seasons": seasons,
          "players": players, "franchises": franchises}
if len(final_ranks):
    final_ranks = final_ranks[["season", "overall_rank", "player_name", "player_key",
                               "position", "pos_rank", "nfl_team", "nfl_franchise",
                               "games", "points", "points_per_game", "points_std",
                               "points_ppr", "receptions"]]
    tables["final_ranks"] = final_ranks.reset_index(drop=True)
try:
    adp = pd.read_excel(os.path.join(SRC, "2021 Draft Results.xlsx"), sheet_name="Sheet1 (2)")
    adp = adp.iloc[:, 5:10]
    adp.columns = ["player_name", "position", "nfl_team", "adp_value", "value_diff"]
    adp = adp[adp["player_name"].notna()].copy()
    adp["player_name"] = adp["player_name"].map(clean_str)
    adp["player_key"] = adp["player_name"].map(player_key)
    adp["season"] = 2021
    tables["adp_underdog_2021"] = adp.reset_index(drop=True)
except Exception as e:                                   # noqa: BLE001
    print("  (skipped 2021 ADP sheet:", e, ")")

# --- preseason ADP, 2017-2025 (see fetch_adp.py) ---------------------------
# The market's expectation going INTO each season, so it can be set against
# final_ranks (what happened) and draft_picks (what this league paid).
ADP_DIR = os.path.join(ROOT, "rawdata", "adp")
FORMAT_PREFERENCE = ["half-ppr", "ppr", "standard"]     # league is half-PPR

adp_rows = []
if os.path.isdir(ADP_DIR):
    for year in range(2017, 2027):
        for fmt in FORMAT_PREFERENCE:
            path = os.path.join(ADP_DIR, f"adp_{fmt}_{year}.json")
            if not os.path.exists(path):
                continue
            payload = json.load(open(path, encoding="utf-8"))
            for p in payload.get("players", []):
                adp_rows.append({
                    "season": year, "scoring_format": fmt,
                    "player_name": clean_str(p.get("name")),
                    # FFC labels kickers PK; the rest of the schema uses K
                    "position": {"PK": "K", "DST": "DEF"}.get(
                        clean_str(p.get("position")).upper(),
                        clean_str(p.get("position")).upper()),
                    "nfl_team": clean_str(p.get("team")).upper(),
                    "adp": p.get("adp"), "adp_formatted": p.get("adp_formatted"),
                    "times_drafted": p.get("times_drafted"), "stdev": p.get("stdev"),
                    "high": p.get("high"), "low": p.get("low"), "bye": p.get("bye"),
                    "total_drafts": payload.get("meta", {}).get("total_drafts"),
                })

for r in adp_rows:
    r["source"] = "ffc"

# Current-season Underdog best-ball ADP (see fetch_underdog_adp.py). Underdog
# best ball is half-PPR like this league, so it is the closest live market
# signal available -- but it is best ball, not redraft: 18 rounds, no waivers,
# a FLEX this league lacks, and no kickers or defenses at all.
UD_DIR = os.path.join(ROOT, "rawdata", "underdog")
adp_meta = []
for csv_path in sorted(glob.glob(os.path.join(UD_DIR, "underdog_adp_*.csv"))):
    ud = pd.read_csv(csv_path)
    meta_path = csv_path.replace(".csv", ".meta.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    adp_meta.append(meta)
    for r in ud.to_dict("records"):
        adp_rows.append({
            "season": int(r["season"]), "scoring_format": "half-ppr", "source": "underdog",
            "player_name": clean_str(r["player_name"]),
            "position": clean_str(r["position"]).upper(),
            "nfl_team": clean_str(r["nfl_team"]).upper(),
            "adp": r.get("adp"), "adp_formatted": r.get("pos_adp"),
            "times_drafted": None, "stdev": None,
            "high": None, "low": None, "bye": None, "total_drafts": None,
            "prev_adp": r.get("prev_adp"), "adp_delta": r.get("adp_delta"),
        })

# Sleeper's own ADP, read straight from the projections feed, as a third market.
for path in sorted(glob.glob(os.path.join(PROJ_DIR, "proj_*_*.json"))
                   if os.path.isdir(PROJ_DIR := os.path.join(ROOT, "rawdata", "projections"))
                   else []):
    season = int(re.search(r"_(\d{4})\.json$", path).group(1))
    for row in json.load(open(path, encoding="utf-8")):
        a = (row.get("stats") or {}).get("adp_half_ppr")
        if a is None or float(a) >= 400:
            continue
        nm = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
        adp_rows.append({
            "season": season, "scoring_format": "half-ppr", "source": "sleeper",
            "player_name": clean_str(nm), "position": clean_str(row["position"]).upper(),
            "nfl_team": clean_str(row.get("team")).upper(), "adp": float(a),
            "adp_formatted": None, "times_drafted": None, "stdev": None,
            "high": None, "low": None, "bye": None, "total_drafts": None,
            "prev_adp": None, "adp_delta": None,
        })

if adp_rows:
    adp_all = pd.DataFrame(adp_rows)
    if "prev_adp" not in adp_all:
        adp_all["prev_adp"] = pd.NA
        adp_all["adp_delta"] = pd.NA
    adp_all["player_key"] = adp_all["player_name"].map(player_key)
    adp_all["nfl_franchise"] = adp_all["nfl_team"].replace(NFL_MOVES)
    # Defenses are named three different ways across sources ("Atlanta Defense",
    # "Los Angeles Rams", "DEN DEF"), so normalise them to the same key the
    # draft and results tables use, or nothing joins.
    dm = adp_all["position"] == "DEF"
    adp_all.loc[dm, "player_name"] = adp_all.loc[dm, "nfl_franchise"] + " DEF"
    adp_all.loc[dm, "player_key"] = "def_" + adp_all.loc[dm, "nfl_franchise"].str.lower()
    adp_all = adp_all.sort_values(["season", "scoring_format", "adp"])
    adp_all["format_rank"] = (adp_all.groupby(["season", "scoring_format"])["adp"]
                              .rank(method="first").astype(int))

    # Each format publishes a different, partly-overlapping player set (2022
    # half-PPR lists only 124 players, standard 195). Rank orderings agree
    # across formats at rho 0.94-0.99, so take each player's ADP from the most
    # league-appropriate format that lists them, then rank the merged set.
    # This keeps half-PPR wherever it exists without losing depth.
    # CONSENSUS: average each player's RANK across the independent half-PPR
    # markets, then re-rank. Picking a single primary source inherits its noise
    # wherever it is close: FFC had Breece Hall 0.5 ahead of Kenneth Walker while
    # Underdog had Walker ahead by 14.5 and Sleeper by 12.4 — the board followed
    # the coin-flip. Ranks are averaged rather than raw ADP because the sources
    # have different roster depths (Underdog is 18-round best ball).
    hp = adp_all[adp_all["scoring_format"] == "half-ppr"].copy()
    if hp["source"].nunique() > 1:
        hp["src_rank"] = hp.groupby(["season", "source"])["adp"].rank(method="min")
        cons = (hp.groupby(["season", "player_key"])
                .agg(adp=("src_rank", "mean"), n_src=("src_rank", "size"),
                     player_name=("player_name", "first"),
                     position=("position", "first"), nfl_team=("nfl_team", "first"),
                     nfl_franchise=("nfl_franchise", "first"),
                     prev_adp=("prev_adp", "first"), adp_delta=("adp_delta", "first"))
                .reset_index())
        cons["source"] = "consensus"
        cons["scoring_format"] = "half-ppr"
        for col in ("adp_formatted", "times_drafted", "stdev", "high", "low",
                    "bye", "total_drafts"):
            cons[col] = None
        cons["format_rank"] = cons.groupby("season")["adp"].rank(method="first").astype(int)
        adp_all = pd.concat([adp_all, cons], ignore_index=True)

    # Consensus first, then FFC half-PPR, then Underdog, then other FFC formats.
    #
    # FFC leads for two reasons. (1) Consistency: the ADP->price curve is
    # calibrated on FFC historical ADP, so the current-season input must be FFC
    # too or the curve is fitted on one source and applied to another.
    # (2) Format: FFC is 12-team redraft half-PPR and drafts kickers and
    # defenses; Underdog is best ball with a FLEX, 18 rounds and no K/DEF.
    # Underdog still fills the tail -- it lists 250 players against FFC's 205.
    def _rank(src, fmt):
        if src == "consensus":
            return 0
        if src == "ffc" and fmt == "half-ppr":
            return 1
        if src == "underdog":
            return 2
        if src == "sleeper":
            return 3
        return 4 + FORMAT_PREFERENCE.index(fmt)

    adp_all["_pref"] = [_rank(s, f) for s, f in
                        zip(adp_all["source"], adp_all["scoring_format"])]
    adp_all = adp_all.sort_values(["season", "player_key", "_pref"])
    adp_all["is_primary"] = ~adp_all.duplicated(["season", "player_key"], keep="first")

    prim = adp_all["is_primary"]
    adp_all["preseason_rank"] = pd.NA
    adp_all["pos_rank"] = pd.NA
    adp_all.loc[prim, "preseason_rank"] = (adp_all[prim].groupby("season")["adp"]
                                           .rank(method="first").astype(int))
    adp_all.loc[prim, "pos_rank"] = (adp_all[prim].groupby(["season", "position"])["adp"]
                                     .rank(method="first").astype(int))
    adp_all = adp_all.sort_values(["season", "preseason_rank", "format_rank"])
    tables["preseason_adp"] = adp_all.reset_index(drop=True)[
        ["season", "source", "scoring_format", "is_primary", "preseason_rank",
         "format_rank", "player_name", "player_key", "position", "pos_rank",
         "nfl_team", "nfl_franchise", "adp", "adp_formatted", "prev_adp",
         "adp_delta", "times_drafted", "stdev", "high", "low", "bye", "total_drafts"]]

tables.update(rules_tables)

# --- standings / season outcomes (rawdata/standings/) -----------------------
# The dependent variable. Without this we can measure what a pick returned but
# not what a *strategy* wins. Hand-entered from Yahoo standings pages, one CSV
# per season -- add standings_YYYY.csv and re-run to extend.
STAND_DIR = os.path.join(ROOT, "rawdata", "standings")
stand_files = sorted(glob.glob(os.path.join(STAND_DIR, "standings_*.csv"))) \
    if os.path.isdir(STAND_DIR) else []
if stand_files:
    st = pd.concat([pd.read_csv(f) for f in stand_files], ignore_index=True)
    st["team"] = st["team"].map(clean_str)
    st["team_key"] = st["team"].map(team_key)
    # reuse the same truncation-tolerant resolution the draft data uses
    st["franchise"] = st["team_key"].map(lambda k: longest.get(canon.get(k, k), None))
    st["franchise"] = st["franchise"].fillna(st["team"])
    st["games"] = st["wins"] + st["losses"] + st["ties"]
    st["win_pct"] = (st["wins"] / st["games"].replace(0, pd.NA)).round(3)
    st["ppg"] = (st["points_for"] / st["games"].replace(0, pd.NA)).round(2)
    st["pf_rank"] = st.groupby("season")["points_for"].rank(ascending=False).astype(int)
    st["made_playoffs"] = st["playoff_seed"].notna()
    tables["standings"] = st

# --- current-season projections (see fetch_projections.py) ------------------
# Sleeper publishes raw stat components, so points are computed HERE under this
# league's rulebook rather than taken from someone else's scoring. That matters:
# the -2 interception is a league override, and generic "half-PPR" points use -1.
PROJ_DIR = os.path.join(ROOT, "rawdata", "projections")
proj_meta = []
proj_rows = []
if os.path.isdir(PROJ_DIR):
    for meta_path in sorted(glob.glob(os.path.join(PROJ_DIR, "projections_*.meta.json"))):
        proj_meta.append(json.load(open(meta_path, encoding="utf-8")))
    for path in sorted(glob.glob(os.path.join(PROJ_DIR, "proj_*_*.json"))):
        season = int(re.search(r"_(\d{4})\.json$", path).group(1))
        for row in json.load(open(path, encoding="utf-8")):
            s = row.get("stats", {})
            name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
            pos = row["position"]
            num = lambda k: float(s.get(k) or 0)

            if pos in ("K", "DEF"):
                # Sleeper exposes only the 40-49 / 50+ FG bands and a partial
                # points-allowed breakdown, so its own total is the best
                # available. K+DEF are ~2% of league spend.
                pts = num("pts_half_ppr")
                basis = "sleeper_pts"
            else:
                pts = (num("pass_yd") / 25
                       + num("pass_td") * SCORING.get("passing touchdowns", 4)
                       + num("pass_int") * SCORING.get("interceptions", -2)
                       + num("rush_yd") / 10
                       + num("rush_td") * SCORING.get("rushing touchdowns", 6)
                       + num("rec") * PPR_RATE
                       + num("rec_yd") / 10
                       + num("rec_td") * SCORING.get("receiving touchdowns", 6)
                       + (num("pass_2pt") + num("rush_2pt") + num("rec_2pt")) * 2
                       + num("fum_lost") * SCORING.get("fumbles lost", -2))
                basis = "league_rules"

            proj_rows.append({
                "season": season, "player_name": clean_str(name),
                "player_key": player_key(name), "position": pos,
                "nfl_team": clean_str(row.get("team")).upper(),
                "proj_points": round(pts, 2),
                "proj_points_sleeper_half_ppr": round(num("pts_half_ppr"), 2),
                "scoring_basis": basis,
                # Sleeper's own market, kept as the control for market-vs-model
                # checks: if a value gap also shows up against THIS adp, it is
                # not an artifact of mixing Underdog prices with Sleeper models.
                "sleeper_adp": (float(s["adp_half_ppr"])
                                if s.get("adp_half_ppr") is not None else None),
                "pass_yd": num("pass_yd"), "pass_td": num("pass_td"),
                "pass_int": num("pass_int"), "rush_yd": num("rush_yd"),
                "rush_td": num("rush_td"), "rec": num("rec"),
                "rec_yd": num("rec_yd"), "rec_td": num("rec_td"),
                "fum_lost": num("fum_lost"),
            })

if proj_rows:
    pj = pd.DataFrame(proj_rows)
    # same defense normalisation as preseason_adp -- Sleeper calls them
    # "Los Angeles Rams", FFC "Atlanta Defense", the results tables "LAR DEF"
    dm = pj["position"] == "DEF"
    pj.loc[dm, "nfl_team"] = pj.loc[dm, "nfl_team"].replace(NFL_MOVES)
    pj.loc[dm, "player_name"] = pj.loc[dm, "nfl_team"] + " DEF"
    pj.loc[dm, "player_key"] = "def_" + pj.loc[dm, "nfl_team"].str.lower()
    # a player can appear under multiple positions in the feed; keep the best
    pj = pj.sort_values("proj_points", ascending=False)
    pj = pj.drop_duplicates(subset=["season", "player_key"], keep="first")
    pj["proj_rank"] = pj.groupby("season")["proj_points"].rank(
        method="first", ascending=False).astype(int)
    pj["proj_pos_rank"] = pj.groupby(["season", "position"])["proj_points"].rank(
        method="first", ascending=False).astype(int)
    tables["projections"] = pj.sort_values(
        ["season", "proj_rank"]).reset_index(drop=True)

# --- data freshness ---------------------------------------------------------
# Most of this dataset is historical and never goes stale. Current-season ADP
# does: it moves daily through the summer. This table makes staleness a query
# rather than something to remember -- see the check in CLAUDE.md.
from datetime import datetime as _dt, timezone as _tz  # noqa: E402

# compare in UTC -- fetch_underdog_adp.py stamps fetched_at in UTC, so using a
# local date here can report a negative age
_today = _dt.now(_tz.utc).date()

fresh = [{
    "dataset": "draft_picks / final_ranks / preseason_adp (historical)",
    "source": "Yahoo workbooks + nflverse + FFC",
    "as_of": "2025 season (complete)",
    "fetched_on": "", "stale_after_days": None,
    "refresh_command": "python fetch_nflverse.py && python fetch_adp.py",
    "note": "historical; only needs refreshing once a new season completes",
}]
for meta in adp_meta:
    fetched = meta.get("fetched_at", "")
    age = None
    if fetched:
        try:
            age = (_today - _dt.strptime(fetched, "%Y-%m-%d").date()).days
        except ValueError:
            age = None
    fresh.append({
        "dataset": f"preseason_adp (season {meta.get('season')}, underdog)",
        "source": meta.get("source", "underdog"),
        "as_of": meta.get("source_updated") or "",
        "fetched_on": fetched, "stale_after_days": 3,
        "refresh_command": "python fetch_underdog_adp.py && python build_clean_data.py",
        "note": f"{meta.get('rows')} players; moves daily in preseason"
                + (f"; {age}d old at last build" if age is not None else ""),
    })
for meta in proj_meta:
    fetched = meta.get("fetched_at", "")
    age = None
    if fetched:
        try:
            age = (_today - _dt.strptime(fetched, "%Y-%m-%d").date()).days
        except ValueError:
            age = None
    fresh.append({
        "dataset": f"projections (season {meta.get('season')}, sleeper)",
        "source": meta.get("source", "sleeper"), "as_of": "",
        "fetched_on": fetched, "stale_after_days": 3,
        "refresh_command": "python fetch_projections.py && python build_clean_data.py",
        "note": f"{sum((meta.get('counts') or {}).values())} players; "
                "revised through preseason as camps and injuries land"
                + (f"; {age}d old at last build" if age is not None else ""),
    })
tables["data_freshness"] = pd.DataFrame(fresh)

# --- 2025 preseason rankings ------------------------------------------------
top = os.path.join(RAW25, "top2025.txt")
if os.path.exists(top):
    rows = []
    for line in open(top, encoding="utf-8"):
        m = re.match(r"\s*(\d+)\.\s*(.+?),\s*([A-Za-z]+)\s*--\s*([A-Za-z]+)(\d+)", line)
        if m:
            rows.append({"season": 2025, "overall_rank": int(m.group(1)),
                         "player_name": clean_str(m.group(2)),
                         "player_key": player_key(m.group(2)),
                         "nfl_team": m.group(3).upper(), "position": m.group(4).upper(),
                         "pos_rank": int(m.group(5))})
    tables["preseason_ranks"] = pd.DataFrame(rows)

# --------------------------------------------------------------------------
# write outputs
# --------------------------------------------------------------------------
os.makedirs(os.path.join(OUT, "csv"), exist_ok=True)
os.makedirs(os.path.join(OUT, "parquet"), exist_ok=True)

db_path = os.path.join(OUT, "fantasy.db")
if os.path.exists(db_path):
    os.remove(db_path)
con = sqlite3.connect(db_path)
for name, df in tables.items():
    df.to_sql(name, con, index=False)
    df.to_csv(os.path.join(OUT, "csv", f"{name}.csv"), index=False, encoding="utf-8-sig")
    try:
        df.to_parquet(os.path.join(OUT, "parquet", f"{name}.parquet"), index=False)
    except Exception:                                    # noqa: BLE001
        pass

con.executescript("""
CREATE INDEX idx_picks_season   ON draft_picks(season);
CREATE INDEX idx_picks_player   ON draft_picks(player_key);
CREATE INDEX idx_picks_pos      ON draft_picks(season, position);
CREATE INDEX idx_picks_fran     ON draft_picks(season, franchise);
CREATE VIEW v_position_spend AS
  SELECT season, position, COUNT(*) n, SUM(price) spend,
         ROUND(AVG(price), 2) avg_price,
         ROUND(100.0 * SUM(price) / (SELECT SUM(price) FROM draft_picks p2
                                     WHERE p2.season = p.season), 1) pct_of_league
  FROM draft_picks p GROUP BY season, position;
CREATE VIEW v_top_buys AS
  SELECT season, price_rank, price, player_name, position, franchise
  FROM draft_picks WHERE price_rank <= 10 ORDER BY season, price_rank;
""")
if "final_ranks" in tables:
    con.executescript("""
    CREATE INDEX idx_final_season ON final_ranks(season);
    CREATE INDEX idx_final_player ON final_ranks(season, player_key);
    -- what each draft pick actually returned: price paid vs where they finished
    CREATE VIEW v_draft_value AS
      SELECT d.season, d.franchise, d.player_name, d.position, d.price, d.price_rank,
             f.overall_rank AS final_rank, f.pos_rank AS final_pos_rank,
             f.points, f.games,
             d.price_rank - f.overall_rank AS rank_delta
      FROM draft_picks d
      LEFT JOIN final_ranks f
        ON f.season = d.season AND f.player_key = d.player_key;
    """)
if "standings" in tables:
    con.executescript("""
    CREATE INDEX idx_standings ON standings(season, franchise);
    -- draft spend shape vs how the season actually went
    CREATE VIEW v_season_outcome AS
      SELECT s.season, s.franchise, s.rank, s.wins, s.losses, s.points_for,
             s.pf_rank, s.made_playoffs, s.finish, s.moves, s.waiver_budget_left,
             f.spend, f.picks_made, f.max_bid, f.median_bid, f.pct_on_top3
      FROM standings s
      LEFT JOIN franchise_seasons f
        ON f.season = s.season AND f.franchise = s.franchise;
    """)

if "preseason_adp" in tables:
    con.executescript("""
    CREATE INDEX idx_adp_season ON preseason_adp(season, is_primary);
    CREATE INDEX idx_adp_player ON preseason_adp(season, player_key);
    -- one row per player per season, deduped across scoring formats
    CREATE VIEW v_preseason AS
      SELECT season, preseason_rank AS overall_rank, player_name, player_key,
             position, pos_rank, nfl_team, adp, prev_adp, adp_delta,
             stdev, times_drafted, source, scoring_format
      FROM preseason_adp WHERE is_primary = 1;
    -- expectation vs outcome vs what this league actually paid
    CREATE VIEW v_player_season AS
      SELECT COALESCE(p.season, f.season)         AS season,
             COALESCE(p.player_key, f.player_key) AS player_key,
             COALESCE(p.player_name, f.player_name) AS player_name,
             COALESCE(p.position, f.position)     AS position,
             p.overall_rank AS preseason_rank, p.adp,
             f.overall_rank AS final_rank, f.points, f.games,
             p.overall_rank - f.overall_rank AS beat_expectation,
             d.price, d.price_rank, d.franchise
      FROM v_preseason p
      FULL OUTER JOIN final_ranks f
        ON f.season = p.season AND f.player_key = p.player_key
      LEFT JOIN draft_picks d
        ON d.season = COALESCE(p.season, f.season)
       AND d.player_key = COALESCE(p.player_key, f.player_key);
    """)
con.commit()
alias.to_csv(os.path.join(OUT, "franchise_map.csv"), index=False, encoding="utf-8-sig")

# --------------------------------------------------------------------------
# validation report
# --------------------------------------------------------------------------
print(f"\nwrote {db_path}")
print(f"tables: {', '.join(f'{k}({len(v)})' for k, v in tables.items())}\n")

if FIXES:
    print("source defects repaired:")
    for yr, what, n in FIXES:
        print(f"  {yr}  {what}  (n={n})")

print(f"\n{'season':>7} {'teams':>6} {'picks':>6} {'spend':>7} {'maxTeam':>8} "
      f"{'overBudget':>11} {'shortRoster':>12}")
ok = True
for _, s in seasons.iterrows():
    sub = fs[fs["season"] == s["season"]]
    over = sub[sub["spend"] > BUDGET]
    short = sub[sub["picks_made"] != ROSTER_SLOTS]
    ok &= over.empty
    print(f"{int(s['season']):>7} {int(s['teams']):>6} {int(s['picks']):>6} "
          f"{int(s['total_spend']):>7} {int(sub['spend'].max()):>8} "
          f"{len(over):>11} {len(short):>12}")

dupes = draft_picks.groupby(["season", "player_key"]).size()
dupes = dupes[dupes > 1]
print(f"\nduplicate player-within-season rows: {len(dupes)}")
print(f"rows missing position: {(draft_picks['position'] == '').sum()}   "
      f"missing nfl_team: {(draft_picks['nfl_team'] == '').sum()}")
print(f"franchise labels: {len(franchises)}  (review cleandata/franchise_map.csv)")

if "final_ranks" in tables:
    fr_t = tables["final_ranks"]
    cov = (draft_picks.merge(fr_t[["season", "player_key"]], on=["season", "player_key"],
                             how="left", indicator=True))
    off = cov[cov["position"].isin(["QB", "RB", "WR", "TE", "K"])]
    hit = (off["_merge"] == "both").mean()
    print(f"\nfinal_ranks: {len(fr_t)} rows, {fr_t['season'].nunique()} seasons "
          f"({fr_t['season'].min()}-{fr_t['season'].max()})")
    print(f"draft picks matched to a final rank: {hit:.1%} of QB/RB/WR/TE/K picks "
          f"({(off['_merge'] == 'both').sum()}/{len(off)})")
    print("  (unmatched = drafted but never played a snap that season; "
          "DEF has no nflverse equivalent)")

if "preseason_adp" in tables:
    pa = tables["preseason_adp"]
    prim = pa[pa["is_primary"]]
    pk = set(zip(prim["season"], prim["player_key"]))
    skill = draft_picks[~draft_picks["position"].isin(["DEF", "K"])]
    flags = [(s, k) in pk for s, k in zip(skill["season"], skill["player_key"])]
    hit = sum(flags) / len(flags) if flags else 0.0
    fmts = (prim.groupby("season")["scoring_format"]
            .agg(lambda s: "+".join(sorted(set(s)))).to_dict())
    print(f"\npreseason_adp: {len(pa)} rows across 3 formats; "
          f"{len(prim)} primary ({prim['season'].nunique()} seasons)")
    print(f"draft picks matched to a preseason rank: {hit:.1%} of QB/RB/WR/TE picks")
    for s in sorted(fmts):
        n = (prim["season"] == s).sum()
        print(f"    {s}  {n:>3} players  [{fmts[s]}]")

if "scoring_rules" in tables:
    sr = tables["scoring_rules"]
    custom = sr[sr["differs_from_default"]]
    print(f"\nscoring_rules: {len(sr)} rules parsed from "
          f"{os.path.basename(rules_html[0])[:40]}...")
    print(f"  receptions = {PPR_RATE} pts  ->  half-PPR "
          f"({'matches' if PPR_RATE == 0.5 else 'DOES NOT match'} the inferred rate)")
    if len(custom):
        print("  league overrides of Yahoo defaults:")
        for r in custom.itertuples():
            print(f"    {r.stat}: {r.league_value} (default {r.yahoo_default})")
    if "roster_slots" in tables:
        rs = tables["roster_slots"]
        starters = rs[rs["is_starter"]]
        print(f"  roster: {starters['count'].sum()} starters "
              f"({', '.join(f'{r.count}x{r.slot}' for r in starters.itertuples())})"
              f" + {rs[~rs['is_starter']]['count'].sum()} bench/IR")

print("\nbudget check:", "PASS - no team over $200" if ok else "FAIL")
