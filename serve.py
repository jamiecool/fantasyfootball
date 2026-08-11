"""Serve cleandata/ with caching turned off.

`python -m http.server` sends Last-Modified but no Cache-Control, so Chrome
applies heuristic caching and an F5 can be answered from memory without ever
asking the server. That means a rebuilt dashboard silently does not appear --
which shows up as features "not working" when in fact an older page is running.

This is the same server with no-store on every response, so F5 always gets what
build_dashboard.py last wrote.

Run:  python serve.py            (then open http://localhost:8000/dashboard.html)
      python serve.py 8080       (if 8000 is taken)
"""
import functools
import http.server
import os
import socketserver
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cleandata")


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):        # one line per request, not three
        sys.stderr.write("  %s\n" % (fmt % args))


class Reusable(socketserver.TCPServer):
    allow_reuse_address = True                # no 'address already in use' on restart


if not os.path.exists(os.path.join(ROOT, "dashboard.html")):
    sys.exit(f"no dashboard.html in {ROOT} -- run: python build_dashboard.py")

handler = functools.partial(NoCache, directory=ROOT)
with Reusable(("", PORT), handler) as httpd:
    print(f"serving {ROOT} with caching disabled")
    print(f"  http://localhost:{PORT}/dashboard.html")
    print("  ctrl-c to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
