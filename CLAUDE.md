# PBAFFL — auction draft analysis

Working context for a multi-week project (Aug 2026), to be picked up again next year.
This file is the durable memory: decisions, traps, findings, and reference material.
Keep it current — append findings as they're established, and correct entries that
turn out to be wrong rather than leaving both versions.

## ⚠ First thing each session: check ADP freshness

Current-season ADP moves daily through the preseason. Everything else here is
historical and never goes stale.

```bash
python -c "import sqlite3;print(*sqlite3.connect('cleandata/fantasy.db').execute('SELECT dataset,as_of,fetched_on,stale_after_days FROM data_freshness'),sep='\n')"
```

**If the Underdog row's `fetched_on` is more than 3 days ago, say so and offer to
refresh before doing any analysis that uses 2026 ADP:**

```bash
python fetch_underdog_adp.py && python build_clean_data.py
```

Don't refresh silently mid-analysis — ADP shifting underneath a comparison makes
results irreproducible. Mention it, refresh, then proceed.

## The project

Jamie plays in **PBAFFL** (Yahoo league 792831), a 12-team **auction** league he's been
in since 2017. Goal: use nine years of league history plus market data to prepare for
the 2026 draft, via analysis and simulation.

**Scope steer (2026-08, from Jamie):** interested in **league-wide changes over time**,
not individual manager patterns. Don't build per-manager analysis.

## League dynamics (from Jamie, 2026-08)

- **Strict redraft.** No keepers, so prices are comparable across years without adjustment.
- **2020 was 10 teams because two managers left** — a real contraction, not a data
  artifact. Comparable once normalised by `price_share`.
- **Skill is uneven: ~4 sharks, 4 decent, 4 scrubs.** This matters a lot. The league is
  *not* an efficient market, so observed prices are a noisy blend of sharp and soft
  bidding — don't treat league price as consensus value. It also means roughly a third
  of the field is beatable by process alone.
- **IR stays for now** (Jamie proposed removing it; unresolved). So the thin-wire
  finding below holds for 2026 planning.
- **Nomination is unstructured** — anyone can nominate anyone, so order is close to
  random: "it'll go from a kicker to the most expensive player and back to a kicker."
  Confirmed in the data (2025 had three kickers in the first seven nominations).
- **FAB waiver budget is $100/team** (from 2025 standings; max remaining was $100).

## Rebuilding the data

```bash
python fetch_nflverse.py      # season stat lines 2017-2025 -> rawdata/nflverse/  (network)
python fetch_adp.py           # historical ADP 2017-2025    -> rawdata/adp/       (network)
python fetch_underdog_adp.py  # CURRENT-season Underdog ADP -> rawdata/underdog/  (network)
python build_clean_data.py    # everything -> cleandata/fantasy.db + csv/ + parquet/
```

The two historical fetchers skip files already present, so the normal loop is just
`build_clean_data.py`. `fetch_underdog_adp.py` always re-fetches — that's the point —
and needs `SEASON` bumped each year. It is fully deterministic and safe to re-run; it rewrites the DB
from scratch each time. `build_draft.py` (in `rawdata/2025rawhtml/`) is a one-off that
reconstructed the 2025 prices and is not part of the pipeline.

Read `cleandata/README.md` for the schema. Don't hand-edit anything in `cleandata/`.

## League rules that actually matter

All in the DB (`scoring_rules`, `league_settings`, `roster_slots`), parsed from Yahoo.

- **Half-PPR** (0.5/reception). Confirmed in the rulebook *and* independently inferred
  from Yahoo's own final ranks at rho 0.9999.
- **Only one non-default rule: interceptions are −2, not Yahoo's −1.**
- **$200 budget per team, 12 teams, 16 draft slots.** ($200 is inferred, not stated —
  consistent with all 9 seasons.)
- **Starters: 1 QB, 3 WR, 2 RB, 1 TE, 1 K, 1 DEF — no FLEX.** Plus 7 bench, 1 IR.
  The absent FLEX is analytically significant: it makes replacement level exact
  (below) and raises the value of WR depth relative to a flex league.
- Head-to-head, 6-team playoffs weeks 15–17, FAB waivers, fractional + negative points.
- 2020 was a **10-team** season (160 picks). Every other year is 12 teams / 192.

### Replacement levels (derived, exact — no FLEX means no ambiguity)

Starter demand = teams × slots, so the last starter is:

