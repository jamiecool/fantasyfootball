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

**The name join is fine — the "~18 mismatches" claim was wrong.** The Cowork README
that came with this data said about 18 players were spelled differently from Underdog's
(`James Cook III`, `DJ Moore`, `Kenny Gainwell`). Measured against the repo's own
`player_key`, which already folds `Jr/Sr/III`, strips punctuation and carries an alias
table, the real numbers are:

- **0 collisions** in the ESPN pool — no two different players fold to one key, which is
  the check trap 1 exists to force. `build_board()` raises rather than joining if this
  ever stops being true.
- **206 of 249** join to Underdog ADP.
- **3 skill players** miss: Najee Harris, Darius Slayton, Jahan Dotson — all deep-round
  names Underdog does not rank. They fall back to ESPN's ADP for ordering and the board
  marks them `espn` in its UD column.
- **40** are K/DEF, which Underdog carries none of by design (trap 8), ordered on ESPN's
  own ADP instead.
- **0 position disagreements** among the players that joined.
