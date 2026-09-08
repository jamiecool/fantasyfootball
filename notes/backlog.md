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
   and retire `rawdata/ppp/`. Do not do the second half before the first. **First half
   done for the board on 2026-09-05** (`--board-only`, no cookies needed): 246/248 shared
   ids, 0 name or position disagreements against the 09-01 PSV. History seasons untested.
2. ~~`board2026.psv` is frozen at 2026-09-01.~~ **Refreshable since 2026-09-05:**
   `fetch_espn_league.py --board-only` rewrites it (headerless, same schema) plus a dated
   `snapshots/` copy, and keeps ESPN's top 300 + the first 45 QBs (was 248 with 31 QBs;
   Penix, Cousins and Shedeur Sanders sat past ESPN #427). Still manual — nothing runs it
   on a build — and the page still cannot say how old the pool is.
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

### From the VBD board session, 2026-09-04 (agreed direction, confirm before coding)

`build_ppp_vor_board.py` → `cleandata/analysis/ppp_vor_board.csv` is methodologically
settled; see `notes/log/2026-09-04-jamie.md` for the method and the accepted findings.
Three things were agreed and not done:

7. **Restore the raw elite-QB value.** The log+linear fit gives the QB1 slot 321, but the
   raw first-QB-taken average is 367. Allen should come out around 1.01–1.02, not 1.04.
   Options: blend raw and fitted for ranks 1–3, or fit QB separately with a steeper top.
8. **Add a 4-season sensitivity (2022–25)** so QB5–8 placement shows both answers — rounds
   3–5 on 2023–25, rounds 2–3 once 2022 is in. The board currently reports only the
   pessimistic end without saying so.
~~9. Wire `ppp_vor_board.csv` into the dashboard's PPP board.~~ **Done 2026-09-04** as a
   *pivot* on the existing board (pick curve | value over baseline), not a replacement:
   `build_ppp_vor_board.py` is a `build_all.py` stage, `build_ppp_data.py` joins its rows
   as `vb*` fields, the template toggles the sort and columns. The pick curve stays the
   default and still orders the planner pool. `CLAUDE.md` records the relationship.
10. **The value pivot's baseline is a single fitted point with enormous leverage, and it
   is off the data.** At WR40 the fit says 150; the raw data around that slot says 165–188.
   At RB28 the fit says 154; the data says 128–145. Every shape-free estimate (raw window
   ±1…±8, isotonic) moves WR 17 → 11–15 and RB 13 → 16–22 in the first three rounds. But a
   single baseline slot has a standard error of ~30–53 points on three seasons (RB28
   scored 214, 205, 13), so neither answer is firm. Fix: keep the parametric fit for the
   top of each curve, estimate the baseline from a raw window or isotonic, and add 2022
   (item 8), which halves the standard errors. Not done before the draft on purpose.
11. **The within-QB baseline may be too deep, not too shallow.** QB13–24 score the same as
   QB5–12 (~220) and are available in rounds 7–12, so the QB you realistically get by
   waiting scores ~220, not QB23's 197. Measured against that, early QBs are worth even
   less than the value pivot says. Note only; needs the item-10 fix first.

12. **The Yahoo pivot's fetcher depends on six hard-coded FantasyPros expert IDs**
   (`fetch_yahoo_rankings.py`, `YAHOO_EXPERTS`). Yahoo's article embeds a FantasyPros
   widget filtered to its analysts; if the staff changes, the IDs change and the fetcher
   asserts `total_experts == 6` and stops. Re-derive them from the article's iframe `filters=`.
   Also: no `data_freshness` row yet for this feed — it is a live feed like Underdog's and
   should get the same 3-day staleness check in `build_clean_data.py`.

~~10. `serve.py` drops `xplans`.~~ **Already fixed** (2026-09-02) and verified 2026-09-04:
all four keys round-trip through `write_state()` and `GET /api/state`.

13. **The live draft relay is proven on mocks, not yet on a real draft.** Run one more mock
    on draft morning; if the console's `[relay]` line says "draft websocket opened" rather
    than "draft stream opened", the WebSocket frame format is being exercised for the first
    time — check picks still land. Fallback is manual entry (press stop). Also worth pulling
    `autoDraftTypeId` for 2021–2025 to mark past autopicks.

## Known gaps

- **No D/ST in `final_ranks`.** Rules are captured (`scoring_rules`), so it's buildable
  from nflverse team stats + game scores, but hasn't been. ~1% of spend. **Half done
  2026-09-06:** D/ST *game logs* now exist in `player_weeks` (position `DEF`, 32 teams,
  2017–25, via `fetch_nflverse_team.py`), so the NFL stats tab, player card and team card
  show them under both leagues' scoring. Season ranks (`final_ranks`) still exclude them,
  so a D/ST has no Pos rk and no replacement level. Two judgement calls to revisit if a
  total looks off: TD = `def_tds + special_teams_tds` (nflverse's `fumble_recovery_tds`
  overlaps `def_tds` and was left out); yards allowed = opponent net yards
  (`passing_yards − |sack_yards_lost| + rushing_yards`).
- **No weekly data** — `final_ranks` is season totals. Any week-level work (consistency,
  playoff-weeks performance, start/sit) needs `stats_player_week_YYYY` from nflverse.
- **52 of the 2025 prices are estimated**, not actual (median error ~$1.75). Filter
  `price_source = 'actual'` for price-sensitive work.
- **Franchise identity across seasons is unresolved and will stay that way** — Jamie
  can't recover the old names. Doesn't matter given the league-wide scope steer.
- **No projections.** All analysis so far is retrodictive. Drafting in 2026 will need
  actual 2026 projections from somewhere.
