"""Download Perennial Push for Penultimacy (ESPN league 623238770).

The second league on the dashboard. ESPN, 12 teams, 18-round SNAKE draft, full PPR,
and a SUPERFLEX slot (lineup slot 7) -- so unlike Underdog its ADP and its QB
valuations are NOT comparable to PBAFFL. Keep the two leagues' conclusions apart.

WHY THIS IS A SCRIPT AND NOT A BROWSER SESSION. The first pull of this data was done
by hand through a logged-in browser, which left the numbers but not the method: the
next refresh would have meant rediscovering the endpoints, the filter header and the
batch size from scratch. That is the failure this file exists to prevent.

TWO ENDPOINTS, NOT ONE. Current and future seasons are public:
    /apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{id}
Prior seasons 401 on that path and must come from leagueHistory, which returns a
one-element ARRAY rather than an object:
    /apis/v3/games/ffl/leagueHistory/{id}?seasonId={season}
leagueHistory also 404s while unauthenticated, which reads like "wrong URL" and is
really "no session" -- see AUTH.

AUTH. Historical seasons need espn_credentials.json (gitignored, same pattern as
yahoo_credentials.json):
    {"espn_s2": "<cookie>", "SWID": "{<cookie>}"}
Both cookies come from a browser logged in to fantasy.espn.com (DevTools >
Application > Cookies > .espn.com). Without them, 2025-2026 still work and the
historical seasons are skipped with a warning rather than failing the run.

PLAYER NAMES AND POINTS. Draft picks carry only playerId. Names, positions and both
actual and projected points come from view=kona_player_info with an x-fantasy-filter
header, in batches -- 216 ids in one request returns 400, ~40 is reliable:
    {"players": {"filterIds": {"value": [id, ...]}}}
appliedTotal is already scored under THIS league's rules, which is the whole reason
to pull it from the league endpoint instead of a generic projection source.
statSourceId 0 = actual, 1 = projected; statSplitTypeId 0 = season total.

WRITES to rawdata/espn/:
  draft_{season}.csv            immutable once a season is drafted; never re-fetched
  teams_{season}.csv            standings and finish
  board_{season}__YYYY-MM-DD.csv  dated, because ADP and projections move daily
  *.meta.json                   what was fetched, when, and from which endpoint

Run:  python fetch_espn_league.py                 current board + any missing history
      python fetch_espn_league.py --seasons 2025  just that season's draft
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

LEAGUE_ID = "623238770"
CURRENT_SEASON = 2026
HISTORY_SEASONS = [2021, 2022, 2023, 2024, 2025]
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(ROOT, "rawdata", "espn")
CREDS = os.path.join(ROOT, "espn_credentials.json")
BATCH = 40                      # 216 ids in one call returns 400; 40 is safe
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
PRO = {0: "FA", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN",
       8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR",
       15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI",
       22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB", 28: "WSH",
       29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU"}
# ESPN lineup slot ids that matter here. 7 is OP/superflex -- the single most
# consequential fact about this league, and invisible unless you decode the slots.
SLOTS = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 7: "SUPERFLEX", 16: "DEF", 17: "K",
         20: "BENCH", 21: "IR", 23: "FLEX"}


def cookies():
    """espn_s2 + SWID if present. Absent is fine; history is then skipped."""
    try:
        with open(CREDS, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("espn_s2") and c.get("SWID"):
            return "espn_s2=%s; SWID=%s" % (c["espn_s2"], c["SWID"])
    except FileNotFoundError:
        return None
    except Exception as e:                                       # noqa: BLE001
        print("  WARNING could not read espn_credentials.json: %r" % e)
    return None


COOKIE = cookies()


def get(url, fantasy_filter=None):
    """One GET. Returns parsed JSON, unwrapping leagueHistory's single-element list."""
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if COOKIE:
        headers["Cookie"] = COOKIE
    if fantasy_filter:
        headers["x-fantasy-filter"] = json.dumps(fantasy_filter)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    return data[0] if isinstance(data, list) and data else data


def league_url(season, views):
    v = "&".join("view=" + x for x in views)
    if season >= CURRENT_SEASON or season == max(HISTORY_SEASONS):
        return "%s/seasons/%d/segments/0/leagues/%s?%s" % (BASE, season, LEAGUE_ID, v)
    return "%s/leagueHistory/%s?seasonId=%d&%s" % (BASE, LEAGUE_ID, season, v)


