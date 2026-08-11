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
9. **Never use `np.minimum.accumulate` to make a curve monotone.** A running minimum
   drags every later point down to any dip. On the 2026 price board it flattened ADP
   ranks 10–17 to a single $38 (true medians: 47, 50, 44, 46, 44, 43, 43, 42) and
   under-priced them by $5–12 each. Use `sklearn.isotonic.IsotonicRegression`, which
   fits the best monotone curve instead. Smooth first if the per-point sample is thin
   — each ADP rank has only ~3 observations when pricing off 3 seasons.
10. **Fitting price ~ ADP with a polynomial in log space bends the wrong way at the
    top** — a quadratic priced ADP 1 *below* ADP 5. Rank-matching against history is
    better behaved and inherits the budget identity.

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

## Starter-tier analysis (`analyze_tier_surplus.py`, run 2026-08) — SUPERSEDES the top-3 framing

Jamie rejected "elite = top-3" as the upside bar, correctly:

> "If I pay $50 for a player they pretty much need to be top 3 or it's a problem.
> But say I pay $5 for a WR and he hits as a top-12 WR — that's a smash, because
> now I have a WR1 in my WR3 spot. That's a huge matchup advantage."

Value is relative to **the slot you're filling** and **what you paid**. With no FLEX,
`pos_tier = ceil(positional_finish / teams)`. A WR12 is tier 1 ("WR1 quality"); putting
him in your WR3 slot is +2 tiers of edge.

### What a starter tier is worth (mean season points)

| pos | tier 1 | tier 2 | tier 3 | tier1 − tier3 |
| --- | --- | --- | --- | --- |
| QB | 321 | 224 | 141 | **+180** |
| RB | 259 | 183 | 140 | +119 |
| TE | 158 | 100 | 70 | +88 |
| WR | 233 | 183 | 155 | **+78** |

Note WR has the *smallest* tier gap — it's the deepest position, so Jamie's WR3-slot
edge is real but is the cheapest tier upgrade to obtain. QB has the largest gap but
only one slot to apply it to.

### What each price actually bought (median realized tier)

| pos | $1–2 | $3–5 | $6–10 | $11–20 | $21–35 | $36+ |
| --- | --- | --- | --- | --- | --- | --- |
| QB | 2 | 2 | 2 | 1 | 1 | — |
| TE | 2 | 2 | 2 | 2 | 1 | 1 |
| RB | 5 | 4 | 3.5 | 3 | 2 | 1 |
| WR | **7** | 5 | 4 | 3 | 2.5 | 1 |

A $1–2 QB or TE already delivers tier-2 production. A $1–2 WR delivers tier 7.

### FINDING 7 — RB/WR are priced efficiently; QB/TE are not

Tier-1 seasons bought **per $100 spent**:

| pos | $1–2 | $3–5 | $6–10 | $11–20 | $21–35 | $36+ |
| --- | --- | --- | --- | --- | --- | --- |
| QB | **34.9** | 9.6 | 5.9 | 3.9 | 2.6 | — |
| K | **31.6** | — | — | — | — | — |
| TE | **27.7** | 12.5 | 6.3 | 3.3 | 2.5 | 2.1 |
| RB | 2.3 | 1.2 | 1.2 | 0.9 | 1.2 | 1.2 |
| WR | 0.5 | 1.1 | 1.6 | 1.4 | 0.9 | 1.3 |

**RB and WR are flat at ~1 tier-1 season per $100 at every price point.** The market
prices them efficiently — you get proportional production whatever you spend, and
there is no bargain zone. **QB and TE are wildly convex**: cheap ones deliver tier-1
production at 10–17× the rate per dollar of expensive ones.

That is the edge, and it is sharper than the earlier top-3 framing suggested.

### What $36+ actually buys

62% return tier 1; **18% aren't startable at all**. Among $36+ RBs: 57 tier-1, 16
tier-2, 9 tier-3, 5 complete zeros. So paying up is how you *reliably* get tier-1
RB/WR — it just isn't cheap per dollar, and one pick in six is a write-off.

### CORRECTION — "tier 1" is meaningless at 1-slot positions

Jamie, 2026-08: *"For a QB or TE to hit, it really needs to be top 5. If it's top 12,
sure it's technically tier 1, but that means you're probably always losing at that
position."*

He's right and it invalidates Finding 7's QB/TE numbers. With one starting slot,
`tier 1` spans ranks 1–12 — the **entire** starter pool — so `tier-1 rate` at QB/TE is
just `startable rate` renamed. The 34.9-vs-2.3 "per $100" comparison was measuring
"any startable QB" against "top-12 of 36 WRs". Not like for like.

**Correct baseline for a head-to-head league is the MEDIAN starter** (QB6, TE6, RB12,
WR18) — that's what the opponent fields each week.

### Production as a multiple of the median starter, by positional finish

