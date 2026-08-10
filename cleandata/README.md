# cleandata

Normalized PBFFL auction-draft history, 2017–2025. Everything here is **generated** —
rebuild with `python build_clean_data.py` from the repo root. Don't hand-edit these
files; the one exception is `franchise_map.csv` (see below), which is an input.

## What's here

| Path | Use |
| --- | --- |
| `fantasy.db` | **Primary.** SQLite, indexed, with helper views. |
| `csv/*.csv` | Same tables as text — eyeball, diff, drop into Excel. |
| `parquet/*.parquet` | Same tables for fast pandas/Arrow loads. |
| `franchise_map.csv` | **Editable input.** Declares which team names are the same manager. |

```python
import pandas as pd, sqlite3
con = sqlite3.connect("cleandata/fantasy.db")
df  = pd.read_sql("SELECT * FROM draft_picks", con)
```

## Tables

**`draft_picks`** (1,695 rows) — one row per player drafted per season. The fact table.

| Column | Notes |
| --- | --- |
| `season` | 2017–2025 |
| `price` | auction price in dollars |
| `price_rank` | 1 = most expensive that season |
| `price_share` | `price / 200`, i.e. share of a team's budget |
| `player_name`, `player_key` | `player_key` is the cross-season join key (accent- and suffix-folded) |
| `position` | primary position: QB/RB/WR/TE/K/DEF |
| `position_raw` | as recorded, e.g. `QB,TE` for Taysom Hill |
| `nfl_team` | as recorded that season (`OAK` pre-2020) |
| `nfl_franchise` | relocation-normalized (`OAK`→`LV`) — use this to join a club across years |
| `franchise` | fantasy team, resolved via `franchise_map.csv` |
| `team_raw` | the team string exactly as it appeared in the workbook |
| `draft_order` | as recorded; **semantics vary by year** (see caveats) |
| `price_source` | `actual`, or `estimated` for 52 reconstructed 2025 prices |