| Pos | Replacement | 2025 pts | 9-yr range |
| --- | --- | --- | --- |
| QB | QB12 | 271.9 | 255–333 |
| RB | RB24 | 169.3 | 149–177 |
| WR | WR36 | 137.9 | 130–161 |
| TE | TE12 | 136.1 | 104–136 |
| K | K12 | 144.0 | 126–146 |

(2020 uses 10 teams.) Query `final_ranks` by `pos_rank` to recompute.

## Traps already hit — don't repeat these

Each of these silently produced plausible-but-wrong output before being caught:

1. **Name-collision joins.** `player_key` is a folded name, and different players share
   names — WR *and* DB Michael Thomas, QB *and* CB Lamar Jackson (14 collisions).
   Unhandled, Michael Thomas' record 2019 read as "finished 589th". `final_ranks` now
   keeps the higher-scoring player per key. **Any new join on a name needs this check.**
2. **Regex HTML parsing.** Early parsers silently dropped rows whose `<td>` carried an
   extra `id` attribute. Use BeautifulSoup, and always assert row counts.
3. **Trusting a fetched page's numbers.** FantasyData served 2025 data when asked for
   2024. Caught only because McCaffrey's point total contradicted his known injury
   season. **Sanity-check fetched data against something you already know.**
4. **nflverse retroactive renames.** Robby Anderson is "Robbie Chosen" in all seasons,
   which broke four years of joins. See `PLAYER_ALIASES`.
5. **Raw overall rank flatters QBs.** See the open question below — this one is still
   live and is the biggest analytical trap in the dataset.
6. Pro-Football-Reference returns **403** to automated fetches. nflverse instead.
7. **`adp_delta` sign is `prev_adp − adp`, so POSITIVE = rising** (being drafted
   earlier). It reads backwards at a glance and was mislabelled once already.
8. **Underdog ADP is best ball, not redraft.** 18 rounds, no waivers, a FLEX this
   league doesn't have, and **no K or DEF at all**. Good market signal, wrong shape
   for a drafting plan — don't feed it into a PBAFFL lineup simulation unadjusted.

## What Jamie actually wants out of this

Stated 2026-08. **Not** player rankings — that's a solved problem with far more
investment behind it than we can add. The edge is in **this league's own data**:

- Where value sits **by position and by price tier** in PBAFFL specifically.
- **Auction-specific structure.** Auctions are uncommon, so far less community effort
  has gone into "solving" them than snake drafts, and an auction permits roster shapes
  a snake draft cannot. That's where the exploitable room is.
- Output: eventually **a draft board.**

### The IR / thin-waiver effect — CONFIRMED, and it overturns the received wisdom

Jamie's read: the IR slot is always used, so the waiver wire stays bare, so drafted
players matter more than usual and "$1 scrubs + stream the wire" is unreliable.

The settings show the mechanism: **IR is a 17th roster spot**, injured players can be
added from waivers *directly* to IR, and there is **no acquisition cap**. So the league
holds 12 × 17 = **204 players against a 192-player draft**. The wire is structurally
drained. (Jamie has proposed removing IR; unresolved as of 2026.)

The data agrees. 2025 end-of-season rosters:

| | share of roster spots | share of points | startable rate |
| --- | --- | --- | --- |
| drafted & kept | 71.4% | 80.3% | 55.7% |
| acquired in-season | 28.6% | **19.7%** | **21.4%** |

And across all 9 years, whether a pick returned a startable season (top-12 QB / 24 RB /
36 WR / 12 TE) by price tier:

| tier | n | startable | bust | median pts |
| --- | --- | --- | --- | --- |
| $1–2 | 422 | **21.6%** | 46.7% | 95 |
| $3–5 | 247 | 30.8% | 33.6% | 118 |
| $6–10 | 212 | 42.5% | 25.5% | 139 |
| $11–20 | 213 | 52.6% | 19.7% | 160 |
| $21–35 | 186 | 66.1% | 11.3% | 177 |
| $36+ | 184 | **81.5%** | 7.6% | 213 |

**This is the key league-specific result:** the 40,000-draft study says stars-and-scrubs
wins because $1–2 players and the waiver wire backfill the roster. In PBAFFL a $1–2 pick
is startable **21.6%** of the time and a waiver add **21.4%** — so the backfill this
league can actually expect is roughly *one in five*, not the deeper pool that research
assumes. **Treat the published stars-and-scrubs conclusion as not transferable here
until tested against real league outcomes.**

