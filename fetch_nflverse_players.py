"""Player biography: height, weight, birth date, college, draft slot.

Joins on gsis_id, not on a name. player_weeks already carries nflverse's
player_id, so this is an ID join and none of the name-collision problems that
have bitten this project twice -- the two Michael Thomases and the two Chris
Thompsons -- can reach it.

One file, ~7MB, and it changes only when players enter or leave the league, so
build_all.py skips it once present.

Run:  python fetch_nflverse_players.py
"""
import os
import sys
import urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "nflverse")
URL = "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv"
OUT = os.path.join(DEST, "players.csv")
MIN_BYTES = 2_000_000

os.makedirs(DEST, exist_ok=True)
if os.path.exists(OUT) and os.path.getsize(OUT) > MIN_BYTES:
    print(f"  already present ({os.path.getsize(OUT):,} bytes)")
    sys.exit(0)

req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=180) as r:
    data = r.read()
if len(data) < MIN_BYTES:
    sys.exit(f"unexpected payload ({len(data)} bytes)")
with open(OUT, "wb") as f:
    f.write(data)
print(f"  downloaded {len(data):,} bytes -> {OUT}")
