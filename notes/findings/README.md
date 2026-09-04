# Findings

One file per analysis. **Read this page before citing any finding** — the
audit below is what stops a retracted result being quoted as live.

## ⚠ Two leagues, two numbering schemes, no crossover

Everything on this page below this section is **PBAFFL** — the Yahoo auction league —
and its findings are numbered **1–11**.

**Perennial Push** (ESPN snake, superflex, full PPR) has its own file and its own
numbering, **PPP-1..PPP-6**, so the two can never be confused in a citation:

- [`ppp-draft-shape.md`](ppp-draft-shape.md) — what shapes a PPP draft. The quarterback
  deadline (PPP-1), the round 4–6 QB dead zone (PPP-2), the RB and WR cliffs (PPP-3),
  what full PPR actually does to receiver value (PPP-4), and the flex being a
  non-decision in full PPR while it would be RB in half (PPP-5). Plus a "did not show
  up" list to be read as unproven rather than absent.
  PPP-6 measures how closely the room drafts to ESPN's within-position order
  (rho 0.95-0.97) and finds reaching punished where fading is not.
  Scripts: `analyze_ppp_shape.py`, `analyze_ppp_flex.py`, `analyze_ppp_espn.py`.

**Nothing transfers in either direction.** Different draft format, different scoring,
different roster. A PBAFFL finding is a statement about an auction.

## Findings so far (PBAFFL)

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