| rank | QB | RB | TE | WR |
| --- | --- | --- | --- | --- |
| 1 | 1.29 | **1.73** | **1.60** | **1.72** |
| 3 | 1.13 | 1.46 | 1.21 | 1.44 |
| 5 | 1.04 | 1.28 | 1.06 | 1.32 |
| 12 | 0.88 | 1.00 | 0.80 | 1.11 |

**QB is by far the flattest position** — even QB1 is only +29% on the median starter,
against +73% for RB1. The whole QB range spans 1.29→0.88; TE spans 1.60→0.80, twice
the spread over the same 12 starters.

### FINDING 8 — what each price actually delivers vs the median starter

(1.00 = coin-flip matchup. Below 1.00 = you lose that slot most weeks.)

| pos | $1–2 | $3–5 | $6–10 | $11–20 | $21–35 | $36+ |
| --- | --- | --- | --- | --- | --- | --- |
| QB | 0.75 | 0.71 | 0.76 | 0.88 | 0.98 | *(n=4)* |
| TE | 0.64 | 0.70 | 0.78 | 0.83 | **1.16** | **1.25** |
| RB | 0.43 | 0.54 | 0.59 | 0.70 | 0.84 | **1.06** |
| WR | 0.46 | 0.61 | 0.73 | 0.84 | 0.87 | **1.15** |

**Except at TE, it takes $36+ to field an above-median starter.** TE gets there at
$21–35 and is the cheapest edge on the board.

Top-5 finish rate: TE $21–35 = **57%**, $36+ = 67%. QB $21–35 = 42%. RB $36+ = 32%,
WR $36+ = 37%.

### THIS REVERSES the earlier "fill QB and TE cheaply" advice — for TE

- **QB: punt it.** Flattest position (QB1 only 1.29× median), so the *most* an elite QB
  can win you is small, and even $21–35 only buys 0.98×. A $1–2 QB still returns top-5
  14% of the time — the best top-5-per-$100 in the draft (11.6 per $100). Buy the
  lottery ticket, not the position.
- **TE: invest, don't punt.** Cheap TE delivers 0.64–0.78× median — you *lose* that slot
  all season. $21–35 buys 1.16× and a 57% top-5 rate. It is the cheapest above-median
  starter available anywhere.
- RB/WR unchanged: $36+ or you're below median.

⚠️ QB $36+ shows 1.06× but rests on **4 picks in 9 years** — ignore it. The reliable
QB ceiling in this league's history is $21–35 at 0.98×.

### Metric caveat — the ">=2 tier smash" threshold is asymmetric

It is unavailable to expensive picks (a $36+ player's expected tier is ~2.1, so
beating it by 2 needs tier 0.1) and to QB/TE (expected ~tier 2 even at $1–2). Their
0.0% smash rates are artifacts, not findings. **Use tier-1 rate**, which is
well-defined at every position and price.

## FINDING 9 — roster SHAPE is a non-decision (`compare_roster_shapes.py`)

Jamie's challenge, 2026-08: *"You're basically arguing for all-out stars and scrubs.
All 3 options were really that."* He was right — the first three example rosters were
3–4 big buys and a wall of $1s, so nothing was actually being compared. It also
contradicted our own Finding (concentration vs roster quality, r = +0.02).

Five genuinely different shapes, each legal (16 picks, all 9 starting slots filled,
≤ $200), scored on projected starting-lineup points off the 2026 board:

| shape | max bid | top-3 % of budget | proj. starter pts |
| --- | --- | --- | --- |
| D. findings-led (no mid RB, TE buy, punt QB) | $62 | 76% | **1473** |
| C. barbell (two bats, then all mid) | $64 | 76% | 1469 |
| B. balanced (nothing over $30) | $31 | 44% | 1449 |
| A. stars & scrubs | $64 | 91% | 1428 |
| E. flat (every starter $18–25) | $25 | 38% | 1413 |

**Spread best-to-worst: 60 points, 4.2%.** One starter tier is worth ~78 pts at WR and
~119 at RB — so the entire range of roster shapes is worth *less than a single tier
upgrade at one position*. Concentration is not a lever. Stop treating it as one.

**What this means for the draft board:** don't prescribe a shape. Price every player,
then take whoever is furthest below their value on the night. The auction's real
advantage over a snake draft is that you can buy *anyone* — so stay liquid and let the
room's mistakes decide the shape.

### Bugs found building this (all silent, all changed the answer)

- **K/DEF bypassed the affordability check**, silently eating $4 and leaving three
  shapes unable to fill their last roster spots (7–9 picks instead of 16). Buy
  mandatory cheap slots FIRST so everything else budgets around them.
- **The board had no $1 players at all** — the floor was $2 with 132 players stacked
  there. Cause: the ADP list only reaches rank 175 among drafted players, and
  forward-filling carried ~$2 to rank 260. $1 is in fact the single most common price
  in league history (97 of 576 picks, 2023–25). Fixed by flooring ranks past the last
  observed one to $1.
- Comparing rosters with different pick counts / illegal lineups. **Always assert
  legality before comparing** — the first run "showed" balanced winning by 185 points,
  which was pure artifact.

