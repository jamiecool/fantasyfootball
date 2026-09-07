"""Yahoo's analysts' consensus rankings -- the third ordering on the Perennial Push board.

WHAT THIS IS. Yahoo's "Fantasy Football Full PPR Rankings: Top 300" article
(sports.yahoo.com/fantasy/article/...-175205585.html) carries no list in its own
markup: the table is a FantasyPros partner widget, filtered to Yahoo's six
analysts (Boone, Harmon, Norris, Pianowski, Smyth, Winks) by their FantasyPros
expert IDs. The widget's JS calls a public JSON endpoint; this pulls the same JSON.
So the file this writes IS the Yahoo article, not a FantasyPros consensus -- the
`filters` parameter is what makes it Yahoo's six and nobody else's.

WHAT IT IS FOR. Ordering WITHIN a position only, as a third pivot next to
Underdog's on the Perennial Push board (see CLAUDE.md, "How a board is priced").
It is a 1-QB PPR ranking, so its cross-position order is meaningless for a
superflex league -- Josh Allen is #31 here -- and nothing downstream uses it.
It does carry K and D/ST, which Underdog does not, so the Yahoo pivot orders
those from Yahoo too.

Written like the other live feeds: a dated snapshot for the record, plus the
fixed-name CSV the build reads. Live, so build_all.py runs it only with --refresh.

Run:  python fetch_yahoo_rankings.py
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

from snapshots import snapshot_path

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(ROOT, "rawdata", "yahoo")
SEASON = 2026
# Yahoo's six analysts, as FantasyPros expert IDs, copied from the widget URL the
# article embeds. If Yahoo changes its staff this is the line to update -- pull
# the article, find the partners.fantasypros.com iframe, read `filters=`.
YAHOO_EXPERTS = "9:317:747:1408:7604:7666"
URL = ("https://partners.fantasypros.com/api/v1/consensus-rankings.php"
       f"?sport=NFL&year={SEASON}&week=0&position=ALL&scoring=PPR&type=ST"
       f"&filters={YAHOO_EXPERTS}&expert=7261")
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Referer": "https://sports.yahoo.com/", "Accept": "application/json"}
STEM = f"yahoo_consensus_ppr_{SEASON}"


def get(tries=3):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(URL, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == tries - 1:
                raise
            print(f"    retry {attempt + 1} after {e}")
            time.sleep(2 + 2 * attempt)


data = get()
players = data.get("players") or []

# Trap 3: sanity-check a fetched page against things we already know before
# trusting it. A wrong year, a different filter, or a truncated payload all show
# up here rather than as a quietly odd board.
if str(data.get("year")) != str(SEASON):
    sys.exit(f"payload is for {data.get('year')}, wanted {SEASON}")
if data.get("total_experts") != 6:
    sys.exit(f"expected Yahoo's 6 analysts, payload has {data.get('total_experts')} "
             f"(filters={data.get('filters')})")
ecr = [p["rank_ecr"] for p in players]
if len(players) < 300 or ecr != list(range(1, len(players) + 1)):
    sys.exit(f"rankings look truncated or unsorted: {len(players)} players, "
             f"ecr {ecr[:3]}..{ecr[-3:]}")
by_pos = {}
for p in players:
    by_pos[p["player_position_id"]] = by_pos.get(p["player_position_id"], 0) + 1
for pos, floor in (("QB", 30), ("RB", 60), ("WR", 80), ("TE", 25)):
    if by_pos.get(pos, 0) < floor:
        sys.exit(f"only {by_pos.get(pos, 0)} {pos}s in the payload; expected at least {floor}")

os.makedirs(DEST, exist_ok=True)
snap = snapshot_path(DEST, STEM, "json")
with open(snap, "w", encoding="utf-8") as f:
    json.dump(data, f)

rows = [dict(
    rank=p["rank_ecr"], player_name=p["player_name"], position=p["player_position_id"],
    team=p["player_team_id"], pos_rank=p["pos_rank"],
    rank_ave=p["rank_ave"], rank_std=p["rank_std"], rank_min=p["rank_min"], rank_max=p["rank_max"],
    tier=p.get("tier"), yahoo_id=p.get("player_yahoo_id"), bye=p.get("player_bye_week"),
) for p in players]
csv_path = os.path.join(DEST, f"{STEM}.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
with open(os.path.join(DEST, f"{STEM}.meta.json"), "w", encoding="utf-8") as f:
    json.dump(dict(source="Yahoo Sports consensus PPR rankings (FantasyPros partner widget, "
                          "filtered to Yahoo's six analysts)",
                   url=URL, season=SEASON, experts=data.get("total_experts"),
                   filters=data.get("filters"), players=len(rows),
                   last_updated=data.get("last_updated"),
                   last_updated_ts=data.get("last_updated_ts"),
                   fetched_on=time.strftime("%Y-%m-%d")), f, indent=2)

print(f"{len(rows)} players from {data.get('total_experts')} Yahoo analysts, "
      f"rankings updated {data.get('last_updated')}  -> {os.path.relpath(csv_path, ROOT)}")
print("  by position: " + ", ".join(f"{k} {v}" for k, v in sorted(by_pos.items())))
print("  top 8:  " + ", ".join(f"{p['rank_ecr']} {p['player_name']} ({p['pos_rank']})" for p in players[:8]))
qbs = [p for p in players if p["player_position_id"] == "QB"][:5]
print("  first QBs (1-QB ranking; only the within-position order is used): "
      + ", ".join(f"{p['player_name']} #{p['rank_ecr']}" for p in qbs))
print(f"  snapshot: {os.path.relpath(snap, ROOT)}")