Caveat to respect: "drafted & kept" is survivorship-biased (kept *because* good). The
honest, unbiased number is the price-tier table, which covers every pick.

### $1–2 picks split hard by position

| pos | n | startable |
| --- | --- | --- |
| QB | 70 | **42.9%** |
| TE | 66 | 34.8% |
| WR | 154 | 15.6% |
| RB | 132 | **10.6%** |

A cheap RB almost never works; a cheap QB works four times as often. This reframes the
QB finding: the edge is **not** that QBs are undervalued in PAR terms (they aren't —
QB1 is only +93 over QB12). It's **roster-slot efficiency** — you can fill 1 of 9
starting slots for $1–2 with a ~43% hit rate, versus ~11% trying the same at RB. Cheap
QB frees budget; cheap RB just loses the slot.

### Nomination order recovered for all 9 seasons — the auction-specific unlock

`draft_picks.nomination_order` is the **chronological sequence** in which players were
put up for bid, 1..192, for every season. This is genuinely rare data and it's where
the auction-specific edge lives, since nobody has "solved" auctions the way snake
drafts are solved.

How we know it's chronological and not a rank: its Spearman correlation with
`price_rank` is 0.53–0.80 across seasons — neither 0 (random) nor 1 (a rank). Expensive
players *tend* to go earlier, with heavy noise from junk nominations. 2025 opens:
CeeDee Lamb $52, **Ka'imi Fairbairn (K) $1**, Drake London $34, Kaleb Johnson $7,
Bijan $62, then two more kickers.

Two seasons had to be repaired to get this: **2024** was using `Pick #` (correlation
1.000 — a price rank); the real sequence is the `Slot` column (0.767). **2025** came
from Jamie's price-sorted reconstruction, so the sequence was recovered from
`draftresults.html`, which stores it as 16 nomination rounds of 12.

Enables: inflation over draft time, whether early nominations run hot, whether burning
nominations on kickers early is exploitable, and price-vs-value by draft phase.

## Season outcomes — `standings`

**The dependent variable.** Hand-entered from Yahoo standings pages into
`rawdata/standings/standings_YYYY.csv`; add a file per season and rebuild. Currently
**2025 only** — Jamie believes Yahoo may not expose earlier seasons (unverified; the
season dropdown on the standings page is the place to check). Jamie's Team won 2024.

Joined to draft shape in **`v_season_outcome`**.

⚠️ **Use `points_for`, not `rank`, as the skill measure.** 2025's champion (Kempton's
Alt Right) had the **8th-best** points_for of 12. A 6-team playoff over 3 weeks is
mostly variance; season points is the far less noisy signal.

Yahoo does **not** expose earlier standings: the season control on that page is a view
selector (Standings / Projections / Power Rankings), not a year picker. Checked and
ruled out 2026-08. Assume 2025 is the only season with real standings unless Jamie
finds another route.

2025-only signals (n=12): `corr(pct_on_top3, points_for) = -0.30`,
`corr(moves, points_for) = +0.52`. **The first of these is superseded — see below.**

## Drafted-lineup points — the outcome variable that needs no standings

Standings aren't required to measure **draft quality**. For every team-season we can
compute the best legal starting lineup from *drafted players only*, using
`final_ranks` season points: 1 QB, 3 WR, 2 RB, 1 TE, 1 K. That yields **106
team-seasons** across 2017–2025 instead of one, and it isolates drafting from
in-season management — which is what a draft board is actually trying to improve.

(Limitations: season totals, so it ignores weekly variance, bye weeks and *when*
injuries hit; DEF is absent, so it covers 8 of 9 starting slots.)

### FINDING: budget concentration does NOT predict draft quality

`corr(pct_on_top3, drafted-lineup points)`:

| pooled (n=106) | season-normalised | per-season range |
| --- | --- | --- |
| **+0.02** | **−0.02** | −0.66 (2017) to +0.32 (2022) |

Essentially zero. **Stars-and-scrubs versus balanced is a wash in this league** on
draft quality. The per-season range also shows exactly why the 2025-only −0.30 was
untrustworthy: single seasons of 12 swing from −0.66 to +0.32 on pure noise.

**Implication, and it points straight at the goal:** the lever is not the *shape* of
spending but *which players* you buy at *which prices* — i.e. value per dollar. That is
precisely what a draft board encodes, and it raises the priority of the retrodictive
VBD valuation over any roster-construction rule.

