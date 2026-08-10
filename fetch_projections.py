"""Download current-season player projections from Sleeper.

Why Sleeper: it returns RAW STAT COMPONENTS (pass_yd, pass_int, rec, rush_td...)
rather than someone else's fantasy points. That matters because this league is
half-PPR with a non-default -2 per interception, so points have to be computed
from components to be correct. It is also a real JSON API -- no scraping, and
it refreshes cleanly.

Checked and rejected:
  FantasyPros   302-redirects automated requests
  FantasyData   served 2025 numbers when asked for 2024 (caught by sanity check)
  nflverse      historical stats only, no projections

Covers QB/RB/WR/TE/K/DEF. Note K exposes only the 40-49 and 50+ FG bands and
DEF only a partial points-allowed breakdown, so those two are scored with
Sleeper's own points in the build; the other four are computed from components
under the league rulebook. K+DEF are ~2% of league spend.

Also note `gp` is a constant 18.0 for every player -- it is a placeholder, NOT
an availability projection. Do not use it for injury modelling.

Writes rawdata/projections/ : one JSON per position plus a .meta.json.

Run:  python fetch_projections.py        (always re-fetches; that is the point)
"""
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

SEASON = 2026                      # bump each year
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]
BASE = "https://api.sleeper.app/projections/nfl"
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "projections")

os.makedirs(DEST, exist_ok=True)
counts, failed = {}, []
for pos in POSITIONS:
    url = (f"{BASE}/{SEASON}?season_type=regular&position[]={pos}"
           f"&order_by=pts_half_ppr")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            payload = json.load(r)
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"unexpected payload for {pos}")
        # keep only what we need; the raw feed is mostly ADP variants
        slim = []
        for row in payload:
            p = row.get("player") or {}
            stats = {k: v for k, v in (row.get("stats") or {}).items()
                     if not k.startswith("adp_")}
            if not stats:
                continue
            slim.append({
                "player_id": row.get("player_id"),
                "first_name": p.get("first_name"), "last_name": p.get("last_name"),
                "position": pos, "team": row.get("team"),
                "stats": stats,
            })
        with open(os.path.join(DEST, f"proj_{pos}_{SEASON}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(slim, f)
        counts[pos] = len(slim)
        print(f"  {pos:<4} {len(slim):>4} players")
        time.sleep(0.4)                       # be polite
    except Exception as e:                    # noqa: BLE001
        print(f"  {pos:<4} FAILED: {e}")
        failed.append(pos)

meta = {
    "season": SEASON, "source": "sleeper api (api.sleeper.app/projections/nfl)",
    "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "counts": counts, "scoring": "raw stat components; points computed in build",
    "note": "gp is a constant placeholder, not an availability projection; "
            "K/DEF scored with Sleeper's own points (partial stat breakdown)",
}
with open(os.path.join(DEST, f"projections_{SEASON}.meta.json"), "w",
          encoding="utf-8") as f:
    json.dump(meta, f, indent=1)

print(f"\n{sum(counts.values())} projections -> {DEST}")
print(f"fetched {meta['fetched_at']}")
if failed:
    raise SystemExit(f"failed positions: {failed}")