## ⚠ KNOWN BIAS — the bench has been valued at ~zero, and that is an artifact

Jamie, 2026-08: *"I feel like in all your analysis you give basically zero value to the
bench? Is that intentional?"* It was not. It entered through the metrics, and it cuts
against this league's own structure.

Where it entered, in decreasing severity:

1. **`proj_starter_pts` (compare_roster_shapes.py) counts the 9 starters and nothing
   else.** Bench contributes literally zero. This is the worst offender and it is
   forward-looking, i.e. it feeds draft recommendations.
2. **`startable` / tier metrics use end-of-season positional rank**, so a player who
   missed six weeks and a player who played every week score identically.
3. **`drafted_lineup_pts` is only partly guilty** — it takes the best N *from the whole
   drafted roster*, so depth does get credit, but with perfect hindsight and no weekly
   structure. You cannot retroactively start whoever ended up scoring most.

### Why this matters more here than in a typical league

Availability, from `final_ranks.games` (17-game season, a healthy player plays 16):

| tier | mean games | played 16+ | played <12 |
| --- | --- | --- | --- |
| $36+ | 14.1 | 50% | **16%** |
| $21–35 | 13.5 | 34% | 20% |
| $11–20 | 13.8 | 43% | 19% |
| $1–2 | 12.8 | 38% | 27% |

**Even $36+ starters miss ~2.9 games each.** Nine starters × ~2.5–3.5 missed games is
roughly **20 starter-weeks a season needing a bench fill, out of 126** — about **18%**.

And we already established the wire here is bare (in-season acquisitions were startable
just 21.4% of the time, because IR is a 17th roster spot with no acquisition cap). So
this league needs its bench *more* than most, while every model above needs it less.

**Treat concentration conclusions as provisional until this is fixed.** Finding 9
("shape is a non-decision") is most at risk: it scored shapes on starters only, which
systematically flatters rosters that punt their bench.

### FINDING 10 — the bench is worth 100–173 pts/season, and there is a sweet spot

Correcting the bias above (bench = points that FILL a starter's missed weeks; it is an
addition, not a deduction — `exp_points` already nets out games missed):

| shape | bench $ | starter pts | bench fill | total |
| --- | --- | --- | --- | --- |
| F. two bats + real bench | $17 | 1487 | 138 | **1625** |
| D. findings-led | $7 | 1473 | 108 | 1581 |
| A. stars & scrubs | $7 | 1428 | 109 | 1537 |
| G. depth-first (12 real players) | $55 | 1338 | 173 | **1511** |

**A modest bench (~$17, i.e. 3–4 players at $6–10 rather than $1) is worth ~30 points
over a minimum bench and costs nothing in starter quality. A heavy bench ($55) is
clearly wrong** — it buys 35 more bench points while giving up 149 starter points.

Spread is now 114 pts (7.5%), up from 4.2% when the bench counted zero. So bench
allocation matters *more* than the starter-shape question that preceded it.

### Objective correction — season points is NOT the goal

Jamie, 2026-08: *"You only need to make the top 6 to make the playoffs and top 2 to get
a bye… there are no player byes in the playoffs, so usually the hottest/strongest team
that makes the playoffs wins."*

So the real objective is **P(top 6) × P(win from there)**, not expected season points:

- Making the playoffs is a **threshold** problem → floor and consistency matter, and
  each H2H loss is a full unit against the bar.
- Winning once in is largely variance → ceiling matters, and **bye weeks don't exist in
  weeks 15–17**, so season-long availability is worth less than it looks.

Everything scored so far maximises expected season points, which is the wrong
objective for both halves. **This is the largest remaining modelling gap.**

Jamie's own mechanism to test: a roster of a few stars plus waiver-level filler
probably *loses the week* whenever a star is out — turning ~3 missed games into ~3
losses, which is half the margin to the playoff bar.

### On modelling injury risk (Jamie: "seems tricky")

Predicting *who* gets hurt is not feasible and not necessary. What is computable from a
roster alone is **exposure**: the points/game gap between each starter and the best
bench player behind them. You cannot know who goes down, but a given roster's cost when
someone does is deterministic. Aggregate availability is stable and known ($36+ players
average 14.1 of 17 games; ~20 starter-weeks a season need filling).

### The fix requires weekly data

`stats_player_week_YYYY` from the same nflverse release (already listed under Known
gaps). With it we can build realistic **weekly optimal lineups** — respecting byes,
injury weeks, and the fact that lineups are set before results are known — instead of
season totals. That is now the highest-value item in the backlog.

## Projections — SOLVED (2026-08-10), and it unblocks the draft board

Previously the board's "projections" were a price lookup: ADP → price → points. Only 13
distinct values across the top 50, and **any value gap computed from it was circular**,
since both sides derived from ADP. That is fixed.

**Source: the Sleeper API** (`api.sleeper.app/projections/nfl/{season}`), via
`fetch_projections.py`. Chosen because it returns **raw stat components**
(`pass_yd`, `pass_int`, `rec`, `rush_td`…), not someone else's fantasy points — so
points are computed in `build_clean_data.py` under **this league's rulebook**, including
the −2 interception override. 3,301 players across QB/RB/WR/TE/K/DEF.