**`franchise_seasons`** (106) — per team per season: `spend`, `unspent`, `max_bid`, `median_bid`, `pct_on_top3`.
**`seasons`** (9) — league shape per year: teams, picks, total spend.
**`players`** (558) — per player across all years: `seasons_drafted`, `total_spent`, `avg_price`, `max_price`.
**`franchises`** (32) — per franchise label: seasons played, first/last season.
**`final_ranks`** (5,714) — **end-of-season actual results, 2017–2025.** One row per
player per season: `overall_rank`, `pos_rank`, `points` (this league's scoring),
`points_per_game`, `games`, plus `points_std` / `points_ppr` if you want to re-rank
under different settings. Built by `fetch_nflverse.py` + this script from
[nflverse](https://github.com/nflverse/nflverse-data) season stat lines.

**`preseason_adp`** (5,348) — **preseason expectation, 2017–2026.** Two sources, kept
distinct via the `source` column:

- `ffc` (5,098) — historical ADP 2017–2025 from
  [Fantasy Football Calculator](https://fantasyfootballcalculator.com), 12-team, via
  `fetch_adp.py`. All three scoring formats stored.
- `underdog` (250) — **current-season** Underdog best-ball ADP via
  `fetch_underdog_adp.py`, with `prev_adp` and `adp_delta` for movement.

`is_primary = 1` marks the one row per player per season that feeds the ranking;
Underdog wins where present, otherwise the FFC format preference below applies.

⚠️ **`adp_delta = prev_adp − adp`, so positive means the player is RISING** (drafted
earlier than before). Easy to read backwards.

⚠️ **Underdog ADP is best ball, not redraft** — 18 rounds, no waivers, a FLEX this
league lacks, and **no K or DEF**. Treat it as a market signal, not a draft plan.

**`data_freshness`** — which datasets go stale and when. The historical tables never
do; current-season ADP moves daily. Check it at the start of a session:
`SELECT * FROM data_freshness`.

**`preseason_ranks`** (200) — Yahoo's own 2025 preseason top 200 (from `top2025.txt`).
Kept as an independent cross-check on `preseason_adp`; the two agree at rho 0.96.
**`adp_underdog_2021`** (1,341) — bonus UnderDog ADP list found in the 2021 workbook.

### Views

- `v_preseason` — one row per player per season, expectation going in.
- `v_draft_value` — every pick's price against where that player actually finished.
- **`v_player_season`** — the analysis table: preseason rank, final rank, points, and
  what this league paid, all on one row, with `beat_expectation`
  (`preseason_rank - final_rank`). Start here.
- `v_position_spend`, `v_top_buys` — spend by position by season; top 10 buys per season.

## League rulebook

Parsed from your saved Yahoo Scoring & Settings page (`rawdata/scoringrules/`).

**`scoring_rules`** (33) — every scoring rule, by category (Offense / Kickers /
Defense-Special Teams), with `league_value`, `yahoo_default`, and a
`differs_from_default` flag. **Exactly one rule is customised: interceptions are −2,
not Yahoo's −1 default.**
**`league_settings`** (37) — league ID, name (PBAFFL), 12 teams, head-to-head,
FAB waivers, 6-team playoffs weeks 15–17, fractional and negative points on.
**`roster_slots`** (8) — 9 starters (1 QB, 3 WR, 2 RB, 1 TE, 1 K, 1 DEF), no FLEX,
plus 7 bench and 1 IR. Matches the 16 draft picks per team.

These are not just documentation — `scoring_rules` **drives** the points calculation
in `final_ranks`. `PPR_RATE` and the kicker FG bands are read from the parsed table,
so there is no second hardcoded copy to drift.

The rulebook independently confirmed the half-PPR inference (`Receptions: .5`), and
verifying nflverse's `fantasy_points` against it showed an exact match on every
offensive rule — including this league's −2 interception override, which nflverse
also uses. Re-validation after wiring the rules in: still rho 0.9999 vs Yahoo.

## Preseason ADP: how the format is chosen

Your league is half-PPR, but FFC publishes a different, partly-overlapping player set
per format — 2022 half-PPR lists only 124 players while standard lists 195, and 2017
has no half-PPR at all. Rank orderings agree across formats at rho 0.94–0.99, so each
player's ADP is taken from the most league-appropriate format that lists them
(half-PPR → PPR → standard) and the merged set is then ranked.

That lifts draft-pick coverage from 71% to 94% in the worst season, 95.5% overall,
without giving up half-PPR where it exists. Every row keeps its `scoring_format`, and
all three formats stay in `preseason_adp` if you'd rather rank one strictly.

## Scoring: half-PPR (0.5 per reception)

Not assumed — inferred. Your `finalrosters.mhtml` carries Yahoo's own "2025 Final
Rank" per player, computed under your real league settings. Scoring 2025 three ways
and rank-correlating against it gave:

| scoring | Spearman vs Yahoo |
| --- | --- |
| standard (0 PPR) | 0.9732 |
| **half-PPR** | **0.9999** |
| full PPR | 0.9824 |

Kickers are scored Yahoo-style from FG distance buckets (0–39 = 3, 40–49 = 4, 50+ = 5,
PAT = 1), since nflverse's `fantasy_points` excludes kicking entirely.

If your league's settings ever change, edit `PPR_RATE` in `build_clean_data.py` and rebuild.

## Franchise identity — deliberately left partial

Managers rename their teams between seasons, and Yahoo truncates long names
(`Pooky and the Pum...`). Truncation was resolved automatically by prefix matching;
genuine renames can't be, and the original mapping is no longer recoverable. So
there are 32 labels across 9 seasons for what is really ~12–15 managers.

**This was a deliberate call, not an outstanding gap** — the analysis this dataset is
for is league-wide, and none of it depends on franchise identity.

What is still fully valid:

- **All league-wide work** — positional spend, price curves, ADP-vs-outcome, market
  inefficiency, inflation. None of it groups by franchise.
- **Any single-season franchise analysis** — team names are correct *within* a season,
  so per-team spend, roster construction, and strategy in a given year are reliable.
- **Five franchises that are stable across all nine years** — All up to Luck, Banks,
  Daniel's Dandy Team, Jamie's Team, Kempton's Alt Right. Multi-year analysis
  restricted to these is sound.

What is not valid: multi-season trends grouped by `franchise` across the other labels,
because one manager may appear under several. `franchise_seasons` is per season and
therefore fine; it's only cross-season grouping that breaks.

`franchise_map.csv` is still generated and still honoured if anyone ever fills in the
`manager` column, but nothing depends on it.

## Caveats

- **2020 was a 10-team season** (160 picks). Every other year is 12 teams / 192 picks.
  Normalize by `price_share`, not raw dollars, when comparing across years.
- **52 of the 2025 prices are estimated**, not actual — those players were drafted
  then dropped, so Yahoo no longer had the price. Filter on
  `price_source = 'actual'` for anything price-sensitive. Hold-out testing put the
  median error at ~$1.75. 2025 also has 191 picks, not 192: one draft slot was empty.
- **`draft_order` is not comparable across years.** 2017–2022 record a single
  nomination/pick number, 2024 records slot/round/pick, and 2023 records a
  spreadsheet sort order. Use `price_rank` for cross-year work.
- **The $200 budget is inferred**, not stated in any source. It's consistent with
  every season (no team exceeds it; several land within a dollar or two).
- **Defenses are keyed by NFL team**, not name: 2017–24 use city (`Los Angeles`),
  2025 uses nickname (`Broncos`), and two clubs can share a city. They normalize to
  `LAR DEF` / `def_lar` etc. so they join across seasons.
- **`final_ranks` has no D/ST.** nflverse publishes no team-defense fantasy dataset.
  The full D/ST rules are now in `scoring_rules` (sack 1, INT 2, fumble recovery 2,
  TD 6, safety 2, block 2, plus points-allowed tiers from +10 down to −4), so it is
  now buildable from team stats and game scores — but it hasn't been built. D/ST is
  ~1% of league spend. Ask if you want it.
- **18 draft picks have no final rank** (`final_rank IS NULL` in `v_draft_value`).
  These are correct, not join failures: each player missed his entire season —
  Le'Veon Bell's 2018 holdout, Gronkowski's 2022 retirement, Watson inactive in 2021,
  the rest season-ending injuries. Treat NULL as "drafted, never played." Overall
  98.9% of QB/RB/WR/TE/K picks join to a final rank.
- **Eight player-name aliases** are applied so the same human joins across sources —
  e.g. nflverse backdates Robby Anderson to his post-2022 legal name "Robbie Chosen".
  See `PLAYER_ALIASES` in `build_clean_data.py`; each was verified by hand.
- **Name collisions between different players are resolved by points.** WR Michael
  Thomas and DB Michael Thomas both played 2017–22; so did QB and CB Lamar Jackson.
  Since `player_key` is just a folded name, `final_ranks` keeps only the
  higher-scoring player per key (14 such collisions). Left unhandled, the join
  silently returned the 0-point defender — Michael Thomas' record-setting 2019
  showed up as "finished 589th".
- **~5% of skill-position picks have no preseason rank.** These are players drafted
  outside FFC's published list (deep sleepers, late-breaking rookies). NULL means
  "went undrafted in the public market," which is itself signal for an auction league.

## Repairs applied to source data

Both are logged on every run:

- **2023** — one row's team cell contained the stray text `u`. Jamie's Team had 15
  picks and every other team had 16, so the row was assigned there.
- **2025** — an empty draft slot had been parsed as a player named `--empty--`; dropped.
