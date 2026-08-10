"""Download nflverse season-level player stats for 2017-2025.

nflverse builds these from official NFL play-by-play, so they are authoritative
and reproducible -- unlike scraped ranking lists, which bake in someone else's
scoring settings. We pull raw stat lines and compute fantasy points ourselves
under this league's scoring (half-PPR, see build_clean_data.py).

Covers QB/RB/WR/TE and K. Team defenses (D/ST) are NOT in this dataset.

Run:  python fetch_nflverse.py        (re-run is safe; skips files already present)
"""
import os
import sys
import urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "nflverse")
BASE = "https://github.com/nflverse/nflverse-data/releases/download/stats_player"
SEASONS = range(2017, 2026)

os.makedirs(DEST, exist_ok=True)
failed = []
for year in SEASONS:
    fn = f"stats_player_reg_{year}.csv"
    out = os.path.join(DEST, fn)
    if os.path.exists(out) and os.path.getsize(out) > 100_000:
        print(f"  {year}  already present ({os.path.getsize(out):,} bytes)")
        continue
    url = f"{BASE}/{fn}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if data.strip() == b"Not Found" or len(data) < 100_000:
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