Validation that the scoring is really ours: QB projections come out 8–13 points *below*
Sleeper's own half-PPR figure, exactly `−1 × pass_int` (Allen: 10 INTs → −10.0), while
non-QBs differ by 0.0. That is the override working.

Rejected sources: **FantasyPros** 302-redirects automated requests; **FantasyData**
served 2025 numbers when asked for 2024 (caught only by a sanity check); **nflverse** is
historical only.

Caveats: **`gp` is a constant 18.0 placeholder, not an availability projection** — do
not use it for injury modelling. **K and DEF are scored with Sleeper's own points**
because the feed exposes only the 40–49/50+ FG bands and a partial points-allowed
breakdown; they are ~2% of spend. Column `scoring_basis` records which path each row took.

**D/ST projections exist for all 32 teams**, which finally makes the DEF slot valuable
prospectively even though `final_ranks` still has no historical D/ST.

Refresh, exactly like ADP (both stale after 3 days, both in `data_freshness`):

```bash
python fetch_projections.py && python build_clean_data.py
```

### Is the value gap real, or just two sources disagreeing?

Jamie asked the right question: prices come from Underdog's market, projections from
Sleeper's model — so is "value" just source noise? **No.** `projections.sleeper_adp`
keeps Sleeper's own market as the control:

| comparison | spearman |
| --- | --- |
| Underdog ADP vs Sleeper ADP | **0.963** |
| Sleeper ADP vs Sleeper projections | 0.753 |
| Underdog ADP vs Sleeper projections | 0.813 |

The two markets agree with each other far more than either agrees with the projections,
and Underdog actually tracks the projections *better* than Sleeper's own ADP does. So
mixing sources is not creating the gap — it is genuine **market-consensus vs model**
divergence. Re-run this check after any refresh.

**Where the divergence lives:** the top 8 WRs are priced efficiently (market rank vs
projection rank shifts by 0–1). Disagreement concentrates in the **$25–33 band** —
Rashee Rice (market WR11, projection WR18), Nabers (12→16), against McConkey (18→13)
and Olave (15→11). Hunt for edges in the middle tier, not among the elite.

⚠️ **Divergence does not say who is right.** Consensus ADP aggregates thousands of
drafters; a projection model is one opinion. We **cannot** settle it — that needs
*historical* projections to backtest, which we don't have and can't reconstruct.
Treat gaps as "worth a second look", never as confirmed mispricing.

### Unresolved tension this immediately surfaced

On projected **PAR per dollar**, Josh Allen at $25 is the *best* value on the 2026 board
(2.68) — ahead of Gibbs (2.15). That agrees with Finding 6 (QB PAR/$ 2.74, second only
to K) but appears to contradict Finding 8's "punt QB". Both are right under their own
baseline: PAR measures against the **last starter** (QB12), Finding 8 measured against
the **median starter** (QB6), and the QB curve is flat enough that the choice flips the
answer. **The baseline question is now the thing blocking a draft board — pick it on
evidence before recommending QB spend either way.**

## FINDING 11 — the ELITE tier is underpriced; the cheap tier is overpriced

Three independent lines of evidence, all pointing the same way. This reverses the
intuition (and an early misreading) that stars are the expensive mistake.

**1. VBD worth vs market price**, projections → PAR → $2,400 pool allocated
proportionally, $1 floor:

| price tier | n | pays | worth | delta |
| --- | --- | --- | --- | --- |
| $1–10 | 126 | $3.1 | $1.9 | −1.1 |
| $11–20 | 25 | $15.2 | $14.4 | −0.8 |
| $21–35 | 23 | $28.0 | $30.2 | +2.2 |
| **$36+** | 18 | $50.0 | **$55.9** | **+5.9** |

Biggest buys: Gibbs +27, Bijan +25, Allen +20, Bowers +14, Nacua +13, McBride +11,
Loveland +10, Mike Evans +10. Biggest fades: Tuten −16 (below replacement at $17),
Jefferson −8, Rice −7, Hampton / Javonte Williams / Jacobs −6.

**2. Expensive players are LESS volatile**, from the empirical distribution of
actual/tier-mean over 9 seasons:

| tier | p10 | median | p90 |
| --- | --- | --- | --- |
| $1–2 | **0.20×** | 0.83× | 2.07× |
| $21–35 | 0.46× | 0.99× | 1.60× |
| $36+ | **0.51×** | 0.99× | 1.52× |

A $36+ bust still returns half its projection; a $1–2 bust returns a fifth. Stars are
the *reliable* asset. This weakens the earlier fragility worry considerably.

**3. Monte Carlo on real outcome distributions** — an elite roster (top-2 RBs, $126 of
$193) beat a spread roster (nothing over $36) in **58%** of simulated seasons *and* had
the better 10th percentile (+61). Higher mean and higher floor.

### Reconciling with Finding 6

