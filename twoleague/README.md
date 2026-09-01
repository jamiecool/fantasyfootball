> ## ⚠ SUPERSEDED — frozen archive, do not build from this
>
> Everything here was folded into the real pipeline on 2026-09-01. **Nothing in this
> folder is read by any build.** It is kept only as provenance and for the six
> league-history analysis scripts in `ppp/`, whose results are baked into the eight
> strategy rules.
>
> The live versions:
>
> | this folder | now lives in |
> |---|---|
> | `ppp/*.psv`, `ppp/league.json` | **`rawdata/ppp/`** — edit there, not here |
> | `ppp/build_data.py` | **`build_ppp_data.py`** (a pipeline stage) |
> | `patch1/2/3.py` | folded into **`dashboard_template.html`** |
> | `ppp/ppp_data.json` | generated to `cleandata/analysis/` — not tracked |
>
> The PSVs below are therefore a **duplicate copy** of `rawdata/ppp/`. If the two ever
> disagree, `rawdata/ppp/` is the one the dashboard is built from. See trap 11 in
> `CLAUDE.md` for why the patch-on-artifact approach was replaced.

# Two-league report — build sources (from a Cowork session, 2026-09-01)

These are the sources for the Perennial Push (ESPN, snake/superflex) league that was
added to the dashboard. Everything here was built in an ephemeral cloud container and
is checked in so it is not lost. NONE of it is wired into build_all.py yet.

## What produced cleandata/draft2026.html

    report_v2.html                     <- the published Hub v2, i.e. build_dashboard.py output
      + patch1.py                      markup: league selector, tabs, PPP panels, CSS
      + patch2.py                      JS: league state, PPP renderers, snake planner
      + patch3.py                      JS/markup: post-draft roster sub-view (both leagues)
    = draft2026.html

patch3b.py and planjs.py are edit-scripts that rewrite patch3.py / patch2.py in place;
they were iteration tools, not part of the build. Run order is patch1 -> patch2 -> patch3.

This is a PATCH-ON-ARTIFACT pipeline, which is the wrong shape. To survive a rebuild
the three patches need folding into build_dashboard.py (or a sibling that imports it)
so the two-league report becomes a build output like dashboard.html.

## ppp/  — Perennial Push data (ESPN league 623238770)

    draft2021..2025.psv   pick-by-pick, with actual + projected points under league rules
                          schema: overall|round|pick|teamId|playerId|keeper|name|pos|actual|proj|gp
    teams.psv             season|teamId|name|abbrev|owner|w|l|pf|seed|finish  (incl. 2026 rosters)
    board2026.psv         2026 board: pid|name|pos|proTeam|espnRank|adp|own|proj
    league.json           scoring, roster slots, superflex flag, per-season team counts
    build_data.py         -> ppp_data.json (the blob patch1 injects). Run this first.
    analyze.py analyze2.py hist.py hist2.py hist3.py    the league-history analysis
    snapshots/            dated ESPN board pulls (espn_board_YYYY-MM-DD.psv)

Source: ESPN. 2021-2024 need an authenticated session and the leagueHistory endpoint
(/apis/v3/games/ffl/leagueHistory/623238770?seasonId=YYYY); 2025-2026 are public under
/seasons/YYYY/segments/0/leagues/623238770. Player names/points come from
view=kona_player_info with an x-fantasy-filter of {"players":{"filterIds":{"value":[ids]}}}
in batches of ~40. Superflex is ESPN lineup slot 7.

## underdog/

    ud_2026-08-25_to_2026-09-01.psv    name|pos|adp_aug25|adp_sep1|change

Pulled from 4for4's Shiny app (apps.4for4.com/UD_ADP/, public, no login). NOTE: this is
a SECOND source alongside fetch_underdog_adp.py's Sharp Football table, and the two use
OPPOSITE sign conventions:
    Sharp  adp_delta = prev - current   -> POSITIVE = rising
    4for4  ADP Change = current - prev  -> NEGATIVE = rising
Do not merge them without normalising. Prefer the existing Sharp pipeline; it already
carries prev + delta as columns.

## Known gaps

- xplans (the snake draft planner's state) is dropped by serve.py's write_state(),
  which only persists targets/notes/plans. PPP plans live in localStorage only.
- ppp/ has no name normaliser; ~18 players differ from Underdog's short names
  (James Cook III vs James Cook, DJ Moore vs D.J. Moore, Kenny Gainwell vs Kenneth
  Gainwell, and similar).
- The published Hub copy is version 7. Hub publishing is currently disabled org-wide
  (enabledFeatures.publishing = false), so local is the only path right now.
