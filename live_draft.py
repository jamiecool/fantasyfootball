"""Watch an ESPN draft while it is happening, for the dashboard's DRAFTED plan.

WHY. Entering 216 picks by hand during a 90-second-clock draft is not viable, and
ESPN's draft room is the only screen that shows them. But the league endpoint we
already read for history exposes the draft while it is in progress: every pick
slot exists before the draft starts (playerId -1) and fills in as picks are made.
Poll it, and the dashboard can grey out the taken players and fill Jamie's own
picks into the DRAFTED plan with nobody typing anything.

    https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leagues/<id>?view=mDraftDetail

Verified 2026-09-08 that the 2026 slots are already there for league 623238770,
with the pick order set. Verified by someone else's shipped tool (justinmck's
fantasy-football-draft-toolkit) that the slots fill mid-draft at a 5-second poll and
that ESPN honours If-None-Match, so most polls are an empty 304. NOT yet verified
here against a live draft -- that is what the first mock is for.

The league is public in 2026, so no cookies are needed. A private league would
need espn_s2 + SWID in espn_credentials.json (gitignored), same as history does.

TESTED AGAINST A MOCK 2026-09-08: the read API does NOT see an in-progress draft. The room
was at pick 131 and mDraftDetail still showed 0 filled slots (origin cache miss confirmed).
So polling is only good for the record after the draft. The room gets its picks from a
Server-Sent Events stream on fantasydraft.espn.com, and that server allows ONE connection
per team: joining it from here kicked Jamie's browser out with "Duplicate Connection", and
once his session was gone every join was refused ("No team with ID 11"). Hence the third
mode, which is the one that works on draft night:

    RELAY. tools/espn_draft_relay.user.js (Tampermonkey) wraps EventSource in the draft-room
    tab and POSTs every event the room receives to serve.py at /api/live/relay. The room
    keeps its single connection; we read over its shoulder. Event grammar seen so far:
        AUTODRAFT <team> <bool>        SELECTING <team> <clockMs>       CLOCK <?> <msLeft> <team>
        SELECTED <team> <playerId> <n> AUTOSUGGEST <playerId>           TOKEN <...>
        INIT <base64 blob>             (18KB binary state; not decoded -- start the relay
                                        before pick 1 and it is not needed)

Three modes:
    Watcher.start(league_id, team_id)      poll the read API (post-draft record only)
    Watcher.start("sim", team_id)          a simulated draft off ESPN's list, one pick
                                           every few seconds, for rehearsing the page
    Watcher.relay(text)                    an event forwarded from the draft room

The snapshot this hands out (Watcher.snapshot(), served as GET /api/live) is:
    active, mode, leagueId, teamId, season, teams[{id,ab,name}], pickOrder[teamId],
    nTeams, rounds, inProgress, drafted, picks[{o,rd,pk,tm,pid,auto}],
    players{pid:{n,pos,tm}} for anyone not on board2026.psv, updated, polled, error
"""
import csv
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(ROOT, "espn_credentials.json")
BOARD = os.path.join(ROOT, "rawdata", "ppp", "board2026.psv")
OUT = os.path.join(ROOT, "shared", "live_draft.json")     # gitignored; transient
BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/leagues/{lid}"
PLAYERS = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players?view=kona_player_info"
POLL_IDLE = 5.0           # seconds between polls before the draft starts
POLL_LIVE = 3.0           # ...and once it is in progress
SIM_STEP = 3.0            # seconds per simulated pick
UA = "Mozilla/5.0 (fantasyfootball dashboard; local draft watcher)"

POS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}
try:
    from fetch_espn_league import PRO                     # ESPN proTeamId -> code
except Exception:                                         # noqa: BLE001
    PRO = {}


