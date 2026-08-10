"""Download historical preseason ADP (2017-2025) from Fantasy Football Calculator.

ADP is the market's expectation going INTO a season -- the counterpart to
final_ranks, which is what actually happened. Together they let you ask which
managers beat the market rather than just who finished well.

All three scoring formats are pulled and stored. This league is half-PPR, but
FFC has no half-PPR data for 2017, so the build falls back to PPR for that year
and records which format each row came from.

Saved as raw JSON so a re-run is reproducible and the source is auditable.

Run:  python fetch_adp.py        (re-run is safe; skips files already present)
"""
import json
import os
import time
import urllib.request

DEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rawdata", "adp")
BASE = "https://fantasyfootballcalculator.com/api/v1/adp"
# Includes the CURRENT season deliberately. The ADP->price curve is calibrated on
# FFC historical ADP, so the current-season input must also be FFC or the curve
# is fitted on one source and applied to another. FFC is also the better format
# match for this league than Underdog: redraft rather than best ball, and it
# drafts kickers and defenses, which Underdog does not.
SEASONS = range(2017, 2027)
FORMATS = ["half-ppr", "ppr", "standard"]
TEAMS = 12

os.makedirs(DEST, exist_ok=True)
got, missing = 0, []
for year in SEASONS:
    for fmt in FORMATS:
        out = os.path.join(DEST, f"adp_{fmt}_{year}.json")
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            got += 1
            continue
        url = f"{BASE}/{fmt}?teams={TEAMS}&year={year}&position=all"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                payload = json.load(r)
            if payload.get("status") != "Success" or not payload.get("players"):
                missing.append(f"{year}/{fmt}")
                continue
            with open(out, "w", encoding="utf-8") as f:
                json.dump(payload, f)
            n = len(payload["players"])
            print(f"  {year} {fmt:<9} {n:>3} players, {payload['meta']['total_drafts']:>5} drafts")
            got += 1
            time.sleep(0.6)          # be polite to a free public API
        except Exception as e:       # noqa: BLE001
            print(f"  {year} {fmt:<9} FAILED: {e}")
            missing.append(f"{year}/{fmt}")

print(f"\n{got} files in {DEST}")
if missing:
    print("no data published for:", ", ".join(missing))
