
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