## Findings so far

Established:

- **Positional spend has drifted hard.** RB fell 48.6% of league spend (2020) → 35.8%
  (2024); WR rose to 47.7%; QB roughly doubled 4.1% → ~9%. Query `v_position_spend`.
- **Cheap QBs repeatedly finish top-5 overall.** Mahomes $1 (2018, ADP 123) → overall
  #1. Josh Allen $3 → #1. Herbert $5 → #2. Drake Maye $1 (2025) → #3. The public
  market missed these too, so it's a market-wide misprice, not just a league blind spot.
- **Busts are almost entirely early-season injuries**, not talent misreads — David
  Johnson (wk1), Saquon (wk2), Chubb (wk2), McCaffrey (wk4). Relevant to how much
  risk-adjustment is worth modelling.

### Open question — resolve before acting on the QB finding

Raw overall rank **overstates QB value in a 1-QB league**. 2025 PAR of each positional #1:

- RB1 **+196** over RB24 · WR1 **+173** over WR36 · TE1 **+117** · QB1 only **+93** over QB12

Because QB replacement level is so high (271.9), a QB scoring 365 is worth far less
above replacement than his overall rank suggests. So the honest framing is not "QBs are
underpriced" but **"$1 for +93 PAR is excellent value per dollar"** — the edge is real
but smaller than raw rank implies. Confirm with **$/PAR by position by season** before
building any recommendation on it. Note the 40k-simulation study below also found
adding an elite QB to stars-and-scrubs *did not* help.

## Auction theory reference

Researched 2026-08; sources at the bottom. Recorded so we can **test these claims
against nine years of actual league data** rather than take them on faith.

### Value-based drafting (VBD) → dollar values

The standard pipeline, and what we should implement:

1. **Project points** per player.
2. **Subtract replacement level** for the position → PAR (points above replacement).
   Our replacement levels are exact (table above).
3. **Reserve $1 per roster spot** (12 × 16 = $192 of the $2,400 pool is untouchable
   minimum bids; some sources reserve ~$2/bench spot).
4. **Distribute the remaining pool proportionally to PAR.** Players at or below
   replacement get the $1 minimum.

So: `$ = 1 + (PAR / total_positive_PAR) × (2400 − 192)`. This is directly computable
from `final_ranks` for a **retrodictive** valuation — what each season's prices
*should* have been with perfect foresight. Comparing that to `draft_picks.price` is
probably the single most valuable analysis available to us.

### Baselines (the choice matters more than the arithmetic)

- **VOLS** — value over *last starter*. Our table above. Favours studs, ignores bench.
- **VORP** — value over best *un-rostered* player. More conservative, shifts money to
  depth; generally considered wrong for redraft.
- **BEER / man-games** — replacement set by how many player-games the league actually
  consumes over a season (byes, injuries). More balanced.
- **BEER+** — blends ~40% VOLS / 60% BEER, adds risk adjustment. Recommended default
  for redraft.

Start with VOLS since our roster makes it exact, then test whether BEER-style baselines
better explain observed prices.

### Inflation (in-draft, but modellable from history)

Total dollars are fixed ($2,400); total value on the board is fixed. Every
overpayment must be recovered from later players.

`inflation = remaining_dollars / remaining_projected_value`

If $1,700 remains chasing $1,500 of value, everything left costs ~13% more than list.
Our history lets us measure **when** in each draft inflation ran hot or cold — i.e.
whether this league systematically overpays early and bargains late, which is the
classic pattern.

### Roster construction — what the research says

- **Stars and scrubs beat balanced** in a 40,000-draft simulation study (2022–25):
  26.9% league-winning rate vs 16.6% for RB-heavy. Definition: 60–70% of budget on
  3–4 players, rest at $1–2. Balanced = 40–55% on the top three.
- **Bench spending is low-return.** Bench players contribute little; excess cap should
  go to starters. One valuation model applies a **+10% premium to the top 30 players
  and −10% to players past 90th** to reflect this.
- **Elite QB added to stars-and-scrubs did *not* improve win rate** — it forced cuts
  elsewhere. Consistent with our PAR finding above.
- Stars-and-scrubs works better with **shallow rosters and good waiver wires**, because
  replacement level is higher. Ours: 7 bench spots, FAB waivers, no acquisition cap —
  a fairly deep bench, which argues *slightly* against the most extreme version.
