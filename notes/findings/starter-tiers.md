
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
