# PBAFFL — auction draft analysis

Working context for a multi-week project (Aug 2026), to be picked up again next year.
This file is the durable memory: decisions, traps, findings, and reference material.
Keep it current — append findings as they're established, and correct entries that
turn out to be wrong rather than leaving both versions.

## ⚠ FIRST: does `cleandata/fantasy.db` exist?

```bash
python build_all.py          # ~85s. Only needed if cleandata/fantasy.db is missing.
python serve.py              # http://localhost:8000/dashboard.html
```

**Everything generated is gitignored** — the database, the analysis CSVs, the 4MB
dashboard — so a fresh clone has none of it and nothing below will work until
`build_all.py` has run once. It is idempotent; running it again is harmless.

Live feeds (ADP, Yahoo, Vegas) do **not** run without `--refresh`, deliberately:
a rebuild should be reproducible, and re-fetching mid-analysis silently changes
numbers underneath a comparison.

Orientation, in this order: **`README.md`** for the pipeline and where the numbers
come from, **`CONTRIBUTING.md`** for the conventions and which files conflict, then
this file for why things are the way they are. The "Traps already hit" and
"FINDINGS STATUS AUDIT" sections below are the two most load-bearing.

New session notes go in `notes/log/YYYY-MM-DD-<name>.md`, one file per person per
session. This file stays the durable index — decisions, traps, findings — not a diary.


## ⚠ Then: check ADP freshness

Current-season ADP moves daily through the preseason. Everything else here is
historical and never goes stale. (Needs the database, so run `build_all.py` first.)

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


## Where everything lives

This file is the **durable index**: how to run things, how the league works, what
has already gone wrong. It changes rarely and deliberately.

Analysis write-ups and session notes moved out, because two people both appending
to one file conflict on every commit. They now live where you will not collide:

| | |
|---|---|
| `notes/findings/README.md` | **the findings audit — read before citing any result** |
| `notes/findings/*.md` | one file per analysis: price-vs-value, tiers, upside, bench, roster shape |
| `notes/backlog.md` | what is worth doing next, and what the data cannot answer |
| `notes/log/YYYY-MM-DD-<name>.md` | one file per person per session |
| `strategy_rules.py` | the rules we act on, with evidence and a confidence |

Adding an analysis? New file in `notes/findings/`, and a line in its README.
Do not append it here.

## Working practice

- **Never `git push` unless Jamie asks in that message.** Committing locally without
  being asked is fine. Approval for one push does not carry forward — not even within
  the same session on the same repo. Commit, say what's waiting, let him call it.
- `yahoo_credentials.json` and `yahoo_token.json` are gitignored and must never be
  committed. The repo is **private** — it holds leaguemates' real team names and their
  full spending history from a private league.


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


## Data sources, and what each is for

| source | fetch | role |
|---|---|---|
| **Underdog** | `fetch_underdog_adp.py` | **ordering within position** — the only thing driving the board's rank |
| PBAFFL history | `build_clean_data.py` | **cross-position weighting** — our own price curves supply what Underdog can't |
| FFC | `fetch_adp.py` | K/DEF only. Jamie's read: materially staler than Underdog, injury news lags |
| **Yahoo** | `fetch_yahoo_adp.py` | the room's anchor (we draft in the app) + the only **auction dollar** figure |
| Sleeper | `fetch_projections.py` | projections. **Not in the board any more** — dropped 2026-08-11 |
| nflverse | `fetch_nflverse*.py` | stat lines, season and weekly |
| **Vegas** | `fetch_vegas.py` | implied team totals. **Display only** — never touches pricing or sort |

The board's price is: Underdog says who is WR9, our own 2023-25 price curve says what
WR9 costs here. No projection enters it. Yahoo and Vegas ride along as cross-checks.

**Yahoo's auction costs say our board is $6-10 light at the top** (Gibbs $64 vs $73.3).
Consistent with the "treat these as a floor" note in `build_2026_board.py`.

**Vegas is not validated.** It is on the board as a visual check only. The open question
is whether implied totals add anything ON TOP of ADP — everyone setting ADP has seen the
same number. Testable with nine seasons of lines in `vegas_team_week` against
`player_weeks`; not yet run.


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
