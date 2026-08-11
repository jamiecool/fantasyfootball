"""Pull historical league standings from the Yahoo Fantasy API.

We have draft data for 106 team-seasons and actual outcomes for 12. This closes
that gap, which is the single most valuable data acquisition left: it turns
every retrospective result from "this roster scored well" into "this roster
won", and gives the season simulator something real to validate against.

The league is private (Make League Publicly Viewable: No), so this needs OAuth.
One-time setup:

  1. Go to https://developer.yahoo.com/apps/create/
       Application Name : anything, e.g. "pbaffl-analysis"
       Application Type : Confidential Client
       Redirect URI(s)  : https://localhost:8000/callback
       API Permissions  : tick "Fantasy Sports" -> Read
     Create it, then copy the Client ID and Client Secret.

  2. Save them next to this script as yahoo_credentials.json (gitignored):
       {"client_id": "...", "client_secret": "..."}

  3. Run this script. It prints a URL -- open it, approve, and you'll land on a
     localhost page that fails to load. That is expected: copy the ?code=...
     value out of the address bar and paste it back here.

The token is cached in yahoo_token.json, so step 3 happens only once.

Writes rawdata/standings/standings_YYYY.csv, the same shape build_clean_data.py
already reads -- so a rebuild picks them up with no further changes.

Run:  python fetch_yahoo_standings.py
"""
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(ROOT, "rawdata", "standings")
CRED = os.path.join(ROOT, "yahoo_credentials.json")
TOKEN = os.path.join(ROOT, "yahoo_token.json")
REDIRECT = "https://localhost:8000/callback"
AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
API = "https://fantasysports.yahooapis.com/fantasy/v2"
LEAGUE_ID = "792831"          # PBAFFL; past seasons carry the same league id


def _post(url, data):
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r)


def authorize(cid, secret):
    """Interactive once; afterwards the cached refresh token is used."""
    q = urllib.parse.urlencode({"client_id": cid, "redirect_uri": REDIRECT,
                                "response_type": "code"})
    print("\nOpen this URL, approve access, then copy the ?code=... value from")
    print("the address bar of the page it redirects to (it will fail to load):\n")
    print(f"  {AUTH_URL}?{q}\n")
    code = input("code: ").strip()
    tok = _post(TOKEN_URL, {"client_id": cid, "client_secret": secret,
                            "redirect_uri": REDIRECT, "code": code,
                            "grant_type": "authorization_code"})
    tok["obtained_at"] = time.time()
    json.dump(tok, open(TOKEN, "w"))
    return tok


def get_token():
    if not os.path.exists(CRED):
        sys.exit(f"missing {os.path.basename(CRED)} -- see the setup notes at the "
                 "top of this file")
    c = json.load(open(CRED))
    cid, secret = c["client_id"], c["client_secret"]
    if not os.path.exists(TOKEN):
        return authorize(cid, secret)["access_token"]
    tok = json.load(open(TOKEN))
    if time.time() - tok.get("obtained_at", 0) < tok.get("expires_in", 3600) - 120:
        return tok["access_token"]
    fresh = _post(TOKEN_URL, {"client_id": cid, "client_secret": secret,
                              "redirect_uri": REDIRECT,
                              "refresh_token": tok["refresh_token"],
                              "grant_type": "refresh_token"})
    fresh["obtained_at"] = time.time()
    fresh.setdefault("refresh_token", tok["refresh_token"])
    json.dump(fresh, open(TOKEN, "w"))
    return fresh["access_token"]


def api(path, token):
    req = urllib.request.Request(f"{API}/{path}",
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def walk(node, key):
    """Yahoo's JSON nests dicts inside numerically-keyed dicts; find every `key`."""
    out = []
    if isinstance(node, dict):
        if key in node:
            out.append(node[key])
        for v in node.values():
            out += walk(v, key)
    elif isinstance(node, list):
        for v in node:
            out += walk(v, key)
    return out


def main():
    os.makedirs(DEST, exist_ok=True)
    token = get_token()

    # every NFL league this account has ever been in, across all seasons
    data = api("users;use_login=1/games;game_codes=nfl/leagues?format=json", token)
    leagues = {}
    for blk in walk(data, "league"):
        for item in (blk if isinstance(blk, list) else [blk]):
            if isinstance(item, dict) and item.get("league_key"):
                leagues[item["league_key"]] = item
    mine = {k: v for k, v in leagues.items() if k.split(".l.")[-1] == LEAGUE_ID}
    if not mine:
        print("no leagues matched id", LEAGUE_ID, "- found:",
              sorted(leagues))
        mine = leagues
    print(f"{len(mine)} season(s) found\n")

    for key, meta in sorted(mine.items(), key=lambda kv: kv[1].get("season", "")):
        season = int(meta.get("season", 0))
        try:
            st = api(f"league/{key}/standings?format=json", token)
        except Exception as e:                              # noqa: BLE001
            print(f"  {season}  FAILED: {e}")
            continue
        rows = []
        for t in walk(st, "team"):
            flat = {}
            for part in (t if isinstance(t, list) else [t]):
                for chunk in (part if isinstance(part, list) else [part]):
                    if isinstance(chunk, dict):
                        flat.update(chunk)
            outcome = flat.get("team_standings") or {}
            rec = outcome.get("outcome_totals") or {}
            if not flat.get("name"):
                continue
            rows.append({
                "season": season, "rank": outcome.get("rank"),
                "team": flat.get("name"),
                "wins": rec.get("wins"), "losses": rec.get("losses"),
                "ties": rec.get("ties", 0),
                "points_for": outcome.get("points_for"),
                "points_against": outcome.get("points_against"),
                "streak": "", "waiver_budget_left": "",
                "waiver_priority": "", "moves": flat.get("number_of_moves", ""),
                "playoff_seed": outcome.get("playoff_seed", ""),
                "finish": "",
            })
        rows = [r for r in rows if r["rank"]]
        if not rows:
            print(f"  {season}  no standings returned")
            continue
        out = os.path.join(DEST, f"standings_{season}.csv")
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(sorted(rows, key=lambda r: int(r["rank"])))
        print(f"  {season}  {len(rows)} teams -> {os.path.basename(out)}")
        time.sleep(0.5)

    print("\nnow run:  python build_clean_data.py")


if __name__ == "__main__":
    main()
