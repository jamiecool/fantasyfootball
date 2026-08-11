# PBAFFL — auction draft analysis

Nine seasons of a 12-team half-PPR **auction** league, normalised into a queryable
database, plus a localhost dashboard used live during the draft.

The league: $200 budget, 16 roster spots, starters are 1 QB / 2 RB / 3 WR / 1 TE /
1 K / 1 DEF with **no FLEX**, half-PPR with a non-default **−2 interceptions**.
Strict redraft, and an IR slot that everyone uses.

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

**Browser-local, and it never leaves your machine.** The dashboard keeps these in
`localStorage`, so they are per-person and per-browser by design — target stars, per-player
notes, saved draft plans, and the light/dark choice. There is no sync and no export;
two people keep their own. Clearing site data loses them.

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
| `cleandata/fantasy.db` | SQLite, the thing to query. **Generated** |
| `cleandata/dashboard.html` | the draft-day tool. **Generated** |
| `fetch_*.py` | one per external source |
| `build_*.py` | transforms, in the order `build_all.py` runs them |
| `analyze_*.py` | investigations; each prints its findings and some persist a CSV |
| `strategy_rules.py` | the rules we act on, with evidence and an honest confidence |
| `CLAUDE.md` | project memory — decisions, traps, findings. Read it before analysing |

## The dashboard

Six tabs. **2026 board** is the draft-day surface: expected price, a market/fair-value
toggle, target stars, per-player notes, and colour flags for Vegas team strength and
disagreement with Yahoo. **Past drafts** is nine seasons of every pick and how it
turned out. **NFL stats** is 55,861 game lines scored under our rules, with any week
range and a player profile. **Vegas**, **Draft plan** and **Strategy** are what they
sound like.

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
