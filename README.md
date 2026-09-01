# PBAFFL & Perennial Push — draft analysis

Two fantasy leagues, normalised into a queryable database, plus a localhost dashboard
used live during both drafts. A switcher in the page header decides which league every
surface is describing.

**PBAFFL** — nine seasons of a 12-team half-PPR **auction** league. $200 budget, 16
roster spots, starters are 1 QB / 2 RB / 3 WR / 1 TE / 1 K / 1 DEF with **no FLEX**,
half-PPR with a non-default **−2 interceptions**. Strict redraft, and an IR slot that
everyone uses. This is the bulk of the repo.

**Perennial Push for Penultimacy** — five seasons of a 12-team full-PPR **snake**
league on ESPN, 18 rounds, with a **superflex** slot. See `rawdata/ppp/README.md`.

**Almost nothing carries between them.** Different draft format, different scoring,
different roster — so the second league has its own board, its own history and its own
strategy rules rather than reusing any of the auction work. The one thing they share is
the NFL stats and Vegas tabs, which are league-agnostic.

## Get it running

Python 3.11+. Then:

```bash
pip install pandas numpy scikit-learn beautifulsoup4 openpyxl pyarrow
python build_all.py          # rebuilds everything from what is in rawdata/
python serve.py              # http://localhost:8000/dashboard.html
```

`build_all.py` takes about 80 seconds offline. The first run downloads ~80MB of
nflverse stat lines; after that they are cached and skipped.

Every generated artefact is gitignored — the database, the CSVs, the dashboard.
That is deliberate: they are all reproducible from `rawdata/`, and a 4MB HTML file
regenerated on every build is not something two people can share in git.

```bash
python build_all.py --list           # the stages, in order
python build_all.py --refresh        # re-fetch live feeds (ADP, Yahoo, Vegas) first
python build_all.py --from build_dashboard.py   # resume after a failure
```

**Live feeds do not run by default.** ADP moves daily in preseason, and silently
re-fetching mid-analysis makes results irreproducible. Ask for it with `--refresh`.

## What you get on a fresh clone, and what you don't

`build_all.py` reproduces everything except two categories.

**Only the theme is browser-local.** Target stars, per-player notes and draft plans are
SHARED — they live in `shared/board_state.json`, are tracked, and are baked into the page
at build time, so a clone opens on the same view. Press **save for both of us** in the
header to write your edits back, then commit the file.

Unsaved edits sit in `localStorage` and survive a refresh, so nothing is lost if you
close the tab mid-thought. The header button tells you which state you are in. Saving
needs the local server (`python serve.py`) — a static page cannot write to disk, so the
button posts to it. Opened straight off the filesystem, the dashboard still works and
still shows the shared view; it just cannot save.

**One table needs a live fetch.** `vegas_team_week` (weekly betting lines) comes from a
2.1MB nflverse mirror that is not tracked, because it is rewritten wholesale on every
fetch and would conflict constantly. Without it the Vegas tab's "games priced so far"
table is empty; everything else, including the season-long implied totals, works. Fill it
with:

```bash
python build_all.py --refresh
```

Everything else — the database, all 18 other tables, the board, fair prices, dead zones,
55,861 game lines — rebuilds from what is in the repo.

## What is where

| | |
|---|---|
| `rawdata/` | inputs. Nine years of Yahoo exports, plus fetched market data |
| `rawdata/ppp/` | the second league's ESPN pulls, checked in — see its README |
| `cleandata/fantasy.db` | SQLite, the thing to query. **Generated** |
| `cleandata/dashboard.html` | the draft-day tool, both leagues. **Generated** |
| `fetch_*.py` | one per external source |
| `build_*.py` | transforms, in the order `build_all.py` runs them |
| `analyze_*.py` | investigations; each prints its findings and some persist a CSV |
| `strategy_rules.py` | the rules we act on, with evidence and an honest confidence |
| `CLAUDE.md` | project memory — decisions, traps, findings. Read it before analysing |

## The dashboard

Pick a league in the header; the tabs change with it.

**PBAFFL (seven tabs).** **2026 board** is the draft-day surface: expected price, a
market/fair-value toggle, target stars, per-player notes, and colour flags for Vegas
team strength and disagreement with Yahoo. **Past drafts** is nine seasons of every
pick and how it turned out, with a pick-by-pick and a post-draft roster view. **NFL
stats** is 55,861 game lines scored under our rules, with any week range and a player
profile. **Vegas**, **Draft plan** and **Strategy** are what they sound like.

**Perennial Push (five tabs).** **2026 board** ranks by value over replacement for
superflex — no dollar figures, because it is a snake draft. **Past drafts** is five
seasons. **Draft plan** is a snake planner that snakes from your slot and flags picks
where the board says a player will not last. **Strategy** and **Analytics** are derived
from that league's own drafts only. **NFL stats** and **Vegas** are shared with PBAFFL.

The second league's board rests on two corrections to ESPN's numbers, both measured
from five seasons of outcomes: its projections run ~15% high because it assumes every
starter plays 17 games, and its replacement level is projected rather than realised.
The second matters most — ESPN's 24th-best QB projects 239.1 points where the real
five-season figure is 153.7, and in a superflex league that gap is the whole game.

## Where the numbers come from

The board's price is built in two halves, and the split matters:

- **Ordering within a position** is Underdog's. Sharp, best-ball, repriced continuously.
- **Cross-position weighting** is PBAFFL's own price history, 2023–25. Underdog cannot
  supply it — best ball has 18 rounds, a FLEX we do not have, and no K or DEF. RB1 goes
  for $66 here while QB1 goes for $36, and that gap *is* our format.

**No projection enters the price.** Preseason ADP predicts final finish at rho 0.42,
which is roughly the ceiling for anyone; two independent markets agree with each other
at 0.95 while either agrees with a projection model at 0.65–0.72. The model is the
outlier, so it stays out of pricing and lives in analytics only.

## Reading the analysis honestly

Findings carry a confidence set by **sample size**, not by how clean the estimate
looks. Two were retracted early for resting on thin position × tier cells, so anything
under ~25 observations is capped at "low" however tidy it reads, and a claim whose
interval spans the decision boundary cannot carry a recommendation. Rejected rules stay
visible in `strategy_rules.py` so they are not re-adopted by accident.

`CLAUDE.md` has a running list of traps already hit — name-collision joins, thin cells
at the top of the board, hindsight substitution in roster scoring. Worth reading before
adding an analysis, because most of them are easy to hit twice.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — it covers the branch workflow and, more
usefully, which files conflict badly and how the repo is arranged to avoid it.
