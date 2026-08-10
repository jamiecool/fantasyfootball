"""Download current-season Underdog best-ball ADP.

Underdog is the market reference this league already uses (the 2021 workbook
carried an UnderDog ADP sheet), and Underdog best ball is half-PPR -- the same
scoring as PBAFFL -- so its ADP is directly comparable to our valuations.

Underdog publishes no public ADP API, so this reads Sharp Football Analysis'
republished table, which carries current ADP, previous ADP and the delta.

Caveats worth remembering:
  * Best ball is NOT redraft. 18-round rosters, no waivers, and a FLEX that
    PBAFFL does not have. Treat it as a market signal, not a drafting plan.
  * Best ball rosters no kickers or defenses, so K/DEF are absent entirely.

Writes rawdata/underdog/ : the parsed CSV, a .meta.json recording when it was
fetched and when the source itself was last updated, and the raw HTML.

Run:  python fetch_underdog_adp.py        (always re-fetches; that is the point)
"""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone

from bs4 import BeautifulSoup

SEASON = 2026                      # bump each year
URL = ("https://www.sharpfootballanalysis.com/fantasy/"
       "fantasy-football-adp-half-ppr-underdog-best-ball/")
DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "underdog")

TEAM_ABBR = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS", "Free Agent": "FA",
}

os.makedirs(DEST, exist_ok=True)
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
with urllib.request.urlopen(req, timeout=60) as r:
    html = r.read().decode("utf-8", errors="replace")

with open(os.path.join(DEST, f"underdog_adp_{SEASON}.html"), "w", encoding="utf-8") as f:
    f.write(html)

soup = BeautifulSoup(html, "lxml")
grid = soup.find("table")
rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        for tr in grid.find_all("tr")]
data = [r for r in rows if len(r) == 7 and r[0] != "Player"]
if len(data) < 100:
    raise SystemExit(f"parsed only {len(data)} rows - page layout probably changed")

# the page states its own last-updated date in prose, e.g. "Updated August 6"
m = re.search(r"Updated\s+([A-Z][a-z]+\s+\d{1,2})", soup.get_text(" ", strip=True))
source_updated = m.group(1) if m else None

unknown = sorted({r[2] for r in data} - set(TEAM_ABBR))
if unknown:
    print("WARNING unmapped NFL teams:", unknown)

num = lambda s: float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s or "") else None
out = []
for r in data:
    player, pos, team, pos_adp, adp, prev, delta = r
    out.append({
        "season": SEASON, "player_name": player, "position": pos.upper(),
        "nfl_team": TEAM_ABBR.get(team, team), "pos_adp": pos_adp,
        "adp": num(adp), "prev_adp": num(prev), "adp_delta": num(delta),
    })
out.sort(key=lambda x: (x["adp"] is None, x["adp"]))

import csv
csv_path = os.path.join(DEST, f"underdog_adp_{SEASON}.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)

meta = {
    "season": SEASON, "source": "underdog (via sharpfootballanalysis)", "url": URL,
    "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    "source_updated": source_updated, "rows": len(out),
    "scoring": "half-ppr (Underdog best ball)",
    "note": "best ball ADP; no K/DEF; roster shape differs from PBAFFL (has FLEX)",
}
with open(os.path.join(DEST, f"underdog_adp_{SEASON}.meta.json"), "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=1)

print(f"  {len(out)} players -> {csv_path}")
print(f"  source last updated: {source_updated}   fetched: {meta['fetched_at']}")
top5 = ", ".join("{} ({})".format(o["player_name"], o["adp"]) for o in out[:5])
print(f"  top 5: {top5}")
