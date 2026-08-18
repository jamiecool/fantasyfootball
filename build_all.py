"""Run the whole pipeline in dependency order. Start here on a fresh clone.

The scripts have a real order and it was previously undocumented, so a clone
would die on a missing CSV with no hint about what to run first. This is that
order, executable.

    python build_all.py              rebuild everything from what is on disk
    python build_all.py --refresh    re-fetch the live feeds first
    python build_all.py --list       show the stages and stop

Generated artefacts are all gitignored, so running this is how a new machine
gets a working dashboard. The one-off historical fetches (nflverse stat lines)
are only pulled if their files are missing -- they are ~80MB and never change.

Live feeds move daily in preseason and are NOT run by default: a rebuild should
be reproducible, and silently re-fetching mid-analysis makes results
irreproducible for the sake of freshness nobody asked for. Use --refresh when
you actually want new numbers.
"""
import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))

# (script, description, is_live_feed, skip_if_this_exists)
STAGES = [
    ("fetch_nflverse.py", "season stat lines, 2017-2025", False,
     "rawdata/nflverse/stats_player_reg_2025.csv"),
    ("fetch_nflverse_weekly.py", "week-by-week stat lines", False,
     "rawdata/nflverse/stats_player_week_2025.csv"),
    ("fetch_nflverse_players.py", "height, weight, birth date, draft slot", False,
     "rawdata/nflverse/players.csv"),
    ("fetch_adp.py", "FFC redraft ADP (K/DEF only these days)", True, None),
    ("fetch_underdog_adp.py", "Underdog ADP -- drives the board's ordering", True, None),
    ("fetch_projections.py", "Sleeper projections (analytics only)", True, None),
    ("fetch_yahoo_adp.py", "Yahoo ADP + auction cost -- the room's anchor", True, None),
    ("fetch_vegas.py", "Vegas implied team totals", True, None),
    ("build_clean_data.py", "rawdata -> cleandata/fantasy.db", False, None),
    ("build_2026_board.py", "prices -> analysis/board_2026.csv", False, None),
    ("analyze_dead_zones.py", "per-band returns -> analysis/dead_zones.csv", False, None),
    ("build_fair_prices.py", "valuations -> analysis/fair_prices_2026.csv", False, None),
    ("build_dashboard.py", "everything -> cleandata/dashboard.html", False, None),
]

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--refresh", action="store_true",
                help="re-fetch live feeds (ADP, Yahoo, Vegas) before building")
ap.add_argument("--list", action="store_true", help="list the stages and exit")
ap.add_argument("--from", dest="start", metavar="SCRIPT",
                help="resume from this stage, e.g. build_dashboard.py")
args = ap.parse_args()

if args.list:
    print("pipeline order:\n")
    for i, (script, desc, live, _) in enumerate(STAGES, 1):
        print(f"  {i:2}. {script:28} {'[live feed] ' if live else ''}{desc}")
    print("\nlive feeds run only with --refresh")
    sys.exit(0)

started = args.start is None
ran, skipped, t0 = [], [], time.time()

for script, desc, live, sentinel in STAGES:
    if not started:
        if script == args.start:
            started = True
        else:
            skipped.append((script, "before --from"))
            continue
    if live and not args.refresh:
        skipped.append((script, "live feed, use --refresh"))
        continue
    if sentinel and os.path.exists(os.path.join(ROOT, sentinel)):
        skipped.append((script, "already downloaded"))
        continue

    print(f"\n{'=' * 74}\n  {script}   {desc}\n{'=' * 74}")
    t = time.time()
    r = subprocess.run([sys.executable, script], cwd=ROOT)
    if r.returncode != 0:
        print(f"\nFAILED at {script} (exit {r.returncode}).")
        print(f"Fix it, then resume with:  python build_all.py --from {script}")
        sys.exit(r.returncode)
    ran.append((script, time.time() - t))

print(f"\n{'=' * 74}\n  done in {time.time() - t0:.0f}s\n{'=' * 74}")
for s, secs in ran:
    print(f"  ran      {s:28} {secs:5.1f}s")
for s, why in skipped:
    print(f"  skipped  {s:28} {why}")

out = os.path.join(ROOT, "cleandata", "dashboard.html")
if os.path.exists(out):
    print(f"\n  {os.path.getsize(out) / 1e6:.1f}MB dashboard ready. Serve it with:")
    print("    python serve.py       ->  http://localhost:8000/dashboard.html")
