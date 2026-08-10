"""Reconstruct the 2025 auction draft results from three partial sources.

Method
------
1. draftresults.html gives the authoritative set of 192 drafted players and who
   drafted them, but no prices.
2. finalrosters.mhtml supplies real auction prices for the 140 of those players
   still rostered at season's end. (All 140 priced players appear in the draft
   list, so a price always implies a draft pick.)
3. The remaining 52 players were drafted then dropped, so their price is gone.
   We recover it from two signals:
     a. a log-linear price-vs-rank curve fitted on the 127 players that have
        BOTH a known price and a top2025 ranking, and
     b. the auction budget identity: each team spent exactly $200, so a team's
        unpriced players must account for ($200 - its known spend), with a $1
        minimum per player.
   (b) is the stronger constraint and is enforced exactly; (a) decides how the
   leftover dollars are split among a team's unpriced players.
"""
import csv
import json
import re
import unicodedata

import numpy as np

DIR = r"c:\Users\Jamie\repos\fantasyfootball\rawdata\2025rawhtml"
BUDGET = 200
MIN_BID = 1


def norm(n):
    """Name key robust to accents and Jr/Sr/III suffixes."""
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n)
    return re.sub(r"[^a-z]", "", n)


d = json.load(open(f"{DIR}/extracted.json", encoding="utf-8"))
price = {norm(r["player"]): int(r["cost"]) for r in d["rosters"] if r["cost"].isdigit()}
rank = {norm(r["player"]): r["rank"] for r in d["ranks"]}

picks = []
for p in d["draft"]:
    k = norm(p["player"])
    picks.append({**p, "key": k, "known": price.get(k), "rank": rank.get(k)})

# ---- 1. fit log-linear price curve on players with both price and rank ----
cal = [(p["rank"], p["known"]) for p in picks if p["known"] and p["rank"]]
x = np.array([c[0] for c in cal], float)
y = np.log(np.array([c[1] for c in cal], float))
slope, intercept = np.polyfit(x, y, 1)
curve = lambda r: float(np.exp(intercept + slope * r))

pred_known = np.exp(intercept + slope * x)
resid = np.abs(pred_known - np.array([c[1] for c in cal], float))

# ---- 2. seed every unpriced player from the curve ----
# players outside the top-200 ranking get the curve's value at rank 200 (~$1)
for p in picks:
    if p["known"] is None:
        p["seed"] = max(curve(p["rank"] if p["rank"] else 210), 0.35)

# ---- 3. reconcile each team to exactly $200 ----
teams = sorted({p["fteam"] for p in picks})
audit = []
for t in teams:
    known = sum(p["known"] for p in picks if p["fteam"] == t and p["known"])
    unp = [p for p in picks if p["fteam"] == t and p["known"] is None]
    pot = BUDGET - known
    if not unp:
        audit.append((t, known, 0, pot, 0))
        continue
    # distribute `pot` proportional to the curve seed, min $1, integer, exact sum
    free = pot - MIN_BID * len(unp)          # dollars above the $1 floor
    w = np.array([p["seed"] for p in unp], float)
    share = w / w.sum() * max(free, 0)
    base = np.floor(share).astype(int)
    for i in np.argsort(-(share - base))[: int(max(free, 0) - base.sum())]:
        base[i] += 1
    for p, extra in zip(unp, base):
        p["est"] = MIN_BID + int(extra)
    audit.append((t, known, len(unp), pot, sum(p["est"] for p in unp)))

for p in picks:
    p["cost"] = p["known"] if p["known"] is not None else p["est"]
    p["source"] = "actual" if p["known"] is not None else "estimated"

# ---- 4. sort most expensive first and write the CSV ----
picks.sort(key=lambda p: (-p["cost"], p["rank"] if p["rank"] else 999, p["player"]))
out = f"{DIR}/draft2025.csv"
with open(out, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["rank", "cost", "player", "position", "fantasy_team", "source"])
    for i, p in enumerate(picks, 1):
        w.writerow([i, p["cost"], p["player"], p["pos"], p["fteam"], p["source"]])

# ---- report ----
print(f"curve: price = {np.exp(intercept):.1f} * exp({slope:.5f} * rank)   "
      f"n={len(cal)}  median abs err=${np.median(resid):.2f}\n")
print(f"{'team':32s} {'known$':>7s} {'nEst':>5s} {'estPot$':>8s} {'alloc$':>7s} {'total$':>7s}")
for t, known, n, pot, alloc in audit:
    print(f"{t:32s} {known:7d} {n:5d} {pot:8d} {alloc:7d} {known + alloc:7d}")
print(f"{'TOTAL':32s} {sum(a[1] for a in audit):7d} {sum(a[2] for a in audit):5d} "
      f"{sum(a[3] for a in audit):8d} {sum(a[4] for a in audit):7d} "
      f"{sum(a[1] + a[4] for a in audit):7d}")
print(f"\nrows: {len(picks)}   wrote {out}")
