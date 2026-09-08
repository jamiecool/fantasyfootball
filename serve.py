"""Serve cleandata/ with caching turned off, and accept saves of the shared board state.

`python -m http.server` sends Last-Modified but no Cache-Control, so Chrome
applies heuristic caching and an F5 can be answered from memory without ever
asking the server. That means a rebuilt dashboard silently does not appear --
which shows up as features "not working" when in fact an older page is running.

This is the same server with no-store on every response, plus one POST endpoint.

WHY THE POST ENDPOINT. Targets, notes and draft plans used to live only in
localStorage, so they never left the browser that made them. They are now kept in
shared/board_state.json, which IS tracked, so a clone gets them. A static page
cannot write to disk, and this server is already ours, so the "Save" button posts
the state here and this writes the file. Then it is a normal commit.

Four keys are persisted: targets, notes, plans (PBAFFL's auction plans) and
xplans (Perennial Push's snake plans).

It also hosts the ESPN draft watcher (live_draft.py): GET /api/live is the draft as
ESPN last reported it, POST /api/live starts or stops watching a league.

Bound to localhost only, one fixed path, shape-validated, and written atomically
with a .bak kept -- it accepts a file from a web page, so it is careful about it.

Run:  python serve.py            (then open http://localhost:8000/dashboard.html)
      python serve.py 8080       (if 8000 is taken)
"""
import functools
import http.server
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import live_draft                                        # noqa: E402  (the ESPN draft watcher)

# python serve.py [port] [--watch LEAGUE_ID|sim] [--team TEAM_ID]
_args = sys.argv[1:]
WATCH_LEAGUE = _args[_args.index("--watch") + 1] if "--watch" in _args else None
WATCH_TEAM = _args[_args.index("--team") + 1] if "--team" in _args else None
# the port is the digits that are NOT a flag's value -- a league id is 9 digits and
# was once taken for one, which bind() refused
_flagvals = {WATCH_LEAGUE, WATCH_TEAM}
PORT = next((int(a) for a in _args if a.isdigit() and a not in _flagvals), 8000)
WATCH = live_draft.Watcher()
WEB = os.path.join(ROOT, "cleandata")
STATE = os.path.join(ROOT, "shared", "board_state.json")
MAX_BODY = 4 * 1024 * 1024          # plans and notes; nothing legitimate is bigger


