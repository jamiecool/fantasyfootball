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
