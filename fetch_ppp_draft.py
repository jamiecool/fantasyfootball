"""Pull one season's Perennial Push draft from ESPN into rawdata/ppp/draft<season>.psv.

    python fetch_ppp_draft.py            # the current season (2026)
    python fetch_ppp_draft.py 2027

The read API only records a draft once it is COMPLETE (it shows 0 picks while one is in
progress -- see live_draft.py), so run this the morning after. Public league since 2025,
no cookies needed; 2021-2024 sat behind the authenticated league-history endpoint and
were pulled once in a Cowork container (rawdata/ppp/README.md).

Writes, in the schema the other seasons use:
    rawdata/ppp/draft<season>.psv      overall|round|pick|teamId|playerId|keeper|name|pos|actual|proj|gp
                                       (actual and gp are blank/0 until the season is played)
    rawdata/ppp/draft<season>_meta.json  autopicks by overall pick (autoDraftTypeId), pulled-at
    rawdata/ppp/snapshots/draft_<season>_raw.json  the API payload, for provenance

Names, positions and projections come from board<season>.psv where the player is in the
pool, else from ESPN's player endpoint (the same lookup the live watcher uses).
"""
import csv
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_draft                                          # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
PPP = os.path.join(ROOT, "rawdata", "ppp")
LEAGUE = 623238770
SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026


def main():
    st, j, _ = live_draft._get(live_draft.BASE.format(season=SEASON, lid=LEAGUE)
                               + "?view=mDraftDetail&view=mSettings")
    if st != 200 or not j:
        sys.exit(f"ESPN answered {st} for league {LEAGUE} season {SEASON}")
    dd = j.get("draftDetail", {})
    slots = dd.get("picks", [])
    made = [p for p in slots if p.get("playerId", -1) not in (-1, 0)]
    if not dd.get("drafted") or len(made) != len(slots):
        sys.exit(f"draft not complete: drafted={dd.get('drafted')} filled={len(made)}/{len(slots)}")

    # names: the board first, then ESPN for anyone outside the pool
    board = {}
    bp = os.path.join(PPP, f"board{SEASON}.psv")
    if os.path.exists(bp):
        with open(bp, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="|"):
                if len(row) >= 8 and row[0].isdigit():
                    board[row[0]] = dict(n=row[1], pos=row[2], proj=row[7])
    w = live_draft.Watcher()
    w.state = {"players": {}}
    w.board = {k: dict(n=v["n"], pos=v["pos"], tm="", rank=0) for k, v in board.items()}
    missing = {str(p["playerId"]) for p in made if str(p["playerId"]) not in board}
    extra = w._resolve(SEASON, missing) if missing else {}

    made.sort(key=lambda p: p["overallPickNumber"])
    out = os.path.join(PPP, f"draft{SEASON}.psv")
    unknown = 0
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        for p in made:
            pid = str(p["playerId"])
            b = board.get(pid) or extra.get(pid) or {}
            if not b:
                unknown += 1
            f.write("|".join([
                str(p["overallPickNumber"]), str(p["roundId"]), str(p["roundPickNumber"]),
                str(p["teamId"]), pid, "1" if p.get("keeper") else "0",
                b.get("n", f"ESPN #{pid}"), b.get("pos", "?"),
                "",                                            # actual: season not played
                str(b.get("proj", "") or ""), "0",
            ]) + "\n")
    meta = dict(season=SEASON, league=LEAGUE, pulled=time.strftime("%Y-%m-%d %H:%M"),
                picks=len(made), autopicks={str(p["overallPickNumber"]): p["autoDraftTypeId"]
                                           for p in made if p.get("autoDraftTypeId")})
    with open(os.path.join(PPP, f"draft{SEASON}_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    os.makedirs(os.path.join(PPP, "snapshots"), exist_ok=True)
    with open(os.path.join(PPP, "snapshots", f"draft_{SEASON}_raw.json"), "w", encoding="utf-8") as f:
        json.dump(dd, f)
    print(f"wrote {os.path.relpath(out, ROOT)}: {len(made)} picks, "
          f"{len(meta['autopicks'])} autopicks, {len(missing)} names looked up, {unknown} unresolved")


if __name__ == "__main__":
    main()