def whoami():
    """Whose save this was, so the file records it without anyone typing a name."""
    try:
        r = subprocess.run(["git", "config", "user.name"], cwd=ROOT,
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or ""
    except Exception:                                        # noqa: BLE001
        return ""


def write_state(payload):
    """Validate, then write atomically. Returns the record that was stored."""
    if not isinstance(payload, dict):
        raise ValueError("expected an object")
    targets = payload.get("targets", [])
    notes = payload.get("notes", {})
    plans = payload.get("plans", [])
    # The second league's snake plans (Perennial Push). These were dropped on the
    # floor here for a while: the page posted them but this function only knew
    # about three keys, so PPP plans never left the browser that made them.
    xplans = payload.get("xplans", [])
    # Targets carry WHICH LEAGUE they are for: both / ppr / half. Older saves are
    # a plain list of keys, from before that existed; those were league-agnostic
    # by definition, so they are read as "both" rather than dropped.
    if isinstance(targets, list):
        if not all(isinstance(t, str) for t in targets):
            raise ValueError("targets given as a list must be a list of player keys")
        targets = {t: "both" for t in targets}
    elif isinstance(targets, dict):
        bad = {v for v in targets.values()} - {"both", "ppr", "half"}
        if bad:
            raise ValueError("target scope must be both/ppr/half, got "
                             + ", ".join(sorted(map(repr, bad))))
        if not all(isinstance(k, str) for k in targets):
            raise ValueError("target keys must be player keys")
    else:
        raise ValueError("targets must be a map of player key -> both/ppr/half")
    if not isinstance(notes, dict) or not all(isinstance(v, str) for v in notes.values()):
        raise ValueError("notes must be a map of player key -> text")
    if not isinstance(plans, list):
        raise ValueError("plans must be a list")
    if not isinstance(xplans, list):
        raise ValueError("xplans must be a list")

    rec = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M"),
        "saved_by": whoami(),
        # sorted so two people editing produce a line-by-line diff git can merge,
        # rather than a reordered blob that always conflicts. A map now, one
        # player per line, which merges the same way a sorted list did.
        "targets": {k: targets[k] for k in sorted(targets)},
        "notes": {k: notes[k] for k in sorted(notes) if notes[k].strip()},
        "plans": plans,
        "xplans": xplans,
    }
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    if os.path.exists(STATE):
        # ONE .bak IS NOT A BACKUP. It held exactly one save, so two writes in
        # quick succession -- which autosave makes routine -- destroyed the only
        # copy of whatever came before. That is how a finished 11-pick draft plan
        # was lost on 2026-09-02, overwritten and then overwritten again before
        # anyone noticed. Keep a dated history instead; it is a few KB a day.
        shutil.copy2(STATE, STATE + ".bak")
        hist = os.path.join(os.path.dirname(STATE), "history")
        os.makedirs(hist, exist_ok=True)
        shutil.copy2(STATE, os.path.join(
            hist, time.strftime("board_state_%Y%m%d_%H%M%S.json")))
        # keep the most recent 200 -- roughly a fortnight of heavy drafting
        old = sorted(f for f in os.listdir(hist) if f.startswith("board_state_"))
        for f in old[:-200]:
            try:
                os.remove(os.path.join(hist, f))
            except OSError:
                pass
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, indent=2, sort_keys=False, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, STATE)
    return rec


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        if self.path.startswith("/api/live/relay"):        # for the userscript's fetch() fallback
            self.send_header("Access-Control-Allow-Origin", "https://fantasy.espn.com")
            self.send_header("Access-Control-Allow-Headers", "content-type, x-relay-league")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # The page bakes in a copy of the state at build time, so without this it
        # cannot see its own save until the next rebuild -- a reload would show an
        # empty board while the file on disk was correct. This serves the live file.
        if self.path.rstrip("/") == "/api/state":
            try:
                with open(STATE, encoding="utf-8") as f:
                    return self._json(200, json.load(f))
            except FileNotFoundError:
                return self._json(200, {"saved_at": "", "saved_by": "", "targets": {},
                                        "notes": {}, "plans": [], "xplans": []})
            except Exception as e:                           # noqa: BLE001
                return self._json(500, {"error": repr(e)})
        # The live ESPN draft, as the watcher last saw it (see live_draft.py). The page
        # polls this every few seconds while the snake planner is open.
        if self.path.rstrip("/") == "/api/live":
            return self._json(200, WATCH.snapshot())
        # The draft-room relay userscript, served so Tampermonkey can install it from a URL
        # (it intercepts any *.user.js fetched over http). Lives in tools/, not cleandata/.
        if self.path.split("?")[0] == "/espn_draft_relay.user.js":
            try:
                body = open(os.path.join(ROOT, "tools", "espn_draft_relay.user.js"), "rb").read()
            except OSError as e:
                return self._json(404, {"error": repr(e)})
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        # One draft-room event, forwarded by tools/espn_draft_relay.user.js. Plain text
        # body, no JSON: the userscript sends exactly what ESPN sent it.
        if self.path.rstrip("/") == "/api/live/relay":
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 65536:
                    return self._json(413, {"error": "event too large"})
                text = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                out = WATCH.relay(text, self.headers.get("X-Relay-League"))
            except Exception as e:                           # noqa: BLE001
                return self._json(500, {"error": repr(e)})
            return self._json(200, {"ok": True, "status": out})
        if self.path.rstrip("/") == "/api/live":
            # {"action":"start","leagueId":"623238770","teamId":11} or {"action":"stop"}
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
                if body.get("action") == "stop":
                    WATCH.stop()
                elif body.get("action") == "start":
                    lid = str(body.get("leagueId") or "").strip()
                    if not (lid == "sim" or lid.isdigit()):
                        return self._json(400, {"error": "leagueId must be a number or 'sim'"})
                    WATCH.start(lid, body.get("teamId") or None, body.get("season") or 2026)
                else:
                    return self._json(400, {"error": "action must be start or stop"})
            except Exception as e:                           # noqa: BLE001
                return self._json(500, {"error": repr(e)})
            return self._json(200, WATCH.snapshot())
        if self.path.rstrip("/") != "/api/state":
            return self._json(404, {"error": "no such endpoint"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self._json(413, {"error": f"body must be 1..{MAX_BODY} bytes"})
            rec = write_state(json.loads(self.rfile.read(n).decode("utf-8")))
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        except Exception as e:                               # noqa: BLE001
            return self._json(500, {"error": repr(e)})
        sys.stderr.write(f"  saved board state: {len(rec['targets'])} targets, "
                         f"{len(rec['notes'])} notes, {len(rec['plans'])} plans, "
                         f"{len(rec['xplans'])} snake plans"
                         f"{' by ' + rec['saved_by'] if rec['saved_by'] else ''}\n")
        return self._json(200, {"ok": True, "saved_at": rec["saved_at"],
                                "saved_by": rec["saved_by"]})

    def do_OPTIONS(self):                     # CORS preflight for the relay's fetch fallback
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):        # one line per request, not three
        if args and "/api/live" in str(args[0]):
            return                            # the page polls every 4 s and the relay posts every tick
        sys.stderr.write("  %s\n" % (fmt % args))


class Reusable(http.server.ThreadingHTTPServer):
    """THREADED, which is not optional here.

    `python -m http.server` uses ThreadingHTTPServer; the first version of this
    file used a plain socketserver.TCPServer and was therefore single-threaded.
    That works for one sequential curl and fails the moment a browser is
    involved: it holds a keep-alive connection open, the single handler thread
    is stuck on it, and every later request -- including a reload -- hangs until
    it times out. The symptom is a server that logs one 200 and then appears
    dead while still listening.
    """

    allow_reuse_address = True                # no 'address already in use' on restart
    daemon_threads = True                     # ctrl-c should not wait on open sockets


if not os.path.exists(os.path.join(WEB, "dashboard.html")):
    sys.exit(f"no dashboard.html in {WEB} -- run: python build_all.py")

handler = functools.partial(Handler, directory=WEB)
# 127.0.0.1, not 0.0.0.0: this accepts writes, so it should not be on the network
with Reusable(("127.0.0.1", PORT), handler) as httpd:
    print(f"serving {WEB} with caching disabled")
    print(f"  http://localhost:{PORT}/dashboard.html")
    print(f"  POST /api/state -> {os.path.relpath(STATE, ROOT)}  (the Save button)")
    print("  GET  /api/live   -> the ESPN draft as it happens (start it from the snake planner,")
    print("                      or: python serve.py --watch 623238770 --team 11 ; --watch sim rehearses)")
    print("  ctrl-c to stop")
    if WATCH_LEAGUE:
        WATCH.start(WATCH_LEAGUE, WATCH_TEAM)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
