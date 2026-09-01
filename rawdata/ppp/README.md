# Perennial Push — ESPN league 623238770

The second league on the dashboard. **Snake draft, superflex, full PPR, 18 rounds,
12 teams** — almost nothing about PBAFFL's auction analysis carries over, which is
why it gets its own board, its own history and its own strategy rules rather than
reusing any of it.

`build_ppp_data.py` turns everything here into `cleandata/analysis/ppp_data.json`,
which `build_dashboard.py` folds into the page as `D["ppp"]`.

## Why these are checked in rather than fetched

Unlike every other source in `rawdata/`, there is **no fetch script for this one**.
The pulls were done once in an ephemeral container during a Cowork session
(2026-09-01) and the results committed. Two reasons it stayed that way:

1. **2021–2024 need an authenticated ESPN session.** The historical endpoint only
   answers with `espn_s2` + `SWID` cookies, which are personal and expire. Those
   go in `espn_credentials.json`, which is gitignored.
2. **These five seasons are closed.** Historical drafts never change, so a fetcher
   that re-pulls them on every build would be network cost for a guaranteed
   identical answer.

What *does* go stale is `board2026.psv` — see below.

## Files

| | |
|---|---|
| `draft2021..2025.psv` | pick-by-pick, with actual + projected points under league rules |
| `teams.psv` | `season\|teamId\|name\|abbrev\|owner\|w\|l\|pf\|seed\|finish`, including 2026 rosters |
| `board2026.psv` | the 2026 board: `pid\|name\|pos\|proTeam\|espnRank\|adp\|own\|proj` |
| `league.json` | scoring, roster slots, superflex flag, per-season team counts |
| `snapshots/` | dated board pulls, `espn_board_YYYY-MM-DD.psv` |

`draft*.psv` schema: `overall|round|pick|teamId|playerId|keeper|name|pos|actual|proj|gp`

## Reproducing a pull, if someone writes the fetcher

- **2021–2024** — authenticated, via the league-history endpoint:
  `/apis/v3/games/ffl/leagueHistory/623238770?seasonId=YYYY`
- **2025–2026** — public:
  `/seasons/YYYY/segments/0/leagues/623238770`
- **Names and points** — `view=kona_player_info` with an `x-fantasy-filter` header of
  `{"players":{"filterIds":{"value":[ids]}}}`, in batches of about 40.
- **Superflex is ESPN lineup slot 7.**

## Two things to know before trusting a number here

**`board2026.psv` is a dated snapshot, not a live feed.** It was pulled 2026-09-01
and nothing re-pulls it. Every projection, ADP and ownership figure on the Perennial
Push board is frozen at that date. The dashboard cannot tell you this — check
`snapshots/` for what is actually current before drafting off it.

**There is no name normaliser.** About 18 players are spelled differently here than
in Underdog's data — `James Cook III` vs `James Cook`, `DJ Moore` vs `D.J. Moore`,
`Kenny Gainwell` vs `Kenneth Gainwell`. Nothing joins the two leagues' player
tables today, so this costs nothing yet. It would be the first thing to fix if
anyone ever wants to compare a player across both boards. See trap 1 in `CLAUDE.md`
— name joins in this repo have burned us before.
