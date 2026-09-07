"""Download nflverse TEAM-level weekly stats (2017-2025) and the games file.

Why a third nflverse fetcher: a defence/special-teams unit is not a player, so it
has no row in stats_player_week_*.csv. Its fantasy line is a team-week fact --
sacks, takeaways, defensive and return touchdowns, safeties, blocked kicks, plus
two things only a game can tell you: points allowed (from games.csv) and yards
allowed (the opponent's net offence from ITS team-week row). build_clean_data.py
turns these into D/ST game logs in player_weeks so the NFL stats tab, the player
card and the team card stop pretending the position does not exist.

  stats_team_week_{year}.csv   one row per team per game, same 130-odd columns as
                               the player file aggregated to the team
  games.csv                    every NFL game 1999-, with scores -- the same file
                               fetch_vegas.py mirrors under rawdata/vegas/, kept
                               here too so an offline build never depends on a
                               live-feed stage having run

Both are mirrors that only grow, so this skips anything already present, like
the other nflverse fetchers. Gitignored (see .gitignore); build_all.py runs this
when the 2025 team file is missing.

Run:  python fetch_nflverse_team.py     (re-run is safe; skips files present)
"""
import os
import sys
import urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "nflverse")
TEAM_BASE = "https://github.com/nflverse/nflverse-data/releases/download/stats_team"
GAMES_URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
SEASONS = range(2017, 2026)
MIN_TEAM_BYTES = 100_000       # a real team-week file is ~230KB; anything less is a stub
MIN_GAMES_BYTES = 1_000_000    # games.csv is ~2.1MB


def fetch(url, out, min_bytes):
    if os.path.exists(out) and os.path.getsize(out) > min_bytes:
        print(f"  {os.path.basename(out):28} already present ({os.path.getsize(out):,} bytes)")
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        if data.strip() == b"Not Found" or len(data) < min_bytes:
            raise ValueError(f"unexpected payload ({len(data)} bytes)")
        with open(out, "wb") as f:
            f.write(data)
        print(f"  {os.path.basename(out):28} downloaded {len(data):,} bytes")
        return True
    except Exception as e:                                   # noqa: BLE001
        print(f"  {os.path.basename(out):28} FAILED: {e}")
        return False


os.makedirs(DEST, exist_ok=True)
ok = [fetch(f"{TEAM_BASE}/stats_team_week_{y}.csv",
            os.path.join(DEST, f"stats_team_week_{y}.csv"), MIN_TEAM_BYTES) for y in SEASONS]
ok.append(fetch(GAMES_URL, os.path.join(DEST, "games.csv"), MIN_GAMES_BYTES))
print(f"\n{sum(ok)}/{len(ok)} files in {DEST}")
if not all(ok):
    sys.exit(1)
