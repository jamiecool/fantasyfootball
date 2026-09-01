# Backlog and known gaps

What is worth doing next, and what this dataset cannot answer.

## Analysis backlog

Ordered by expected value, revised after the session's findings:

1. **H2H + playoff-threshold model.** Weekly score distributions → P(top 6) → playoff
   win probability. Replaces season-points maximisation, which is the wrong objective.
   Needs `stats_player_week_YYYY` from nflverse (same release already in use).
2. **Per-player value gap for draft night** — expected points vs expected price, so
   bargains are visible live. Mostly built: `build_2026_board.py` has the prices,
   `compare_roster_shapes.py` has the points curves. Needs joining and a clean output.
3. **Retrodictive VBD valuation** — what each player was *worth* vs paid, all 9 years.
   Still the cleanest way to size this league's total mispricing.
4. **Inflation curve within a draft** — now possible for all 9 seasons via
   `nomination_order`. Note Finding 4 already showed timing doesn't move *value*; this
   would test whether it moves *price*.
5. **D/ST** — rules captured, never built. ~1% of spend.

Done or superseded: positional market drift (`v_position_spend`), stars-and-scrubs test
(Findings 9/10 — shape is near-neutral, bench allocation is not), $/PAR by position
(Findings 6–8).


## Perennial Push (the second league, added 2026-09-01)

1. **Two ESPN data layouts are in flight and need reconciling.** `build_ppp_data.py`
   reads the checked-in `rawdata/ppp/*.psv`. `fetch_espn_league.py` writes
   `rawdata/espn/*.csv` on a different naming scheme, with dated board snapshots and
   `.meta.json` siblings — a better long-term shape. **It has never been run**, so no
   file demonstrates its schema yet. The job: run it with ESPN cookies, diff its output
   against the PSVs to prove they agree, then point `build_ppp_data.py` at `rawdata/espn/`
   and retire `rawdata/ppp/`. Do not do the second half before the first.
2. **`board2026.psv` is frozen at 2026-09-01.** Every projection, ADP and ownership
   figure on the PPP board is that day's snapshot and nothing re-pulls it. The page
   cannot tell you this. Resolved by item 1.
3. ~~No name normaliser between the two leagues.~~ **Measured and closed 2026-09-01.**
   The claimed ~18 mismatches were not real: the repo's `player_key` already folds
   `Jr/III` and punctuation, giving 0 collisions, 206/249 joined to Underdog, and only 3
   unmatched skill players (Najee Harris, Darius Slayton, Jahan Dotson — all deep-round,
   and they fall back to ESPN ADP). `build_board()` raises if a collision ever appears.
4. **PPP's strategy rules live in `build_ppp_data.py`, not `strategy_rules.py`.** They
   are auto-interpolated from measured numbers so they cannot go stale, which is good,
   but it means two files now hold "the rules we act on". Worth unifying if PPP work
   continues.
5. **The QB=2.0 starter assumption is gone from the board, but rule 2 still leans on
   it.** The board no longer needs it — the pick curve measures the superflex effect
   directly. Rule 2's "24 QBs start every week" is still an inference from 33 QBs being
   drafted in 2025, not from lineup data. Checkable: ESPN lineup slot 7 is superflex, so
   five seasons of started-lineup data would settle what actually fills it. Worth doing
   before leaning hard on the QB conclusion, though the pick curve now supports it
   independently.
6. **Underdog is a 1QB best-ball format.** The method only takes within-position
   ordering from it, which is format-agnostic, so this is defensible — but it is an
   assumption, not a measurement. If Underdog's QB-vs-QB ordering is itself distorted by
   1QB scarcity (e.g. rushing QBs valued differently), the superflex board inherits it.
   No way to test this without a superflex ADP source.

## Known gaps

- **No D/ST in `final_ranks`.** Rules are captured (`scoring_rules`), so it's buildable
  from nflverse team stats + game scores, but hasn't been. ~1% of spend.
- **No weekly data** — `final_ranks` is season totals. Any week-level work (consistency,
  playoff-weeks performance, start/sit) needs `stats_player_week_YYYY` from nflverse.
- **52 of the 2025 prices are estimated**, not actual (median error ~$1.75). Filter
  `price_source = 'actual'` for price-sensitive work.
- **Franchise identity across seasons is unresolved and will stay that way** — Jamie
  can't recover the old names. Doesn't matter given the league-wide scope steer.
- **No projections.** All analysis so far is retrodictive. Drafting in 2026 will need
  actual 2026 projections from somewhere.
