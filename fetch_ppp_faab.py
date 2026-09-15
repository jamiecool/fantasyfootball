"""Pull Perennial Push waiver / FAAB transactions from ESPN -> rawdata/ppp/faab<season>.psv

    python fetch_ppp_faab.py             # every season it can reach
    python fetch_ppp_faab.py 2025        # one season

ESPN's mTransactions2 view answers per scoring period, so each season is 18 calls. It
returns every waiver claim with its bid and a status: EXECUTED is the winner,
FAILED_INVALIDPLAYERSOURCE is a bid that lost because the player had already gone to a
higher bid in the same run, and the other FAILED_* are roster-rule failures. Free-agent
adds after waivers clear are FREEAGENT with bidAmount 0, and a player cut without a
replacement is a ROSTER transaction carrying only a DROP item (kept, so a player's roster
history has no gaps; lineup shuffles are ROSTER too but carry no DROP and are skipped). Every
dropped player is kept -- a two-for-one claim yields an extra row per additional drop. That
is what the FAAB page needs:
who bid what on whom, who won, and (by subtraction from the budget) what each team had
left going into any week.

2025 onward is public. 2021-2024 sit behind the authenticated leagueHistory endpoint and
need espn_s2 + SWID in espn_credentials.json (gitignored); without the file those seasons
are skipped with a note, not an error.

Schema (pipe-separated, header row):
    season|sp|type|status|teamId|bid|processDate|txId|relatedId|addPid|addName|addPos|dropPid|dropName|dropPos

Player names come from ESPN's player endpoint for that season, cached in
rawdata/ppp/players_cache.json so re-runs do not re-ask. D/ST ids are negative
(-16000 - proTeamId) and are named from the team code table.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live_draft                                          # noqa: E402
from live_draft import PRO, POS                            # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
PPP = os.path.join(ROOT, "rawdata", "ppp")
CACHE = os.path.join(PPP, "players_cache.json")
LEAGUE = 623238770
PUBLIC_FROM = 2025
SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
HIST = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/leagueHistory/{lid}?seasonId={season}"
HEAD = "season|sp|type|status|teamId|bid|processDate|txId|relatedId|addPid|addName|addPos|dropPid|dropName|dropPos"


def league_url(season):
    if season >= PUBLIC_FROM:
        return live_draft.BASE.format(season=season, lid=LEAGUE)
    return HIST.format(lid=LEAGUE, season=season)


def get(url):
    st, j, _ = live_draft._get(url)
    if st == 200 and isinstance(j, list):                  # leagueHistory wraps in a list
        j = j[0] if j else None
    return st, j


def names_for(season, pids, cache):
    """Fill the cache for any id we have not seen. D/ST ids are synthetic."""
    want = []
    for p in pids:
        p = str(p)
        if p in cache:
            continue
        if p.startswith("-16"):
            cache[p] = {"n": PRO.get(-16000 - int(p), p) + " D/ST", "pos": "DEF"}
        else:
            want.append(p)
    for i in range(0, len(want), 60):
        batch = want[i:i + 60]
        flt = json.dumps({"players": {"filterIds": {"value": [int(x) for x in batch]}}})
        st, j, _ = live_draft._get(live_draft.PLAYERS.format(season=season),
                                   headers={"x-fantasy-filter": flt})
        if st == 200 and isinstance(j, list):
            for pl in j:
                cache[str(pl["id"])] = {"n": pl.get("fullName", "?"),
                                        "pos": POS.get(pl.get("defaultPositionId"), "?")}
        for p in batch:
            cache.setdefault(p, {"n": "ESPN #%s" % p, "pos": "?"})


def pull(season, cache):
    rows, seen = [], set()
    base = league_url(season)
    for sp in range(1, 19):
        st, j = get(base + f"{'&' if '?' in base else '?'}view=mTransactions2&scoringPeriodId={sp}")
        if st in (401, 403):
            return None, f"ESPN answered {st}: needs espn_s2 + SWID in espn_credentials.json"
        if st != 200 or not j:
            continue
        for t in j.get("transactions", []):
            # WAIVER = bids, FREEAGENT = $0 adds, ROSTER = a plain drop with nothing added
            # (a roster move that has a DROP item; lineup shuffles have none and are skipped)
            items = t.get("items", [])
            if t.get("type") not in ("WAIVER", "FREEAGENT", "ROSTER") or t["id"] in seen:
                continue
            if t["type"] == "ROSTER" and not any(i["type"] == "DROP" for i in items):
                continue
            seen.add(t["id"])
            add = next((i for i in items if i["type"] == "ADD"), {})
            drops = [i for i in items if i["type"] == "DROP"]
            drop = drops[0] if drops else {}
            base_row = dict(season=season, sp=t.get("scoringPeriodId", sp), type=t["type"],
                            status=t.get("status", ""), teamId=t.get("teamId"),
                            bid=t.get("bidAmount", 0) or 0,
                            processDate=t.get("processDate") or t.get("proposedDate") or 0,
                            txId=t["id"], relatedId=t.get("relatedTransactionId") or "")
            rows.append(dict(base_row, addPid=add.get("playerId"), dropPid=drop.get("playerId")))
            for extra in drops[1:]:                       # a two-for-one claim drops two players
                rows.append(dict(base_row, txId=t["id"] + "#" + str(extra["playerId"]),
                                 type="ROSTER", bid=0, addPid=None, dropPid=extra["playerId"]))
    pids = {r["addPid"] for r in rows if r["addPid"]} | {r["dropPid"] for r in rows if r["dropPid"]}
    names_for(season, pids, cache)
    for r in rows:
        a, d = cache.get(str(r["addPid"]), {}), cache.get(str(r["dropPid"]), {})
        r["addName"], r["addPos"] = a.get("n", ""), a.get("pos", "")
        r["dropName"], r["dropPos"] = d.get("n", ""), d.get("pos", "")
    rows.sort(key=lambda r: (r["sp"], r["processDate"], -r["bid"]))
    return rows, None


def main():
    seasons = [int(sys.argv[1])] if len(sys.argv) > 1 else SEASONS
    cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    for y in seasons:
        rows, why = pull(y, cache)
        if rows is None:
            print(f"{y}: skipped -- {why}")
            continue
        if not rows:
            print(f"{y}: no waiver or free-agent transactions returned")
            continue
        out = os.path.join(PPP, f"faab{y}.psv")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(HEAD + "\n")
            for r in rows:
                f.write("|".join(str(r[k]) if r[k] is not None else "" for k in HEAD.split("|")) + "\n")
        won = sum(1 for r in rows if r["type"] == "WAIVER" and r["status"] == "EXECUTED")
        lost = sum(1 for r in rows if r["type"] == "WAIVER" and r["status"] == "FAILED_INVALIDPLAYERSOURCE")
        fa = sum(1 for r in rows if r["type"] == "FREEAGENT")
        dr = sum(1 for r in rows if r["type"] == "ROSTER")
        print(f"{y}: {len(rows)} rows -> {os.path.relpath(out, ROOT)}  "
              f"({won} winning bids, {lost} outbid, {fa} free-agent adds, {dr} plain drops)")
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=0, sort_keys=True)
    print(f"player cache: {len(cache)} names  ({time.strftime('%Y-%m-%d %H:%M')})")


if __name__ == "__main__":
    main()
