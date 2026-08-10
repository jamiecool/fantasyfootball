# PBAFFL auction draft analysis

Nine seasons (2017–2025) of a 12-team **auction** fantasy football league,
normalized into a queryable database and analysed for league-specific market
inefficiencies.

The premise: player rankings are a solved problem with far more investment behind
them than a side project can add. What *isn't* solved is (a) one specific league's
own pricing history and (b) auction drafts generally, which get a small fraction of
the community attention snake drafts do. That's where the edge is.

## Quick start

```bash
pip install pandas numpy beautifulsoup4 lxml openpyxl pyarrow

python build_clean_data.py      # rawdata/ -> cleandata/fantasy.db  (offline)
python analyze_price_value.py   # what a dollar bought, by position and tier
python analyze_upside.py        # where league-winning seasons come from
```

`build_clean_data.py` needs no network — everything it reads is in `rawdata/`. The
three `fetch_*.py` scripts refresh those inputs and *do* hit the network.

```python
import pandas as pd, sqlite3
con = sqlite3.connect("cleandata/fantasy.db")
pd.read_sql("SELECT * FROM v_player_season WHERE season = 2025", con)
```

## What's in the database

| table | rows | what it is |
| --- | --- | --- |
| `draft_picks` | 1,695 | every pick, 2017–2025: price, position, fantasy team, **nomination order** |
| `final_ranks` | 5,700 | end-of-season results scored under this league's exact rules |
| `preseason_adp` | 5,348 | market expectation going in (FFC 2017–25, Underdog current) |
| `scoring_rules` / `league_settings` / `roster_slots` | 33 / 36 / 8 | the league rulebook, parsed |
| `standings` | 12 | season outcomes (2025 only — Yahoo doesn't expose earlier) |
| `franchise_seasons`, `players`, `seasons`, `franchises` | — | rollups |

Key views: **`v_player_season`** (expectation vs outcome vs price paid, one row per
player-season), `v_draft_value`, `v_preseason`, `v_position_spend`, `v_season_outcome`.

Full schema and caveats: [`cleandata/README.md`](cleandata/README.md).

## Method notes

- **Scoring is the league's own**, not a generic preset: half-PPR with a non-default
  −2 per interception. Verified two ways — parsed from the league rulebook, and
  independently inferred by scoring three ways and correlating against Yahoo's own
  published final ranks (half-PPR won at rho **0.9999**).
- **Fantasy points are computed from raw NFL stat lines**
  ([nflverse](https://github.com/nflverse/nflverse-data)), not scraped from anyone's
  rankings — a published ranking bakes in whoever's scoring settings produced it.
- **Prices for 52 of the 2025 picks are reconstructed**, not observed: those players
  were drafted then dropped, so Yahoo no longer stored the price. They were recovered
  from a rank/price curve plus the per-team budget identity, and hold-out tested at a
  median error of ~$1.75. Flagged as `price_source = 'estimated'` throughout.

## Selected findings

Scoring under this league's rules, over 1,695 picks:

**Elite production at WR and RB cannot be bought cheaply.** In nine seasons, the 154
wide receivers bought at $1–2 and the 94 bought at $3–5 produced **zero** top-3 WR
seasons between them. RB is nearly as stark. The reverse holds at TE and QB — a $6–10
TE finished top-3 nineteen percent of the time.

**Points above replacement per dollar:** K 4.86 · QB 2.74 · TE 2.14 · WR 1.65 · **RB
1.38**. RB is the worst return at every tier, and mid-tier RB ($11–20) is the single
worst place to put money in the draft — while the league drafts **2.42 RBs per RB
slot**, more than any other position.

**Two useful nulls:** budget concentration doesn't predict roster quality
(r = +0.02 over 106 team-seasons), and nomination timing doesn't move value
(±1.5%). So neither "stars and scrubs vs balanced" nor draft-phase timing is where
the edge lives — cross-position allocation is.

## Layout

```
rawdata/            source documents, committed for provenance
  historicalresults/  nine Yahoo draft workbooks, one shape each
  2025rawhtml/        saved Yahoo pages for the 2025 price reconstruction
  nflverse/           season stat lines 2017-2025
  adp/ underdog/      preseason market data
  scoringrules/       the league's Scoring & Settings page
  standings/          season outcomes (hand-entered)
cleandata/          generated; rebuild with build_clean_data.py
CLAUDE.md           working context: decisions, findings, and traps already hit
```

`CLAUDE.md` is the project's working memory — worth reading before extending any of
this, particularly the "traps already hit" section.
