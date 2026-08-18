
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