- **Nomination strategy:** nominate players you don't want early to drain others'
  budgets; avoid nominating the top or bottom of a tier when bidding is hot.

We have `franchise_seasons.pct_on_top3` already — that directly measures
stars-and-scrubs vs balanced per team-season, and we can correlate it with outcomes
*within* a season without needing manager identity.

## Price → value analysis (`analyze_price_value.py`, run 2026-08)

Assumption-free: no replacement baseline, no projections. Just what each dollar
actually bought, over 1,695 picks. Outputs land in `cleandata/analysis/`.

Method notes: a drafted player with no stat line counts as **zero**, not missing (he
was bought and returned nothing). DEF is excluded (its NULLs mean "unknown", not
"zero"). Points are indexed to that season's mean drafted player before pooling.

### FINDING 1 — conditional on price, RB is the worst bet at nearly every tier

Startable rate (top-12 QB / 24 RB / 36 WR / 12 TE) by price paid:

| tier | QB | RB | TE | WR |
| --- | --- | --- | --- | --- |
| $1–2 | **43%** | **11%** | 35% | 16% |
| $3–5 | 38% | 22% | 48% | 32% |
| $6–10 | 46% | 35% | 48% | 46% |
| $11–20 | 58% | 42% | 48% | 59% |
| $21–35 | 74% | 65% | 71% | 65% |
| $36+ | — | 77% | 89% | 86% |

Spend $15 on a WR and you get a starter 59% of the time; the same $15 on an RB, 42%.
That holds at every tier below $21. **Cheap TE and cheap QB are far better darts than
cheap RB** — a $1–2 TE hits 35% and a $1–2 QB 43%, versus 11% for a $1–2 RB.

### FINDING 2 — the league over-allocates roster spots to RB

Players drafted per available starting slot, 2017–2025:

| pos | drafted | slots | per slot |
| --- | --- | --- | --- |
| RB | 514 | 212 | **2.42** |
| WR | 594 | 318 | 1.87 |
| QB | 196 | 106 | 1.85 |
| TE | 160 | 106 | 1.51 |
| K | 113 | 106 | 1.07 |

The league buys 2.4 RBs for every RB slot while cheap RBs hit 11% of the time, and
buys 1.5 TEs per TE slot while cheap TEs hit 35%. That allocation looks backwards and
is the clearest exploitable pattern found so far.

⚠️ **Caveat that matters:** aggregate "cost per startable season" (K $3.7, QB $16.7,
TE $19.9, WR $32.2, RB $43.3) is **confounded by that same volume** — drafting 2.42
RBs per slot caps RB's possible startable rate at 41%. RB's observed 38.7% is near
that ceiling, so most of the aggregate gap is mechanical. **Use the price-conditional
table above, not the aggregate.**

### FINDING 3 (null) — within a position, pricing is efficient

Fitting a separate price→points curve per position, no tier systematically beats its
own market (±10%, no pattern). There is no "always buy the $6–10 tier" trick. The edge
is cross-position allocation, not tier timing within a position.

### FINDING 4 (null) — nomination timing does not move value

After controlling for position, surplus by draft phase is +1.5% (first 24 nominations)
to −1.5% (last 40). **No late-draft bargain effect** — if anything slightly the
reverse. Kills the "overpay early, bargain late" hypothesis for this league.

### Trap: pooled points-vs-price curves flatter QBs

A first pass fitted one curve across all positions and reported QB surplus of +74%
"significant". That is an artifact — QBs simply score more (2025 replacement QB 272
pts vs WR 138), so they beat any pooled points curve regardless of market behaviour.
**Cross-position comparison requires either a replacement baseline or a rules-based
metric like startable rate. Never pool raw points across positions.**

## Upside / tail analysis (`analyze_upside.py`, run 2026-08)

**Jamie's objective, stated 2026-08: finish 1st, not post a winning record.** A high
startable rate is a *mean* measure and only buys the latter. What wins is hitting
players who massively out-produce their cost. So optimise the tail.

Definitions: **smash** = top decile of within-position, price-relative surplus.
**elite** = top-3 finish at the position.

### Testing the claim directly — result is genuinely mixed

Across 106 team-seasons, correlation with best-drafted-lineup points:

| metric | corr | led the league when roster was best |
| --- | --- | --- |
| smashes | **+0.52** | 22% of seasons |
| startables | +0.51 | **44%** of seasons |
| elites (top-3) | +0.44 | 33% of seasons |

