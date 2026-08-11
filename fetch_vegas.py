"""Betting-market expectations for team scoring -- two feeds, both free.

Why bother when rule 4 says not to out-rank the market: this is a DIFFERENT
market. ADP is fantasy drafters guessing; a point spread is priced by people
risking money, repriced continuously, and it is the sharpest read available on
how many points an offence will score. Whether it adds anything ON TOP of ADP is
an open question -- see the validation note at the bottom -- but it is at least
not the same crowd.

  1. nflverse/nfldata games.csv
     Every game 1999-present with spread_line and total_line. Implied team
     total is arithmetic from those two:
         home = total/2 + spread/2      away = total/2 - spread/2
     (spread_line is positive when the HOME team is favoured.)
     This is the historical record, so it is what lets us TEST whether Vegas
     predicted fantasy production across the nine seasons we already have
     week-by-week stats for.

  2. sharpfootballanalysis.com implied team totals tool
     Season-long projected points per game for all 32 teams, plus a
     weeks-15-17 column -- which happens to be exactly this league's playoff
     window. In August this matters more than feed 1, because books have only
     posted the first three or four weeks of games.

Run:  python fetch_vegas.py
"""
import os
import re
import sys
import time
import urllib.request

import pandas as pd
from bs4 import BeautifulSoup

from snapshots import snapshot_path

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(ROOT, "rawdata", "vegas")
GAMES = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
SHARP = "https://www.sharpfootballanalysis.com/fantasy/nfl-implied-team-totals-tool/"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Sharp lists teams by nickname; everything else here keys on the abbreviation.
NICK = {
    "cardinals": "ARI", "falcons": "ATL", "ravens": "BAL", "bills": "BUF",
    "panthers": "CAR", "bears": "CHI", "bengals": "CIN", "browns": "CLE",
    "cowboys": "DAL", "broncos": "DEN", "lions": "DET", "packers": "GB",
    "texans": "HOU", "colts": "IND", "jaguars": "JAX", "chiefs": "KC",
    "raiders": "LV", "chargers": "LAC", "rams": "LA", "dolphins": "MIA",
    "vikings": "MIN", "patriots": "NE", "saints": "NO", "giants": "NYG",
    "jets": "NYJ", "eagles": "PHI", "steelers": "PIT", "49ers": "SF",
    "seahawks": "SEA", "buccaneers": "TB", "titans": "TEN", "commanders": "WAS",
}


def get(url, timeout=90):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


os.makedirs(DEST, exist_ok=True)

# ------------------------------------------------------- 1. game-level lines
print("nflverse games.csv ...")
raw = os.path.join(DEST, "games.csv")
with open(raw, "wb") as f:
    f.write(get(GAMES))
g = pd.read_csv(raw, low_memory=False)
g = g[g["total_line"].notna() & g["spread_line"].notna()].copy()
g["home_implied"] = (g["total_line"] / 2 + g["spread_line"] / 2).round(2)
g["away_implied"] = (g["total_line"] / 2 - g["spread_line"] / 2).round(2)

# one row per team per game, which is the shape everything downstream wants
long = pd.concat([
    g.rename(columns={"home_team": "team", "away_team": "opponent",
                      "home_implied": "implied_total"})
     .assign(is_home=1)[["season", "week", "team", "opponent", "is_home",
                         "spread_line", "total_line", "implied_total"]],
    g.rename(columns={"away_team": "team", "home_team": "opponent",
                      "away_implied": "implied_total"})
     .assign(is_home=0)[["season", "week", "team", "opponent", "is_home",
                         "spread_line", "total_line", "implied_total"]],
], ignore_index=True).sort_values(["season", "week", "team"])
long.to_csv(os.path.join(DEST, "team_week_implied.csv"), index=False)
cov = long.groupby("season").size()
print(f"  {len(long):,} team-games, {long.season.min()}-{long.season.max()}")
print(f"  2026 so far: {cov.get(2026, 0)} team-games "
      f"({long[long.season == 2026].week.max() if (long.season == 2026).any() else 0} weeks priced)")

# ------------------------------------------------- 2. season-long projections
print("\nsharpfootballanalysis implied totals ...")
try:
    soup = BeautifulSoup(get(SHARP).decode("utf-8", "replace"), "html.parser")
    table = None
    for t in soup.find_all("table"):
        head = [c.get_text(strip=True).lower() for c in t.find_all("tr")[0].find_all(["th", "td"])]
        if any("pts" in h for h in head):
            table = t
            break
    if table is None:
        raise ValueError("no table with a points column -- page layout changed")

    cols = [c.get_text(strip=True) for c in table.find_all("tr")[0].find_all(["th", "td"])]
    cols = [re.sub(r"[▼▲]", "", c).strip() for c in cols]
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < 2:
            continue
        # First cell is rank glued to nickname glued to a caret: "1Rams▶".
        # A greedy \d+ eats the 49 in "3149ers", so split on the shortest digit
        # prefix that leaves a nickname we recognise.
        cell = cells[0].replace("▶", "").strip()
        rank = nick = abbr = None
        for k in (1, 2):
            if len(cell) <= k or not cell[:k].isdigit():
                continue
            cand = cell[k:].strip().lower()
            if cand in NICK:
                rank, nick, abbr = int(cell[:k]), cell[k:].strip(), NICK[cand]
                break
        if abbr is None:
            print(f"    unmapped team cell: {cell!r}")
            continue
        rec = {"season": 2026, "vegas_rank": rank, "team": abbr, "nickname": nick}
        for name, val in zip(cols[1:], cells[1:]):
            key = re.sub(r"_+", "_", name.lower().replace("/", " per ")
                          .replace(" ", "_")).strip("_").replace("wk_", "week_")
            try:
                rec[key] = float(val)
            except ValueError:
                rec[key] = None
        rows.append(rec)
    if len(rows) < 30:
        raise ValueError(f"only parsed {len(rows)} teams, expected 32")
    sharp = pd.DataFrame(rows)
    sharp["fetched_at"] = time.strftime("%Y-%m-%d")
    _out = snapshot_path(DEST, "sharp_implied_2026", "csv")
    sharp.to_csv(_out, index=False)
    print(f"  {len(sharp)} teams -> {os.path.basename(_out)}")
    print(f"  columns: {[c for c in sharp.columns if c not in ('season','nickname','fetched_at')]}")
    ppg = next((c for c in sharp.columns if "pts" in c and "per" in c), None)
    if ppg:
        print(f"\n  best and worst offences by projected {ppg}:")
        for r in pd.concat([sharp.nsmallest(4, "vegas_rank"),
                            sharp.nlargest(3, "vegas_rank")]).itertuples():
            print(f"    {r.vegas_rank:>2}. {r.team:4} {getattr(r, ppg):5.1f}")
except Exception as e:                                       # noqa: BLE001
    print(f"  FAILED: {e}")
    print("  (game-level lines above are unaffected)")
    sys.exit(1)

print("""
NOT YET VALIDATED. Before any of this reaches the board, the question to settle
is whether a team's implied total predicts fantasy production ABOVE what ADP
already knows -- ADP is set by people who have also seen the Vegas number. The
test is available: nine seasons of historical lines here, nine seasons of
player_weeks already in the DB.""")