def player_info(season, ids):
    """id -> name/pos/team/actual/projected, scored under this league's rules."""
    out = {}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        url = league_url(season, ["kona_player_info"])
        try:
            j = get(url, {"players": {"filterIds": {"value": chunk}}})
        except urllib.error.HTTPError as e:
            print("  WARNING player batch at %d returned %s" % (i, e.code))
            continue
        for p in j.get("players", []):
            pl = p.get("player") or {}
            stats = pl.get("stats") or []
            pick = lambda src: next(                             # noqa: E731
                (s for s in stats if s.get("statSourceId") == src
                 and s.get("statSplitTypeId") == 0 and s.get("seasonId") == season),
                None)
            act, prj = pick(0), pick(1)
            games = (act or {}).get("stats", {}).get("210")
            out[p["id"]] = {
                "name": pl.get("fullName", ""),
                "position": POS.get(pl.get("defaultPositionId"), "?"),
                "nfl_team": PRO.get(pl.get("proTeamId"), pl.get("proTeamId")),
                "actual": round(act["appliedTotal"], 1) if act and act.get("appliedTotal") is not None else None,
                "projected": round(prj["appliedTotal"], 1) if prj and prj.get("appliedTotal") is not None else None,
                "games": games,
            }
        time.sleep(0.15)                        # be polite; this is someone's API
    return out


def write(path, rows, meta):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.splitext(path)[0] + ".meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print("  %-46s %4d rows" % (os.path.relpath(path, ROOT), len(rows)))


def stamp():
    return time.strftime("%Y-%m-%d")


def fetch_season(season):
    """Draft + teams for one season. Historical drafts never change; skip if present."""
    draft_path = os.path.join(DEST, "draft_%d.csv" % season)
    if os.path.exists(draft_path) and season < CURRENT_SEASON:
        print("  %d draft already present, skipping" % season)
        return
    try:
        j = get(league_url(season, ["mSettings", "mTeam", "mDraftDetail"]))
    except urllib.error.HTTPError as e:
        why = ("no espn_credentials.json, so historical seasons are not visible"
               if e.code in (401, 404) and not COOKIE else "HTTP %s" % e.code)
        print("  %d SKIPPED (%s)" % (season, why))
        return

    settings = j.get("settings") or {}
    slots = (settings.get("rosterSettings") or {}).get("lineupSlotCounts") or {}
    superflex = int(slots.get("7", 0)) > 0
    members = {m["id"]: ("%s %s" % (m.get("firstName", ""), m.get("lastName", ""))).strip()
               for m in j.get("members", [])}
    teams = []
    for t in j.get("teams", []):
        rec = (t.get("record") or {}).get("overall") or {}
        teams.append({
            "season": season, "team_id": t.get("id"),
            "name": ("%s %s" % (t.get("location", ""), t.get("nickname", ""))).strip() or t.get("name", ""),
            "abbrev": t.get("abbrev", ""),
            "owner": " & ".join(filter(None, (members.get(o) for o in t.get("owners") or []))),
            "wins": rec.get("wins"), "losses": rec.get("losses"), "ties": rec.get("ties"),
            "points_for": round(rec.get("pointsFor", 0), 2),
            "points_against": round(rec.get("pointsAgainst", 0), 2),
            "seed": t.get("playoffSeed"), "finish": t.get("rankCalculatedFinal"),
        })
    base_meta = {
        "league_id": LEAGUE_ID, "season": season, "fetched_at": stamp(),
        "endpoint": league_url(season, ["mSettings", "mTeam", "mDraftDetail"]),
        "teams": settings.get("size"), "superflex": superflex,
        "draft_type": (settings.get("draftSettings") or {}).get("type"),
        "authenticated": bool(COOKIE),
    }
    write(os.path.join(DEST, "teams_%d.csv" % season), teams, base_meta)

    picks = ((j.get("draftDetail") or {}).get("picks")) or []
    if not picks:
        print("  %d has no draft picks yet" % season)
        return
    if len(picks) < 100:
        raise SystemExit("%d returned only %d picks - league shape changed?" % (season, len(picks)))
    info = player_info(season, sorted({p["playerId"] for p in picks}))
    rows = []
    for p in sorted(picks, key=lambda x: x["overallPickNumber"]):
        d = info.get(p["playerId"], {})
        rows.append({
            "season": season, "overall": p["overallPickNumber"], "round": p["roundId"],
            "pick": p["roundPickNumber"], "team_id": p["teamId"],
            "player_id": p["playerId"], "keeper": int(bool(p.get("keeper"))),
            "player_name": d.get("name", ""), "position": d.get("position", "?"),
            "nfl_team": d.get("nfl_team", ""), "actual": d.get("actual"),
            "projected": d.get("projected"), "games": d.get("games"),
        })
    resolved = sum(1 for r in rows if r["player_name"])
    write(draft_path, rows, dict(base_meta, picks=len(rows), names_resolved=resolved))
    if resolved < len(rows):
        print("  WARNING %d of %d player names unresolved" % (len(rows) - resolved, len(rows)))


# The 2026 pool the dashboard drafts from. ESPN's board is a ONE-QB list, so its top 300
# carries only ~32 quarterbacks and stops short of QBs this superflex room actually
# drafts (Penix, Cousins and Shedeur Sanders all sat past #427 on 2026-09-05). So the
# pool is the top POOL_TOP by ESPN's order plus the first POOL_QB quarterbacks in that
# order. Not every QB: ESPN lists 83, down to third-stringers at rank ~1400, and this
# room has never drafted more than 35 (2023-25: 33, 35, 33). Jamie asked for the list to
# run ~50 deeper than the 248 it had, and to include Penix and Cousins (2026-09-05).
POOL_TOP = 300
POOL_QB = 45
PPP_BOARD = os.path.join(ROOT, "rawdata", "ppp", "board2026.psv")
PPP_SNAPS = os.path.join(ROOT, "rawdata", "ppp", "snapshots")


