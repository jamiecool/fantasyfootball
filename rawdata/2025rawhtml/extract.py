"""Extract the three raw sources into clean JSON.

Sources (all saved from Yahoo Fantasy, league 792831, 2025 season):
  draftresults.html   - every drafted player + drafting team, NO prices
  finalrosters.mhtml  - end-of-season rosters WITH auction prices, but the
                        player set is wrong (adds waiver pickups, drops cuts)
  top2025.txt         - preseason average player ranking, 1..200
"""
import email
import json
import re

from bs4 import BeautifulSoup

DIR = r"c:\Users\Jamie\repos\fantasyfootball\rawdata\2025rawhtml"


def txt(node):
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def split_pos(s):
    """'Dal - WR' / 'Hou RB' -> ('Dal', 'WR')"""
    parts = [p for p in re.split(r"\s*-\s*|\s+", s.strip()) if p]
    return (parts[0], parts[-1]) if len(parts) >= 2 else (s.strip(), "")


# ---------- 1. draft results ----------
soup = BeautifulSoup(open(f"{DIR}/draftresults.html", encoding="utf-8").read(), "lxml")
draft = []
for rnd, table in enumerate(soup.select("table.Table"), 1):
    for tr in table.select("tr"):
        first = tr.select_one("td.first")
        link = tr.select_one("td.player a.name")
        last = tr.select_one("td.last")
        if not (first and link):
            continue
        nfl, pos = split_pos(txt(tr.select_one("td.player span.Block")).strip("()"))
        draft.append({
            "round": rnd,
            "pick": int(re.sub(r"\D", "", txt(first)) or 0),
            "player": txt(link),
            "nfl": nfl,
            "pos": pos,
            # visible text is truncated ("Cops and Rod..."); title= holds the full name
            "fteam": last.get("title", txt(last)).strip(),
        })

# ---------- 2. final rosters ----------
msg = email.message_from_file(open(f"{DIR}/finalrosters.mhtml", encoding="utf-8", errors="replace"))
part = [p for p in msg.walk() if p.get_content_type() == "text/html"][0]
rsoup = BeautifulSoup(part.get_payload(decode=True).decode("utf-8", errors="replace"), "lxml")

rosters = []
for table in rsoup.find_all("table", id=re.compile(r"^statTable-?\d+$")):
    # team name = nearest preceding heading/link text above this table
    label, node = "", table
    while node and not label:
        node = node.find_previous(["h3", "h2", "a", "div", "span"])
        cand = txt(node)
        if cand and len(cand) < 60 and "Player" not in cand:
            label = cand
    for tr in table.select("tbody tr"):
        cell = tr.select_one("td.player")
        if not cell or not cell.find("a"):
            continue
        nfl, pos = split_pos(txt(cell.select_one("span.F-position")))
        rosters.append({
            "fteam": label,
            "player": txt(cell.find("a")),
            "nfl": nfl,
            "pos": pos,
            "cost": txt(tr.select_one("td.auctioncost")),
        })

# ---------- 3. average rankings ----------
ranks = []
for line in open(f"{DIR}/top2025.txt", encoding="utf-8"):
    m = re.match(r"\s*(\d+)\.\s*(.+?),\s*([A-Za-z]+)\s*--\s*([A-Za-z]+)(\d+)", line)
    if m:
        ranks.append({"rank": int(m.group(1)), "player": m.group(2).strip(),
                      "nfl": m.group(3), "pos": m.group(4), "posrank": int(m.group(5))})

json.dump({"draft": draft, "rosters": rosters, "ranks": ranks},
          open(f"{DIR}/extracted.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

if __name__ == "__main__":
    import collections
    print(f"draft   : {len(draft):4d} picks, {max(d['round'] for d in draft)} rounds, "
          f"{len(set(d['fteam'] for d in draft))} teams")
    print(f"rosters : {len(rosters):4d} rows,  "
          f"{len(set(r['fteam'] for r in rosters))} teams")
    print(f"ranks   : {len(ranks):4d} players\n")
    print("roster rows/team:", collections.Counter(r["fteam"] for r in rosters).most_common())
    print("\nteam-name match draft vs roster:",
          set(d["fteam"] for d in draft) == set(r["fteam"] for r in rosters))
    c = collections.Counter(r["cost"] for r in rosters)
    print("blank costs:", c[""], " dash costs:", c["-"],
          " priced:", sum(v for k, v in c.items() if k.isdigit()))