Finding 6 (RB worst PAR/$ at 1.38) is about RB **as a position** versus QB/TE. *Within*
RB, $36+ was always the best tier (1.43) and mid-tier the worst (1.05). The correct
reading was always **"elite RB or no RB"**, not "avoid RB" — I had been stating it too
loosely.

### Caveats

- The $1–10 delta is partly mechanical: VBD floors at $1, so sub-replacement players
  cannot go lower, and 126 of them sit there.
- **Josh Allen +20 rests entirely on the unresolved baseline question** (PAR vs QB12 =
  285; the *median* starter is QB6). Least reliable row on the board.
- Worth is per projections and inherits their error. Where model and market disagree
  hard (Jefferson, Rice) we cannot say who is right — no historical projections to
  backtest against.
- VBD concentrating value at the top more steeply than auction prices do is a *known*
  auction property, not something unique to this league. It is still exploitable here.

## ⚠ FINDINGS STATUS AUDIT (`audit_findings.py`, 2026-08-10) — READ BEFORE CITING ANY FINDING

Two findings were knocked down in consecutive turns, both resting on thin
position × tier cells. So every claim was re-checked with its n and a 95% bootstrap
CI. **A claim is only as good as its interval** — if the CI spans the decision
boundary, it cannot support a recommendation however clean the point estimate looks.

### Cell sizes — 9 of 30 position × tier cells have n < 25

| pos | $1–2 | $3–5 | $6–10 | $11–20 | $21–35 | $36+ |
| --- | --- | --- | --- | --- | --- | --- |
| K | 103 | **7** | **2** | **1** | 0 | 0 |
| QB | 70 | 40 | 39 | **24** | **19** | **4** |
| RB | 132 | 88 | 72 | 62 | 65 | 95 |
| TE | 66 | 25 | **21** | 25 | **14** | **9** |
| WR | 154 | 94 | 80 | 102 | 88 | 76 |

**Every upper tier at QB and TE is thin** — which is exactly where the QB and TE
recommendations came from. RB and WR are well-sampled everywhere.

### SOLID — large n, interval clear of the boundary

- **Tier value ratios** (n=1,514 picks): $1–2 returned **3.16×** its cost share
  (CI 2.52–3.83), $3–5 **1.36×** (1.02–1.73), $6–10 **1.33×** (1.05–1.63),
  $21–35 **0.79×** (0.67–0.91), $36+ **0.88×** (0.80–0.97). Cheap tiers return more
  per dollar; expensive tiers return less. *$11–20 at 0.91 (0.75–1.08) crosses 1.0 —
  inconclusive.*
- **Startable rate by price**: any $1–2 pick 26% (22–29), any $36+ pick 82% (76–87).
- **Cheap RB vs cheap WR for a starting slot**: RB $1–2 11% (5–16), WR 16% (10–21).
- **Elite reliability**: RB $36+ 77% (68–85), WR $36+ 86% (78–93).
- **Concentration is not a lever** — r = +0.02 across 106 team-seasons, confirmed
  forward on the 2026 board (shapes within 4.2%).
- **ADP predicts reality at only 0.42** (9 seasons, ~1,700 pairs). The single most
  important number in the project.
- **Positional spend drift** (n=1,695) and **nomination-order recovery** (all 9 seasons).

### WEAK — directionally interesting, cannot carry a recommendation

- **TE $21–35 top-5 = 57%, but n=14, CI [29%, 79%].** Spans a coin flip. Over the last
  5 years at $20+, the mean outcome was **TE9.8 — below the TE6 median starter** — and
  ex-Kelce it is 0.94× median. **Finding 8's TE advice is downgraded to a weak prior.**
- **QB $1–2 startable = 43%, CI [31%, 54%].** Spans 50%. The "cheap QB lottery ticket"
  is plausible but unproven.
- **Anything involving QB $21–35 (n=19), QB $36+ (n=4), TE $36+ (n=9), or K above $2.**
- **The IR / thin-wire result** (waiver adds startable 21.4%, 19.7% of points) is
  **2025 only** — one season, 196 roster spots. The mechanism is sound and the settings
  confirm it, but the magnitude is a single observation.

### RETRACTED

- **Finding 2 — "the league over-allocates to RB" (2.42 RBs per slot).** Jamie: cheap
  RBs are option buys, because an injured starter hands his backup a full workload
  while WR60 inherits nothing. Confirmed: a $1–2 RB reaches top-12 **3.0%** of the time
  vs **0.6%** for a $1–2 WR (5×); at $1–5 the top-5 rate is 1.4% vs 0.4%. My metric used
  position-relative thresholds (top-24 RB vs top-36 WR) — the right bar for filling a
  starting slot, the **wrong bar for a bench stash**. The league is correctly barbelling
  RB (220 picks ≤$5, 160 ≥$21, only 134 in the middle), not erring.
- **Finding 11 — "the elite tier is underpriced."** Refuted by the tier value ratios
  above. VBD allocates the pool proportionally to PAR, which assumes **roster spots are
  free**; with 16 slots that is wrong, and it manufactured the result.