def write_ppp_board(rows, season):
    """Write the pool build_ppp_data.py reads, in its existing PSV schema, plus a dated snapshot.

    Same file, same columns (pid|name|pos|proTeam|espnRank|adp|own|proj) -- the build
    path does not change. Backlog item 1 (retire rawdata/ppp/ for rawdata/espn/) is a
    separate job; this only makes the frozen snapshot refreshable.
    """
    qbs = [r["player_id"] for r in rows if r["position"] == "QB"][:POOL_QB]
    pool = [r for i, r in enumerate(rows) if i < POOL_TOP or r["player_id"] in qbs]
    fmt = lambda v: "" if v is None else v                          # noqa: E731
    # HEADERLESS, like the 2026-09-01 original: build_ppp_vor_board.py int()s column 5 of
    # every line, and build_ppp_data.py's rows() only tolerates a header, never needs one.
    lines = [
        "|".join(str(fmt(x)) for x in (r["player_id"], r["player_name"], r["position"],
                                       r["nfl_team"], r["espn_ppr_rank"], r["adp"],
                                       r["percent_owned"], r["projected"]))
        for r in pool]
    os.makedirs(PPP_SNAPS, exist_ok=True)
    for path in (PPP_BOARD, os.path.join(PPP_SNAPS, "espn_board_%s.psv" % stamp())):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    nqb = sum(1 for r in pool if r["position"] == "QB")
    print("  %-46s %4d rows  (top %d + first %d QBs: %d QBs in pool)"
          % (os.path.relpath(PPP_BOARD, ROOT), len(pool), POOL_TOP, POOL_QB, nqb))


def fetch_board(season=CURRENT_SEASON, want=600):
    """Current draft board: ESPN's PPR rank, ADP, ownership, projected points.

    Dated, because these move every day. NOTE the rank is ESPN's ONE-QB PPR order --
    it is not a superflex board and should not be used as one. `want` runs well past
    the pool so that write_ppp_board() can keep every quarterback ESPN lists.
    """
    rows, seen = [], set()
    for off in range(0, want, 60):
        f = {"players": {"limit": 60, "offset": off,
                         "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "PPR"}}}
        try:
            j = get(league_url(season, ["kona_player_info"]), f)
        except urllib.error.HTTPError as e:
            print("  WARNING board page at offset %d returned %s" % (off, e.code))
            break
        page = j.get("players", [])
        if not page:
            break
        for p in page:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            pl = p.get("player") or {}
            own = pl.get("ownership") or {}
            prj = next((s for s in pl.get("stats") or []
                        if s.get("statSourceId") == 1 and s.get("statSplitTypeId") == 0
                        and s.get("seasonId") == season), None)
            dr = (pl.get("draftRanksByRankType") or {}).get("PPR") or {}
            rows.append({
                "season": season, "player_id": p["id"], "player_name": pl.get("fullName", ""),
                "position": POS.get(pl.get("defaultPositionId"), "?"),
                "nfl_team": PRO.get(pl.get("proTeamId"), pl.get("proTeamId")),
                "espn_ppr_rank": dr.get("rank"),
                "adp": round(own["averageDraftPosition"], 1) if own.get("averageDraftPosition") is not None else None,
                "percent_owned": round(own["percentOwned"], 1) if own.get("percentOwned") is not None else None,
                "projected": round(prj["appliedTotal"], 1) if prj and prj.get("appliedTotal") is not None else None,
            })
        time.sleep(0.15)
    if len(rows) < 150:
        raise SystemExit("board returned only %d players - filter or endpoint changed?" % len(rows))
    write(os.path.join(DEST, "board_%d__%s.csv" % (season, stamp())), rows, {
        "league_id": LEAGUE_ID, "season": season, "fetched_at": stamp(),
        "rows": len(rows), "rank_basis": "ESPN PPR draft rank (ONE-QB, not superflex)",
        "note": "ADP and projections move daily; snapshots are dated on purpose",
        "authenticated": bool(COOKIE),
    })
    write_ppp_board(rows, season)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seasons", nargs="*", type=int, help="seasons to fetch (default: all)")
    ap.add_argument("--board-only", action="store_true")
    ap.add_argument("--want", type=int, default=600,
                    help="how deep to page ESPN's board (default 600; the pool keeps the top "
                         "%d plus the first %d QBs)" % (POOL_TOP, POOL_QB))
    a = ap.parse_args()
    os.makedirs(DEST, exist_ok=True)
    print("ESPN league %s%s" % (LEAGUE_ID, "" if COOKIE else "   (no credentials: 2021-2024 will be skipped)"))
    if not a.board_only:
        for s in (a.seasons or HISTORY_SEASONS):
            fetch_season(s)
    fetch_board(want=a.want)
    print("done")