def _cookie():
    """espn_s2 + SWID if the file is there; a public league does not need them."""
    try:
        with open(CREDS, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("espn_s2") and c.get("SWID"):
            return "espn_s2=%s; SWID=%s" % (c["espn_s2"], c["SWID"])
    except FileNotFoundError:
        pass
    except Exception as e:                                # noqa: BLE001
        sys.stderr.write("  live: could not read espn_credentials.json: %r\n" % e)
    return None


def _get(url, etag=None, headers=None, timeout=15):
    """GET as JSON. Returns (status, body_or_None, etag). 304 -> (304, None, etag)."""
    h = {"Accept": "application/json", "User-Agent": UA}
    ck = _cookie()
    if ck:
        h["Cookie"] = ck
    if etag:
        h["If-None-Match"] = etag
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8")), r.headers.get("ETag")
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return 304, None, etag
        return e.code, None, etag


def decode_init(blob, teams=None):
    """The INIT payload the draft server sends on join: the whole draft state in a
    custom binary (base64). Reverse-engineered from a mock 2026-09-08. Picks are an
    array of 45-byte records, preceded by their count as a big-endian int32:

        +16 int32 teamId   +20 int32 overallPick   +24 int32 playerId (-1 = not yet made)
        +28 int32 position id (1 QB 2 RB 3 WR 4 TE 5 K 16 DST)

    The record start is found by scanning for consecutive overall numbers 1, 2, 3 at a
    45-byte stride, so the header before it need not be understood. Returns
    [{o, tm, pid}] for made picks ([] before pick 1), or None if the layout is not recognised."""
    import base64
    import struct
    try:
        b = base64.b64decode(blob + "=" * (-len(blob) % 4))
    except Exception:                                     # noqa: BLE001
        return []
    I = lambda o: struct.unpack(">i", b[o:o + 4])[0]     # noqa: E731
    okteam = (lambda t: t in teams) if teams else (lambda t: 0 < t < 100)
    start = None
    for o in range(0, len(b) - 45 * 3):
        if I(o + 20) == 1 and I(o + 65) == 2 and I(o + 110) == 3 and okteam(I(o + 16)):
            start = o
            break
    if start is None:
        return None                                       # layout not recognised
    count = I(start - 4) if start >= 4 and 0 < I(start - 4) <= 400 else 400
    out = []
    for k in range(count):
        o = start + 45 * k
        if o + 28 > len(b) or I(o + 20) != k + 1:
            break
        pid = I(o + 24)
        if pid not in (-1, 0):
            out.append({"o": k + 1, "tm": I(o + 16), "pid": str(pid)})
    return out


def _board():
    """pid -> {n,pos,tm} for everyone on the 2026 board, so no lookup is needed for them."""
    out = {}
    try:
        with open(BOARD, encoding="utf-8") as f:
            for row in csv.reader(f, delimiter="|"):
                if len(row) >= 5 and row[0].isdigit():
                    out[row[0]] = {"n": row[1], "pos": row[2], "tm": row[3], "rank": int(row[4])}
    except FileNotFoundError:
        pass
    return out


class Watcher:
    def __init__(self):
        self.lock = threading.Lock()
        self.thread = None
        self.stop_evt = threading.Event()
        self.state = {"active": False}
        self.board = _board()

    # ---- control -----------------------------------------------------------
    def start(self, league_id, team_id=None, season=2026):
        self.stop()
        league_id = str(league_id).strip()
        self.stop_evt = threading.Event()
        with self.lock:
            self.state = {
                "active": True, "mode": "sim" if league_id == "sim" else "espn",
                "leagueId": league_id, "teamId": int(team_id) if team_id not in (None, "") else None,
                "season": int(season), "teams": [], "pickOrder": [], "nTeams": 0, "rounds": 0,
                "inProgress": False, "drafted": False, "picks": [], "players": {},
                "updated": None, "polled": None, "error": None, "http": None,
            }
        self.thread = threading.Thread(target=self._run, daemon=True, name="espn-draft-watch")
        self.thread.start()
        sys.stderr.write("  live: watching %s draft %s%s\n" % (
            "simulated" if league_id == "sim" else "ESPN", league_id,
            " for team %s" % team_id if team_id else ""))

    def stop(self):
        if self.thread and self.thread.is_alive():
            self.stop_evt.set()
            self.thread.join(timeout=5)
        with self.lock:
            if self.state.get("active"):
                self.state["active"] = False
        self._write()

    def snapshot(self):
        with self.lock:
            return json.loads(json.dumps(self.state))

    # ---- relay: events forwarded from the draft-room tab -------------------
    def relay(self, text, league=None):
        """One SSE payload (or 'JOIN <url>' from the userscript). `league` is the id the
        userscript read off its own stream URL: events from a tab still open on an OLD
        draft are dropped, so two rooms can never feed one session. Returns a status."""
        text = (text or "").strip()
        if not text:
            return "empty"
        kind, _, rest = text.partition(" ")
        if kind == "JOIN":
            return self._relay_join(rest)
        with self.lock:
            st = self.state
            if not st.get("active") or st.get("mode") != "relay":
                return "no relay session -- the userscript sends JOIN first"
            if league and str(league) != str(st.get("leagueId")):
                return "ignored: event from league %s while following %s" % (league, st.get("leagueId"))
            st["lastEvent"] = time.strftime("%H:%M:%S")
        parts = rest.split()
        if kind == "SELECTED" and len(parts) >= 2:
            self._relay_pick(int(parts[0]), parts[1])
            return "pick"
        if kind == "SELECTING" and parts:
            self._set(onClock=int(parts[0]), clockMs=int(parts[1]) if len(parts) > 1 else None, inProgress=True)
            return "clock"
        if kind == "CLOCK" and len(parts) >= 3:
            self._set(clockMs=int(parts[1]), onClock=int(parts[2]))
            return "tick"
        if kind == "AUTODRAFT" and len(parts) >= 2:
            with self.lock:
                self.state.setdefault("autodraft", {})[parts[0]] = parts[1] == "true"
            return "autodraft"
        if kind == "INIT":
            return self._relay_init(rest)
        return "ignored"

    def _relay_join(self, url):
        """The userscript saw the room open its stream. Read league/team off the URL and
        load the teams and pick order from the read API, which does know those."""
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(url).query)
        lid, tid = (q.get("2") or [None])[0], (q.get("3") or [None])[0]
        if not lid:
            m = re.search(r"league-(\d+)", url)
            lid = m.group(1) if m else None
        if not lid:
            return "JOIN without a league id"
        with self.lock:
            same = self.state.get("active") and self.state.get("mode") == "relay" \
                and str(self.state.get("leagueId")) == str(lid)
            if same:                       # a reconnect or a reload of the room, not a new draft
                self.state["lastEvent"] = time.strftime("%H:%M:%S")
                if tid and tid.lstrip("-").isdigit():
                    self.state["teamId"] = int(tid)
        if same:
            return "rejoined"
        # A different league. Make sure it is a live one before dropping the session we
        # have: a room left open on a finished mock reconnects and re-sends JOIN for a
        # league ESPN has already deleted, and that must not hijack the current draft.
        try:
            teams, order = self._teams(2026, lid)
        except Exception as e:                            # noqa: BLE001
            sys.stderr.write("  live: ignoring JOIN for league %s (%s)\n" % (lid, e))
            return "stale join ignored"
        self.stop()
        self.stop_evt = threading.Event()
        with self.lock:
            self.state = {
                "active": True, "mode": "relay", "leagueId": str(lid),
                "teamId": int(tid) if tid and tid.lstrip("-").isdigit() else None, "season": 2026,
                "teams": [], "pickOrder": [], "nTeams": 0, "rounds": 18, "inProgress": True,
                "drafted": False, "picks": [], "players": {}, "autodraft": {}, "onClock": None,
                "clockMs": None, "updated": None, "polled": None, "lastEvent": time.strftime("%H:%M:%S"),
                "error": None, "http": None, "joined": time.strftime("%H:%M:%S"),
            }
        try:
            st, j, _ = _get(BASE.format(season=2026, lid=lid) + "?view=mDraftDetail")
            rounds = (len((j or {}).get("draftDetail", {}).get("picks", [])) // len(order)) if (j and order) else 18
            self._set(teams=teams, pickOrder=order, nTeams=len(order), rounds=rounds or 18)
        except Exception as e:                            # noqa: BLE001
            self._set(error="teams: %r" % e)
        sys.stderr.write("  live: relay from the draft room, league %s team %s\n" % (lid, tid))
        return "joined"

    def _relay_init(self, blob):
        """Full state on (re)join: replaces whatever we had, so a mid-draft join or a
        reload of the room recovers every pick already made with its real number."""
        with self.lock:
            teams = {t["id"] for t in self.state.get("teams", [])}
            n = self.state.get("nTeams") or 0
        made = decode_init(blob, teams or None)
        if made is None:
            with self.lock:
                self.state["error"] = "INIT not decoded: picks are numbered from when the relay joined"
            try:                                          # keep it, so the decoder can be fixed later
                with open(os.path.join(ROOT, "shared", "init_undecoded_%s.b64" % time.strftime("%H%M%S")), "w") as f:
                    f.write(blob)
            except OSError:
                pass
            return "init-undecoded"
        picks = []
        n = n or 12
        for m in made:
            rd = (m["o"] - 1) // n + 1
            pk = (m["o"] - 1) % n + 1
            picks.append({"o": m["o"], "rd": rd, "pk": pk, "tm": m["tm"], "pid": m["pid"], "auto": False})
        new = self._resolve(2026, {m["pid"] for m in made})
        with self.lock:
            self.state["picks"] = picks
            self.state["players"].update(new)
            self.state["updated"] = time.strftime("%H:%M:%S")
            self.state["error"] = None
            self.state["inProgress"] = len(picks) < n * (self.state.get("rounds") or 18) if n else True
        self._write()
        sys.stderr.write("  live: INIT decoded, %d picks already made\n" % len(picks))
        return "init"

    def _relay_pick(self, team, pid):
        """SELECTED carries team and player but no pick number. Picks are numbered by
        arrival, checked against the snake: if the team on this slot is not the one that
        picked, we joined mid-draft, so jump to the next slot that IS this team's."""
        pid = str(pid)
        with self.lock:
            st = self.state
            if any(p["pid"] == pid for p in st["picks"]):
                return
            order, n = st["pickOrder"], st["nTeams"] or 12
            o = st["picks"][-1]["o"] + 1 if st["picks"] else 1

            def owner(k):
                rd = (k - 1) // n + 1
                pk = (k - 1) % n + 1
                return order[pk - 1] if rd % 2 else order[n - pk]
            if order and owner(o) != team:
                k = o
                while k <= n * st["rounds"] and owner(k) != team:
                    k += 1
                if k <= n * st["rounds"]:
                    if not st["picks"]:
                        st["error"] = "relay joined mid-draft: pick numbers inferred from the snake"
                    o = k
            rd = (o - 1) // n + 1
            pk = (o - 1) % n + 1
            st["picks"].append({"o": o, "rd": rd, "pk": pk, "tm": team, "pid": pid,
                                "auto": bool(st.get("autodraft", {}).get(str(team)))})
            st["updated"] = time.strftime("%H:%M:%S")
            done = n and st["rounds"] and o >= n * st["rounds"]
        new = self._resolve(2026, {pid})
        with self.lock:
            self.state["players"].update(new)
            if done:
                self.state["drafted"] = True
                self.state["inProgress"] = False
        self._write()
        sys.stderr.write("  live: pick %d %s -> team %s\n" % (o, self._name(pid), team))

    # ---- internals ---------------------------------------------------------
    def _set(self, **kw):
        with self.lock:
            self.state.update(kw)
            self.state["polled"] = time.strftime("%H:%M:%S")
        self._write()

    def _write(self):
        try:
            os.makedirs(os.path.dirname(OUT), exist_ok=True)
            tmp = OUT + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.snapshot(), f)
            os.replace(tmp, OUT)
        except Exception:                                 # noqa: BLE001
            pass

    def _teams(self, season, lid):
        """Team ids, abbreviations and the draft order. One call, before polling."""
        st, j, _ = _get(BASE.format(season=season, lid=lid) + "?view=mTeam&view=mSettings")
        if st != 200 or not j:
            raise RuntimeError("ESPN answered %s for league %s (mTeam)" % (st, lid))
        teams = [{"id": t["id"], "ab": t.get("abbrev") or str(t["id"]),
                  "name": (t.get("name") or (t.get("location", "") + " " + t.get("nickname", ""))).strip()}
                 for t in j.get("teams", [])]
        ds = j.get("settings", {}).get("draftSettings", {})
        order = ds.get("pickOrder") or [t["id"] for t in teams]
        return teams, order

    def _resolve(self, season, pids):
        """Names for player ids that are not on the board (deep sleepers, late K/DEF)."""
        pids = [p for p in pids if p not in self.board and p not in self.state["players"]]
        if not pids:
            return {}
        flt = json.dumps({"players": {"filterIds": {"value": [int(p) for p in pids]}}})
        st, j, _ = _get(PLAYERS.format(season=season), headers={"x-fantasy-filter": flt})
        out = {}
        if st == 200 and isinstance(j, list):
            for pl in j:
                out[str(pl["id"])] = {"n": pl.get("fullName", "?"),
                                      "pos": POS.get(pl.get("defaultPositionId"), "?"),
                                      "tm": PRO.get(pl.get("proTeamId"), "")}
        for p in pids:                                    # never ask twice for the same id
            out.setdefault(str(p), {"n": "ESPN #%s" % p, "pos": "?", "tm": ""})
        return out

    @staticmethod
    def _picks(dd):
        return [{"o": p["overallPickNumber"], "rd": p["roundId"], "pk": p["roundPickNumber"],
                 "tm": p["teamId"], "pid": str(p["playerId"]),
                 "auto": bool(p.get("autoDraftTypeId"))}
                for p in dd.get("picks", []) if p.get("playerId", -1) not in (-1, 0, None)]

    def _run(self):
        s = self.snapshot()
        season, lid = s["season"], s["leagueId"]
        try:
            if s["mode"] == "sim":
                return self._run_sim(season)
            teams, order = self._teams(season, lid)
            n = len(teams)
            self._set(teams=teams, pickOrder=order, nTeams=n)
            etag = None
            url = BASE.format(season=season, lid=lid) + "?view=mDraftDetail"
            while not self.stop_evt.is_set():
                st, j, etag = _get(url, etag=etag)
                if st == 200 and j:
                    dd = j.get("draftDetail", {})
                    picks = self._picks(dd)
                    rounds = (len(dd.get("picks", [])) // n) if n else 0
                    new = self._resolve(season, {p["pid"] for p in picks})
                    with self.lock:
                        changed = picks != self.state["picks"]
                        self.state["players"].update(new)
                    self._set(picks=picks, rounds=rounds, http=200, error=None,
                              inProgress=bool(dd.get("inProgress")), drafted=bool(dd.get("drafted")),
                              **({"updated": time.strftime("%H:%M:%S")} if changed else {}))
                    if changed:
                        sys.stderr.write("  live: %d picks in%s\n" % (
                            len(picks), ", latest %s" % self._name(picks[-1]["pid"]) if picks else ""))
                    if dd.get("drafted") and picks:
                        sys.stderr.write("  live: draft complete, watcher stopping\n")
                        self._set(active=False)
                        return
                elif st == 304:
                    self._set(http=304, error=None)
                else:
                    self._set(http=st, error="ESPN answered %s" % st)
                self.stop_evt.wait(POLL_LIVE if self.state.get("inProgress") else POLL_IDLE)
        except Exception as e:                            # noqa: BLE001
            self._set(error=repr(e), active=False)
            sys.stderr.write("  live: watcher stopped: %r\n" % e)

    def _name(self, pid):
        p = self.board.get(pid) or self.state["players"].get(pid) or {}
        return p.get("n", pid)

    def _run_sim(self, season):
        """A rehearsal draft: the room takes ESPN's list roughly in order, with the
        kind of scatter the real room shows (sd ~ 6 picks early, widening later).
        Teams and pick order come from the real league so the abbreviations match."""
        try:
            teams, order = self._teams(season, "623238770")
        except Exception:                                 # noqa: BLE001
            teams = [{"id": i, "ab": "T%d" % i, "name": "Team %d" % i} for i in range(1, 13)]
            order = [t["id"] for t in teams]
        n, rounds = len(order), 18
        self._set(teams=teams, pickOrder=order, nTeams=n, rounds=rounds, inProgress=True)
        ranked = sorted(self.board.items(), key=lambda kv: kv[1]["rank"])
        skill = [pid for pid, p in ranked if p["pos"] not in ("K", "DEF")]
        kd = [pid for pid, p in ranked if p["pos"] in ("K", "DEF")]
        taken, picks = set(), []
        rng = random.Random(7)
        for o in range(1, n * rounds + 1):
            if self.stop_evt.is_set():
                return
            rd = (o - 1) // n + 1
            pk = (o - 1) % n + 1
            tm = order[pk - 1] if rd % 2 else order[n - pk]
            pool = kd if rd >= 14 and rng.random() < 0.5 and any(p not in taken for p in kd) else skill
            avail = [p for p in pool if p not in taken]
            if not avail:
                avail = [p for p in skill + kd if p not in taken]
            idx = min(len(avail) - 1, max(0, int(abs(rng.gauss(0, 1.5 + rd * 0.6)))))
            pid = avail[idx]
            taken.add(pid)
            picks.append({"o": o, "rd": rd, "pk": pk, "tm": tm, "pid": pid, "auto": rng.random() < 0.05})
            self._set(picks=list(picks), updated=time.strftime("%H:%M:%S"), http=200)
            self.stop_evt.wait(SIM_STEP)
        self._set(drafted=True, inProgress=False, active=False)