### The pattern worth remembering

Every retraction came from a metric encoding **starting-lineup logic while missing
option value** — the same blind spot as scoring the bench at zero. When a claim
concerns a *bench* or *lottery* role, check absolute upside, not position-relative
startable rate.

## How the 2026 board is priced (settled 2026-08-10)

Two separate jobs, two separate sources. Getting this wrong caused several rounds of
bad output, so it is worth stating plainly.

1. **Ordering WITHIN a position → Underdog.** Jamie's call, from years of watching it:
   sharp money, continuously repriced, moves first. **We cannot verify this** — no
   historical Underdog ADP exists in the dataset, so it rests on his judgement, not
   on anything measured here. Don't re-litigate it without new evidence.
2. **Weighting ACROSS positions → PBAFFL's own positional price curves** (2023–25).
   Underdog cannot supply this: it is best ball, 18 rounds, with a FLEX this league
   doesn't have and no K or DEF at all. League history says RB1 = $66 while QB1 = $36
   — **that gap IS our format** (no FLEX, mandatory K and DEF). So Underdog says who
   the 5th-best RB is; league history says what the 5th RB costs.
3. **K and DEF → FFC**, the only source that drafts them.

Sanity check that this is right: the board now totals **$2,425 against the $2,400 pool**
(~1% over). The previous generic ADP→price curve came in ~15% light and needed a
"treat as a floor" caveat.

### What went wrong before, so it isn't repeated

- **A single primary ADP source inherits its noise wherever it is close.** FFC had
  Breece Hall 0.5 ahead of Kenneth Walker; Underdog had Walker ahead by 14.5 and
  Sleeper by 12.4. The board followed the coin-flip. Under the current method Walker
  is RB9 / $38 and Hall RB14 / $26, a $12 gap against Jamie's ~$15 estimate.
- **One generic ADP→price curve flattens positional structure.** It priced QB and RB
  off the same overall-rank curve, erasing exactly the no-FLEX / K+DEF effect that
  makes this league's prices what they are.
- **Sleeper projections are one algorithm, not a market.** They correlate with markets
  at 0.65–0.72 while markets agree with each other at 0.95. On the dashboard they are
  an informational column only (`proj`), never the ranking. Their QB tier is so
  compressed — QB6–QB14 inside 21 points, about a point a week — that the ordering
  there is close to noise.

## Yahoo API — BLOCKED on Yahoo's approval (checked 2026-08-10)

`fetch_yahoo_standings.py` is written, credentials are on disk, and the OAuth
handshake completes. The fantasy endpoints still refuse:

```text
oauth_problem="additional_authorization_required"
```

**Cause: Yahoo moved Fantasy Sports API access behind a manual approval process.**
The permission checkbox no longer exists in the app-creation UI — apply at
<https://sports.yahoo.com/developer/access/>, supplying the existing Client ID so the
scope attaches to the `JamieFantasyPrep` app (read-only, <1,000 users). Yahoo reviews
each submission by hand and states no turnaround time.

**Do not retry the endpoints until approval arrives** — the 401 is not a bug, a
credential problem, or a redirect-URI issue, all of which were ruled out. The token
exchange succeeds; only the scope is missing.

Once approved, `python fetch_yahoo_standings.py && python build_clean_data.py` writes
`rawdata/standings/standings_YYYY.csv` and lifts `standings` from 12 team-seasons to
~106. That is the highest-value data left: it turns every retrospective result from
"this roster scored well" into "this roster won", and gives the simulator something
real to validate against.

Local files `yahoo_credentials.json` / `yahoo_token.json` are gitignored — never commit.

## Where we left off (2026-08-11, third session)

Added **week-by-week stats** — the piece the whole simulation plan was waiting on.

- `fetch_nflverse_weekly.py` → `rawdata/nflverse/stats_player_week_YYYY.csv`, 2017-2025.
  These are **gitignored** (~70MB); the season files stay tracked.
- `player_weeks` table: **55,861 game lines**, scored through `league_points()` — the
  same function `final_ranks` uses, so a game log cannot drift from a season total.
  The build asserts this: **0 of 5,700 player-seasons mismatch.**
- Verified against known 2024 stat lines — Chase 127/1708/17, Barkley's 2005 rushing
  yards, Allen's 3731/28/6 — all exact.
- New **NFL stats** tab: any week range, position-aware columns, sortable, plus what
  PBAFFL paid for that player that year. Click a name for a profile: tiles, a weekly
  bar chart, the game log, and every season on record with price and buyer.

**Trap avoided, same family as the Michael Thomas bug.** 2017 had an RB Chris Thompson
(WAS) and a WR Chris Thompson (HOU). Deduping name collisions *per week* spliced the two
into one game log that outscored either man. Name collisions have to be resolved **once
per season** — rank whole seasons, keep that `player_id`'s weeks.

**Boom/bust thresholds are derived, not assumed** — each position's own p85/p25 among
starter-quality weeks, so a TE isn't judged on a QB's scale:

| | QB | RB | WR | TE | K |
|---|---|---|---|---|---|
| boom ≥ | 28.2 | 23.1 | 20.1 | 16.4 | 14.0 |
| bust ≤ | 14.2 | 7.9 | 6.4 | 4.7 | 6.0 |

**Known gap:** nflverse covers QB/RB/WR/TE/K only — **no team defences**. Stated in the
tab so it doesn't read as a bug.

**Player names open the profile everywhere** — 2026 board, past drafts, planner roster
and pool, market-disagreement table. Links join on `player_key`, never the display name;
name joins are what caused the Michael Thomas and Chris Thompson bugs, and
"Chris Godwin Jr." vs "Chris Godwin" would break silently. A name is only clickable when
history exists behind it, so 2026 rookies and DEF stay plain text rather than dead links
(board 83% linked, past drafts 94%, NFL stats 100%). Clicking from a past draft opens
*that* season; from the 2026 board, his most recent.

### Next session

- The H2H season simulator is now unblocked: weekly data exists. Build it →
  **P(top 6) × P(win weeks 15-17)** → validate by retrodicting 2025 → then settle the
  VBD baseline and the ceiling-vs-floor question.
- Week-level variance is now measurable, which is the real test of rule 11 (pay the
  certainty premium less readily). A threshold objective should reward ceiling — that
  claim is still theory and can now be checked.
- More beliefs from Jamie → test → promote/demote/reject with a confidence and an `n`.

## Where we left off (2026-08-10, second session)

The dashboard is the working surface now: `python build_dashboard.py` then
`python -m http.server 8000 --directory cleandata`, open
<http://localhost:8000/dashboard.html>. Tabs: **2026 board · Past drafts · Draft plan ·
Strategy · Analytics**.

**Strategy tab** renders `strategy_rules.py` — 15 rules, colour-coded by confidence,
filterable. That file is *content*: edit it, rebuild, done. Confidence is set by sample
size, and anything under ~25 observations is capped at "low" no matter how clean the
estimate looks. Rejected rules stay visible so they aren't re-adopted by accident.

**Jamie's QB belief was tested and promoted to high confidence.** He proposed the QB9–15
band; history backs it hard — $22 per top-5 QB season obtained versus $59 buying QB1–3,
across 63 picks. It came from his intuition, not the analysis, which is the model for
how the rest should get tested.

### Next session

- More beliefs from Jamie → test each the way the QB range was tested → promote, demote
  or reject with a confidence and an `n`.
- The agreed analysis plan, none of which is blocked by Yahoo: **fetch weekly data →
  build the H2H season simulator (P(top 6) × P(title)) → validate it by retrodicting
  2025 → then settle the VBD baseline and the ceiling-vs-floor question.**
- Draft plan tab exists and works; a live in-draft tracker would be the next addition
  once the draft is scheduled.

## Earlier notes (first session, 2026-08-09/10)

Data pipeline is **done and on GitHub** (private: `jamiecool/fantasyfootball`). Nine
seasons normalised, 2026 board priced, five findings established and three nulls.

**The open question, and it's the important one:** everything scored so far maximises
*expected season points*, which Jamie has correctly identified as the wrong objective.
The real one is **P(make top 6) × P(win weeks 15–17)**. Modelling that needs weekly
score *distributions* (for H2H win probability), not weekly optimal lineups — which is
a different reason for wanting `stats_player_week_YYYY` than the one given earlier.

Jamie's testable mechanism: a stars-and-scrubs roster probably *loses the week* whenever
a star is out, converting ~3 missed games into ~3 losses — half the margin to the
playoff bar. Finding 10 supports this directionally (bench worth 100–173 pts) but does
not yet model wins.

Open choice put to Jamie, unanswered: build the H2H/playoff model properly first, or
ship a usable draft board now and refine after.

## Auction theory, round 2 (researched 2026-08-10) — in-draft tactics

The first research pass covered pre-draft *allocation* (VBD, baselines, stars-and-scrubs).
Since then we established allocation is close to a wash (Finding 9), so this pass targets
what's left: mechanics, bidding, and nomination. Sources at the bottom of this file.

### A live auction is a SECOND-PRICE auction — this changes the right play

An open-outcry ascending auction settles at **the second-highest valuation plus $1**, not
the winner's. Consequences:

- **Do not shade your bids.** Bid shading is correct for *sealed-bid* formats (FAAB), where
  you pay your own number. In a live auction the price is set by everyone else, so the
  right play is to bid up to your true value and stop.
- **Your edge is over the room's SECOND-most-optimistic bidder**, not the whole room. You
  profit on players where you are right and the *runner-up* is wrong — being uniquely high
  on someone is worth nothing extra, you just pay one dollar over the next guy.
- The winner's curse is therefore **weaker here than in FAAB**, but not absent: the
  second-highest bid is still drawn from the upper tail of the room's estimates.

### The certainty premium — this explains Finding 11's empirical result