Smashes and startables are a statistical tie; startables predict *being the top roster*
more often. **But the outcome variable here is total lineup points, which is a mean
measure — it cannot properly test a "finish 1st" claim.** Doing that needs championship
/ final-rank data, which exists only for 2025 (n=12). Treat this as unresolved, not
refuted.

### FINDING 5 — elite WR/RB can't be bought cheaply, but elite QB/TE can

Rate of producing a **top-3 season at the position**, by price paid:

| tier | QB | RB | TE | WR |
| --- | --- | --- | --- | --- |
| $1–2 | 9% | 1% | 5% | **0%** |
| $3–5 | 10% | 1% | 0% | **0%** |
| $6–10 | 15% | 0% | **19%** | 4% |
| $11–20 | 12% | 2% | **20%** | 1% |
| $21–35 | **37%** | 6% | **43%** | 6% |
| $36+ | — | 21% | **56%** | 26% |

**In nine seasons, 154 wide receivers bought at $1–2 and 94 bought at $3–5 produced
exactly zero top-3 WR seasons.** RB is nearly as stark. If you want elite WR or RB
production there is no cheap path — it costs $36+.

The reverse holds for QB and TE: a $6–10 TE went top-3 nineteen percent of the time,
and a $1–2 QB nine percent.

### FINDING 6 — points-above-replacement per dollar (VOLS baseline)

| pos | PAR/$ | | tier detail: | $1–2 | $6–10 | $11–20 | $36+ |
| --- | --- | --- | --- | --- | --- | --- | --- |
| K | 4.86 | | QB | **12.8** | 3.0 | 1.5 | — |
| QB | **2.74** | | TE | **8.1** | 2.5 | 1.6 | 1.6 |
| TE | 2.14 | | WR | 2.8 | 2.6 | 1.9 | 1.6 |
| WR | 1.65 | | RB | 2.9 | 1.5 | **1.05** | 1.4 |
| RB | **1.38** | | | | | | |

**RB is the worst return per dollar at every tier**, and mid-tier RB ($11–20, PAR/$
1.05) is the single worst place to put money in the entire draft.

### Strategy this implies (to be backtested before trusting)

Position-specific stars-and-scrubs: **pay $36+ for WR/RB where elite production is the
only way to get it, fill QB and TE from the cheap tiers where elite outcomes are still
live, and avoid mid-tier RB entirely.** Note this agrees with the 40k-sim study's
otherwise puzzling result that adding an *elite QB* to stars-and-scrubs didn't help.

Tension to respect: per **dollar**, cheap picks dominate (elites per $100: $1–2 tier
3.06 vs $36+ tier 0.51). Per **roster spot**, expensive picks dominate. With 16 spots
and $200 both constraints bind — that trade-off *is* the auction problem, and it is
what the backtest has to resolve.

## Analysis backlog

Ordered by expected value:

1. **Retrodictive VBD valuation** — what each player was *worth* vs what was paid, all
   9 years. Foundation for everything else.
2. **$/PAR by position by season** — settles the QB question properly.
3. **Positional market drift** — is this league leading or lagging the public market?
   (`preseason_adp` vs `draft_picks.price`.)
4. **Inflation curve within a draft** — early vs late bargains.
5. **Stars-and-scrubs test on real data** — `pct_on_top3` vs actual outcome.
6. **Simulation** — needs 1–4 first.

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

## Sources

- [VBD baselines: VOLS vs VORP vs BEER+](https://subvertadown.com/article/guide-to-understanding-the-different-baselines-in-value-based-drafting-vbd-vols-vs-vorp-vs-man-games-and-beer-)
- [40,000 auction simulations: Punt The Bench](https://statholesports.substack.com/p/punt-the-bench-40000-fantasy-football)
- [Fantasy Football Analytics — How to Win Your Auction Draft](https://fantasyfootballanalytics.net/how-to-win-your-auction-draft)
- [FantasyPros — Stars and Scrubs or Balanced](https://www.fantasypros.com/2019/06/stars-and-scrubs-or-balanced-auction-roster-how-to-decide-fantasy-football/)
- [Fantasy Football Calculator — auction strategy](https://fantasyfootballcalculator.com/news/fantasy-football-auction-draft-strategy) (also our ADP source)
- [nflverse data releases](https://github.com/nflverse/nflverse-data) (stat lines)
