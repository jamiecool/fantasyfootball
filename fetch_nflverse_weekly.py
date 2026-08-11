"""Download nflverse WEEK-BY-WEEK player stats for 2017-2025.

Same source and the same 140-odd stat columns as fetch_nflverse.py, but one row
per player per game instead of one per player per season. That buys three things
the season totals cannot give:

  * a game log for any player
  * any week range -- "weeks 15-17 only" is the fantasy playoffs, and a player's
    record there is a different question from his season total
  * week-level variance, which is what a head-to-head league actually pays for.
    Two players with identical season totals are not equally valuable if one
    delivers it in even weekly doses and the other in three explosions.

Weekly files carry both REG and POST rows (weeks 1-22). build_clean_data.py
keeps regular season only -- fantasy seasons end at week 18.

Run:  python fetch_nflverse_weekly.py     (re-run is safe; skips files present)
"""
import os
import sys
import urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "nflverse")
BASE = "https://github.com/nflverse/nflverse-data/releases/download/stats_player"
SEASONS = range(2017, 2026)
MIN_BYTES = 3_000_000          # a real weekly file is 6-9 MB; anything less is a stub

os.makedirs(DEST, exist_ok=True)
failed = []
for year in SEASONS:
    fn = f"stats_player_week_{year}.csv"
    out = os.path.join(DEST, fn)
    if os.path.exists(out) and os.path.getsize(out) > MIN_BYTES:
        print(f"  {year}  already present ({os.path.getsize(out):,} bytes)")
        continue
    url = f"{BASE}/{fn}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            data = r.read()
        if data.strip() == b"Not Found" or len(data) < MIN_BYTES:
            raise ValueError(f"unexpected payload ({len(data)} bytes)")
        with open(out, "wb") as f:
            f.write(data)
        print(f"  {year}  downloaded {len(data):,} bytes")
    except Exception as e:                                   # noqa: BLE001
        print(f"  {year}  FAILED: {e}")
        failed.append(year)

print(f"\n{len(list(SEASONS)) - len(failed)}/{len(list(SEASONS))} seasons in {DEST}")
if failed:
    print("failed:", failed)
    sys.exit(1)