Elite players "command premium prices" as *the certainty*: managers pay extra for
predictable production. That is the mechanism behind the tier-value result we measured
independently:

| tier | value returned ÷ cost | p10 outcome (bad case) |
| --- | --- | --- |
| $1–2 | **3.16×** | 0.20× projection |
| $21–35 | 0.79× | 0.46× |
| $36+ | 0.88× | **0.51×** |

Expensive players **are** genuinely safer — we measured the tightest outcome distribution
at $36+. Buyers are paying for real risk reduction; it is simply priced above its
expected-points value. Both facts are true at once, and they stop contradicting each other
once you see the premium as buying *variance reduction* rather than points.

**The actionable consequence, and it is specific to Jamie's stated goal:** certainty is
worth less to a manager optimising for **1st place** than to one optimising for a winning
record. A threshold objective (top 6, then win three weeks) rewards ceiling; the premium
buys floor. **So he should be systematically LESS willing to pay the certainty premium
than his leaguemates are** — that is an edge available from his objective alone, requiring
no better player evaluation.

Consistent with the playoff-format literature: in short samples depth matters less than
ceiling, and boom/bust profiles that are wrong for a regular season are right for weeks
15–17.

### Nomination tactics (received wisdom — and our data disagrees)

The standard five-phase playbook: nominate hyped second-tier QBs first to drain budgets
early; nominate mid-tier RB/WR ahead of their rank to inflate them; trigger a TE run;
late on, nominate players that fit *opponents'* needs to strain their budgets; only
nominate your own targets at the close. Never nominate K/DEF early.

⚠️ **Finding 4 measured nomination timing at ±1.5% of value in this league — no effect.**
Either the tactics don't work here, or our measure (surplus by draft phase) is too coarse
to see them. Do not adopt the playbook as fact; it is a hypothesis we have already failed
to confirm once.

### Budget pacing and the endgame

- $200 / 16 spots = **~$12.50 per slot** average. Useful as a live sanity check.
- **Keep ≥$2 per remaining roster spot.** The last-dollar advantage is real leverage: with
  $2 while the room has $1, you win every contested scrap. Our data supports the setup —
  **$1 is the single most common price in league history** (97 of 576 picks, 2023–25).
- **Price enforcement is a trap.** Bidding purely to "set the market" risks owning players
  you don't want. Rule: every bid must be one you'd be content to win.
- Set a max per player before the draft and never cross it live.

### How this squares with what we already know

| received wisdom | our data |
| --- | --- |
| Stars-and-scrubs wins | Shape is a wash (r = +0.02; shapes within 4.2%) |
| Nomination tactics move prices | No effect measured (±1.5%) |
| Elite players are worth the premium | They return 0.88× cost — but are genuinely safest |
| Cheap $1 fliers backfill the roster | True per dollar (3.16×), but only 26% are startable |

The two that survive contact with the data are **the certainty premium** (explains the
tier curve) and **the endgame dollar** (cheap to exploit, consistent with $1 being the
modal price).

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

## Sources

- [VBD baselines: VOLS vs VORP vs BEER+](https://subvertadown.com/article/guide-to-understanding-the-different-baselines-in-value-based-drafting-vbd-vols-vs-vorp-vs-man-games-and-beer-)
- [40,000 auction simulations: Punt The Bench](https://statholesports.substack.com/p/punt-the-bench-40000-fantasy-football)
- [Fantasy Football Analytics — How to Win Your Auction Draft](https://fantasyfootballanalytics.net/how-to-win-your-auction-draft)
- [FantasyPros — Stars and Scrubs or Balanced](https://www.fantasypros.com/2019/06/stars-and-scrubs-or-balanced-auction-roster-how-to-decide-fantasy-football/)
- [Fantasy Football Calculator — auction strategy](https://fantasyfootballcalculator.com/news/fantasy-football-auction-draft-strategy) (also our ADP source)
- [nflverse data releases](https://github.com/nflverse/nflverse-data) (stat lines)

Second research pass (in-draft tactics, 2026-08-10):

- [Auction theory for fantasy — winner's curse, English vs sealed-bid, bid shading](https://pitcherlist.com/auction-theory-for-fantasy-baseball/)
- [Winner's curse (definition and the conditional-on-winning fix)](https://en.wikipedia.org/wiki/Winner%27s_curse)
- [The power of strategic nominations — the five-phase playbook](https://www.thefantasyfootballers.com/analysis/fantasy-football-auction-drafts-the-power-of-strategic-nominations-fantasy-football/)
- [Auction budget basics and the $2-per-roster-spot endgame rule](https://www.thefantasyfootballers.com/analysis/fantasy-football-auction-drafts-budget-basics/)
- [2026 auction strategy — budget tiers, nomination tricks](https://hellorookie.com/fantasy-football-auction-draft-strategy-budget-tiers-nomination-tricks-and-value-targets/amp/)
- [Elite WRs as "the certainty" — the premium framing](https://www.fantasylife.com/articles/fantasy/auction-fantasy-football-strategy-how-to-approach-wrs-in-2026)
