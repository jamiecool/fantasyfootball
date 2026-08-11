"""Yahoo's own draft analysis -- the market our league actually drafts in.

Why this matters more than any other ADP source we have: PBAFFL drafts in the
Yahoo app, so Yahoo's numbers are what our leaguemates see on their screen while
bidding. Underdog is the sharper market and stays the source for ORDERING (see
build_2026_board.py), but Yahoo is the best available read on what this room has
been anchored to.

And it is an AUCTION league, so `average_cost` is the field that matters -- an
actual dollar figure from Yahoo salary-cap drafts, directly comparable to the
est_price on our board. Nothing else we pull gives us that.

Source: the same public JSON the draftanalysis page calls. No login, no OAuth --
`470.l.public` is Yahoo's public sample league and pub-api-ro is read-only. This
sidesteps the Yahoo Fantasy API entirely, which is still returning
`additional_authorization_required` on every endpoint pending app approval.

Run:  python fetch_yahoo_adp.py
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(ROOT, "rawdata", "yahoo")
SEASON = 2026
# Yahoo's game key for the season. This changes every year -- 449 was 2024,
# 461 was 2025. If a fetch returns last season's players, this is why.
GAME_KEY = 470
PAGE = 25
BASE = ("https://pub-api-ro.fantasysports.yahoo.com/fantasy/v2/"
        f"league/{GAME_KEY}.l.public;out=settings/players;position=ALL;"
        "start={start};count={count};sort=average_pick;search=;"
        "out=auction_values,ranks;ranks=o-rank;out=expert_ranks;"
        "expert_ranks.rank_type=projected_season_remaining/"
        "draft_analysis;cut_types=diamond;slices=last7days?format=json_f")
HEADERS = {"Referer": "https://football.fantasysports.yahoo.com/",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Accept": "application/json"}


def get(start, count=PAGE, tries=3):
    url = BASE.format(start=start, count=count)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if attempt == tries - 1:
                raise
            print(f"    retry {attempt + 1} after {e}")
            time.sleep(2 + 2 * attempt)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


os.makedirs(DEST, exist_ok=True)
rows, start, seen = [], 0, set()
while True:
    payload = get(start)
    players = payload.get("fantasy_content", {}).get("league", {}).get("players", [])
    if not players:
        break
    for item in players:
        p = item.get("player", item)
        key = p.get("player_key")
        if not key or key in seen:
            continue
        seen.add(key)
        da = p.get("draft_analysis") or {}
        rows.append({
            "season": SEASON,
            "player_name": (p.get("name") or {}).get("full", ""),
            "yahoo_player_key": key,
            "position": p.get("display_position", ""),
            "nfl_team": (p.get("editorial_team_abbr") or "").upper(),
            "average_pick": num(da.get("average_pick")),
            "average_round": num(da.get("average_round")),
            "average_cost": num(da.get("average_cost")),
            "percent_drafted": num(da.get("percent_drafted")),
            "preseason_average_pick": num(da.get("preseason_average_pick")),
            "preseason_average_cost": num(da.get("preseason_average_cost")),
            "projected_auction_value": num(p.get("projected_auction_value")),
            "status": p.get("status", ""),
            "injury_note": p.get("injury_note", ""),
        })
    print(f"  {start:>4}-{start + len(players) - 1:<4} {len(rows):>4} players so far")
    if len(players) < PAGE:
        break
    start += PAGE
    time.sleep(0.6)                      # be a polite guest on a public endpoint

if not rows:
    sys.exit("no players returned -- check GAME_KEY (it changes each season)")

# Only players Yahoo has actually seen drafted carry a usable ADP; the long tail
# comes back with nulls and would pollute any rank we derive.
ranked = [r for r in rows if r["average_pick"] is not None]
ranked.sort(key=lambda r: r["average_pick"])
for i, r in enumerate(ranked, 1):
    r["yahoo_rank"] = i                  # overall rank, the thing to compare against

meta = {"source": "yahoo public draft analysis (pub-api-ro)",
        "season": SEASON, "game_key": GAME_KEY,
        "fetched_at": time.strftime("%Y-%m-%d"), "rows": len(rows),
        "with_adp": len(ranked)}
out = os.path.join(DEST, f"yahoo_adp_{SEASON}.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump({"meta": meta, "players": rows}, f, indent=1)

print(f"\n{len(rows)} players, {len(ranked)} with an ADP -> {out}")
withcost = [r for r in ranked if r["average_cost"]]
print(f"{len(withcost)} carry an average auction cost")
print("\ntop 10 by Yahoo ADP:")
print(f"  {'rk':>3} {'player':22} {'pos':4} {'ADP':>6} {'avg $':>7} {'%drafted':>9}")
for r in ranked[:10]:
    pc = f"{100 * r['percent_drafted']:.0f}%" if r["percent_drafted"] is not None else "—"
    ac = f"${r['average_cost']:.1f}" if r["average_cost"] else "—"
    print(f"  {r['yahoo_rank']:>3} {r['player_name'][:22]:22} {r['position']:4} "
          f"{r['average_pick']:>6.1f} {ac:>7} {pc:>9}")
