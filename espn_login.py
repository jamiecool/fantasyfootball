"""Capture ESPN's login cookies into espn_credentials.json, without typing them by hand.

    python espn_login.py

Opens a real browser window on ESPN's sign-in page. You log in there yourself -- nothing
here sees your password. The moment ESPN sets its two session cookies, espn_s2 and SWID,
they are written to espn_credentials.json (gitignored) and the window closes. Those two
cookies are what the authenticated league-history endpoint wants (2021-2024 drafts and
FAAB transactions); the fetchers already read this file. espn_s2 lasts about a year.

The browser profile lives in the scratch folder below, so a re-run a month later is
usually already signed in and finishes in a second.
"""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "espn_credentials.json")
PROFILE = os.path.join(os.environ.get("LOCALAPPDATA", ROOT), "fantasyfootball-espn-profile")
LOGIN = "https://fantasy.espn.com/football/league?leagueId=623238770"   # a fantasy page is what sets espn_s2
LEAGUE = "https://fantasy.espn.com/football/league?leagueId=623238770"
TIMEOUT = 600                              # seconds to wait for the sign-in


def grab(ctx):
    got = {}
    for c in ctx.cookies():
        if c["name"] in ("espn_s2", "SWID") and "espn.com" in c.get("domain", ""):
            got[c["name"]] = c["value"]
    return got if len(got) == 2 else None


def main():
    with sync_playwright() as p:
        # the machine's own Chrome (channel="chrome"): no Playwright browser download needed,
        # and ESPN's sign-in behaves exactly as it does in your normal browser
        try:
            ctx = p.chromium.launch_persistent_context(PROFILE, channel="chrome", headless=False,
                                                       viewport={"width": 1100, "height": 900})
        except Exception:                                    # noqa: BLE001  -- fall back to Edge, then Playwright's Chromium
            try:
                ctx = p.chromium.launch_persistent_context(PROFILE, channel="msedge", headless=False,
                                                           viewport={"width": 1100, "height": 900})
            except Exception:                                # noqa: BLE001
                ctx = p.chromium.launch_persistent_context(PROFILE, headless=False,
                                                           viewport={"width": 1100, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        creds = grab(ctx)
        if not creds:
            page.goto(LOGIN)
            print("Sign in to ESPN in the window that just opened. Waiting for the session cookies...", flush=True)
            t0 = time.time()
            last = None
            while time.time() - t0 < TIMEOUT:
                time.sleep(2)
                creds = grab(ctx)
                if creds:
                    break
                seen = sorted({c["name"] for c in ctx.cookies() if "espn" in c.get("domain", "")})
                if seen != last:                             # say what ESPN has set so far
                    print("  espn cookies so far:", ", ".join(seen) or "(none)", "| page:", page.url[:80], flush=True)
                    last = seen
        if not creds:
            ctx.close()
            sys.exit("No espn_s2 + SWID cookies appeared within %d seconds." % TIMEOUT)
        # a visit to the league page proves the session is good for the private league
        try:
            page.goto(LEAGUE, timeout=20000)
        except Exception:                                    # noqa: BLE001
            pass
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump({"espn_s2": creds["espn_s2"], "SWID": creds["SWID"],
                       "captured": time.strftime("%Y-%m-%d %H:%M")}, f, indent=1)
        ctx.close()
    print(f"wrote {os.path.relpath(OUT, ROOT)}  (SWID {creds['SWID'][:9]}..., espn_s2 {len(creds['espn_s2'])} chars)")


if __name__ == "__main__":
    main()
