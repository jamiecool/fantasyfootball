# Perennial Push — what shapes a draft (`analyze_ppp_shape.py`)

⚠ **These are PPP findings and are numbered PPP-1..PPP-6 on purpose.** The PBAFFL
findings are numbered 1..11 and none of them transfer in either direction — different
draft format (snake vs auction), different scoring (full PPR vs half), different roster
(superflex, 18 rounds, a FLEX). Do not cite a PPP finding in a PBAFFL argument.

Established 2026-09-01 onward, from five seasons of PPP's own drafts: **2021–2025, 62
team-seasons, 1,116 picks.** Two exceptions are flagged where they appear — PPP-4 and
PPP-5 both use nine seasons of nflverse data, because they are statements about NFL
scoring and supply rather than about this room.

Published as a draft-night page:
<https://claude.ai/code/artifact/8f957b3a-0556-4780-aad5-17d9c01b2bc3>

---

## PPP-1 — leave QB2 past round 9 and the season is gone. **High confidence, thin n.**

| | wins | finish | n |
| --- | --- | --- | --- |
| QB2 taken by round 9 | 7.33 | 6.28 | 54 |
| QB2 round 10+, or never | **4.75** | **9.75** | **8** |

A 2.58-win, 3.47-place swing — by a distance the largest effect in the dataset, and the
only split where the difference clears one win.

**The n=8 side is thin, and this is stated strongly anyway because two independent lines
agree with it:**

1. **Supply.** 24 QBs start weekly in a 12-team superflex league. Cumulative QBs gone by
   end of round: r7 **21.2**, r8 **23.6**, r9 **25.2**. The startable pool is simply
   empty after round 8 — nothing about preference.
2. **Returns.** QBs taken in rounds 7–9 returned **+52.7** points over the RB/WR/TE
   taken alongside them, and 10–12 **+62.3**. See PPP-2.

Top-3 finishers took QB2 in round **5.1**; bottom finishers **7.2**. Teams carrying 3 QBs
averaged 7.31 wins against 6.89 for those carrying 2 (n=36 / 18).

**But getting there FIRST is not the point.** Taking 2+ QBs inside rounds 1–3 was worth
**−0.53 wins** (n=19 vs 43). The instruction is *by round 8*, not *early* — which is a
materially different thing from the received "superflex means draft QBs early".

## PPP-2 — rounds 4–6 are the worst place in the draft to take a quarterback

| band | QB mean | skill mean | edge | QB picks |
| --- | --- | --- | --- | --- |
| 1–3 | 264.9 | 242.3 | +22.6 | 67 |
| **4–6** | **195.9** | 185.6 | **+10.3** | 31 |
| **7–9** | **210.0** | 157.3 | **+52.7** | 28 |
| 10–12 | 185.5 | 123.2 | +62.3 | 24 |
| 13–15 | 165.6 | 105.0 | +60.6 | 10 |
| 16–18 | 89.7 | 96.3 | −6.6 | 10 |

A quarterback taken in rounds 4–6 returned **fewer points than one taken three rounds
later** (195.9 vs 210.0) and was startable 65% of the time against 82%. The edge over
skill players collapses to +10.3 in that band and is 5× larger either side of it.

Cells are n=24–31, so this is a real but not enormous sample. The shape — high, dip,
high — is consistent across the two independent measures (mean points and startable
rate), which is what makes it worth acting on.

## PPP-3 — the two cliffs: RB after round 9, WR one band later

Startable rate by position and round band (n per cell in `analyze_ppp_shape.py`):

| pos | 1–3 | 4–6 | 7–9 | 10–12 | 13–15 | 16–18 |
| --- | --- | --- | --- | --- | --- | --- |
| QB | 87% | 65% | 82% | 62% | 60% | 20% |
| **RB** | 85% | 67% | 59% | **32%** | 21% | 23% |
| **WR** | 93% | 72% | 62% | **41%** | 19% | 21% |
| TE | 88% | 78% | 65% | 45% | 45% | 36% |
| K | – | 100% | – | 100% | 100% | 85% |
| DEF | – | – | – | 89% | 87% | 85% |

- **RB collapses immediately after round 9** (59% → 32%). Whatever backs you want, take
  them before round 10.
- **WR beats RB in every band from 10 on** and holds one band longer.
- **TE never really collapses** — 45% in both 10–12 and 13–15, the only skill position
  still alive that late. Consistent with TE1 going at overall pick 31 while RB1 goes at 2.
- **K and DEF are 85–100% startable from round 10 onward**, which is why buying one early
  buys nothing. The 15 taken before round 13 averaged 133.1 points at position rank 6.6;
  the 125 taken from round 13 on averaged 118.5 at rank 7.7 — one rank of kicker quality,
  for a skill player worth roughly 149 points.

## PPP-4 — full PPR widens the WR spread, it does not merely raise the level

⚠ **This one uses nine seasons (2017–2025), not five**, because it is a fact about NFL
scoring rather than about this league and has no staleness argument against the longer
record. Checked for window sensitivity and it has none.

**The trap it avoids:** a bonus applied evenly to every player at a position changes
nothing about what a pick there is worth. Only a widening of elite-minus-replacement does.

Spread = mean of the positional top 5, minus the last player who starts league-wide:

| pos | spread, half-PPR | spread, full PPR | **widens by** | reception gap, elite vs repl |
| --- | --- | --- | --- | --- |
| QB | 175.4 | 175.4 | **+0.1** | 0.1 |
| RB | 162.9 | 177.9 | +15.0 | 29.2 |
| **WR** | 135.4 | 161.8 | **+26.4** | **55.2** |
| TE | 67.8 | 80.5 | +12.6 | 29.5 |

The mechanism is the reception gap, not the raw total: doubling what a catch is worth
amplifies a 55-catch gap twice as hard as a 29-catch one, and does nothing at all for
quarterbacks. Stable across windows — WR widens +28.0 on 2023–25, +26.2 on 2020–25,
+26.4 on 2017–25.

**The sharpest framing:** in half-PPR an elite RB's spread beats an elite WR's by 27.5
points; in full PPR that falls to 16.1. PPR does not make WR beat RB — it erases most of
RB's structural edge. Add that WR has 40 starting slots to RB's 30 and the position moves
ahead in practice, which is what the market here already does (PPP-3).

---

## What did NOT show up — read as unproven, not as proven absent

62 team-seasons cannot detect a small effect. Everything here is a null result at this
sample size and none of it is evidence that the factor is irrelevant.

| tested | result |
| --- | --- |
| Draft slot | 1–4: 6.75 w / 7.5 fin · 5–8: 7.55 / 5.7 · 9–14: 6.73 / 6.9. Inside the noise. |
| First TE in rounds 1–6 vs 7+ | **7.00 wins either way.** |
| 4+ WR by round 9 vs ≤3 | +0.07 wins. |
| 2+ QB in rounds 1–3 | −0.53 wins — see PPP-1, this is a null at best. |
| K/DEF before round 13 | −0.12 wins, though finish was 1.04 places worse (n=10). |
| RB count through round 9 | **Refused** — 56/6 split, too thin to report. |

The draft itself is not a null: total drafted points correlate **+0.50** with wins and
+0.64 with points scored. Top-3 finishers drafted **3,080** points against **2,612** for
the bottom of the table. Rounds 10–18 supply 36.6% of all drafted points against 26.3%
from rounds 1–3.

## Traps hit building this

- **Reporting a split without its n.** The first pass showed several tidy-looking
  differences on 6-a-side splits. `split()` now refuses anything under 8 per side rather
  than printing it, because a printed number gets quoted.
- **Confusing level with spread** (PPP-4). The obvious version of the PPR answer — "WRs
  catch more, so PPR helps them" — is not an argument at all until you show the bonus
  falls unevenly *within* the position. It does, but that had to be measured.
- **Matching a window out of habit.** PPP-4 was first computed on 2023–25 purely because
  the board's pick curve uses that window. Wrong instinct: the curve is deliberately
  short because draft behaviour goes stale, and an NFL scoring fact has the opposite
  requirement. Jamie caught the imprecision.

---

## PPP-5 — the flex is a non-decision in full PPR, and RB in half-PPR

Established 2026-09-03 (`analyze_ppp_flex.py`). Uses nflverse `final_ranks` and
`player_weeks`, 2017–2025, because the question is about the NFL's supply of
flex-quality players rather than about what this room happened to draft.

**The question is about the margin, not the top.** PPP starts 2 RB, 3 WR, 1 TE and
one FLEX across 12 teams, so the dedicated slots consume **24 RB, 36 WR and 12 TE**
before the flex chooses anything. It is never "is an elite back better than an elite
receiver" — it is RB25 against WR37.

| first available to the flex | mean | median |
| --- | --- | --- |
| RB25 | 172.9 | 168.8 |
| WR37 | 169.0 | 168.4 |
| TE13 | 139.9 | 139.5 |

### Weekly, which is how the slot is actually set, they are indistinguishable

4,575 player-weeks from the flex pool, scored full PPR:

| pos | mean | median | p10 | p90 | under 5 pts | 20+ pts |
| --- | --- | --- | --- | --- | --- | --- |
| RB | 10.5 | 9.4 | 2.6 | 20.4 | 24% | 11% |
| WR | 10.6 | 9.4 | 2.6 | 20.8 | 24% | 12% |
| TE | 8.2 | 7.2 | 1.6 | 16.2 | **36%** | 5% |

Same mean, same median, same floor, same ceiling, same bust rate. **And the same
durability** — 14.6 games against 14.5, which kills the "backs get hurt more"
intuition at this depth. Week by week the better start was the RB 43% of the time
and the WR 57%, with symmetric margins (6.5 against 6.1) and an overall difference
of **−0.61 points a week**.

### There is a crossover, and it is small

Same rank offset into each pool, so it is like for like:

| offset into the pool | RB | WR | WR − RB | WR won |
| --- | --- | --- | --- | --- |
| 1st available | 172.9 | 169.0 | −3.9 | 33% |
| 4th | 164.5 | 160.4 | −4.1 | 33% |
| 6th | 154.8 | 155.3 | +0.5 | 56% |
| 9th | 143.1 | 148.5 | +5.4 | 67% |
| 12th | 135.4 | 142.4 | +7.0 | 67% |

**A good flex back beats a good flex receiver; a bad one loses to a bad one.** If
your flex candidate is RB25–28 take the back, and past that take the receiver. Worth
4–7 points across a whole season either way, which is **under half a point a game** —
real, and far too small to draft around.

Filling all twelve flex spots with the best available each season splits
**RB 45% / WR 53% / TE 2%**. A coin flip, as the weekly numbers say it should be.

### ⚠ This does NOT transfer to PBAFFL, and that is the interesting part

| flex pool, 12 deep | RB | WR | TE | verdict |
| --- | --- | --- | --- | --- |
| **full PPR** (PPP) | 153.6 | 154.6 | 118.7 | WR by **1.0** |
| **half-PPR** (PBAFFL) | 137.5 | 127.3 | 96.0 | **RB by 10.2** |

Halving the reception flips the answer, because a flex-quality receiver's points are
far more reception-dependent than a flex-quality back's. In PBAFFL the same weekly
table shows RB ahead 9.4 to 8.7 and busting less often (29% against 33%).

**Actionable:** in PPP, stop treating the flex as a position to plan for — draft the
best player and let the slot sort itself out. **Never flex a tight end** outside the
top 12; TE13+ busts 36% of weeks against 24% for the other two. In PBAFFL the flex
does not exist (no FLEX slot), so the half-PPR column is a statement about that
league's scoring only, not advice.

---

## PPP-6 — the room drafts almost exactly down ESPN's within-position order

Established 2026-09-03 (`analyze_ppp_espn.py`), 2021–25 excluding 2023.

⚠ **This uses ESPN's preseason PROJECTIONS, not its published rank list.** The rank
list for a past preseason is not on disk and is not retrievable — ESPN serves the
current season's ranks, and both board snapshots are 2026. The projections are
demonstrably preseason rather than retro-fitted (actual comes in at 0.81–0.91 of
projection every season; a retro-fit would sit at 1.00). Swapping in the real rank
list would be a refinement, not a correction. **2023 is excluded** — ESPN did not
retain those projections; only 37 of 216 picks carry one.

Only *within* position is compared. This league is superflex and ESPN's board is
built for one quarterback, so comparing overall order would re-measure that known
mismatch (PPP-3) rather than the room's judgement.

### Agreement is very high, and stable

Spearman between ESPN's projected order and the order taken:

| season | QB | RB | WR | TE | all |
| --- | --- | --- | --- | --- | --- |
| 2021 | 0.96 | 0.96 | 0.94 | 0.94 | 0.97 |
| 2022 | 0.96 | 0.94 | 0.96 | 0.95 | 0.97 |
| 2024 | 0.92 | 0.97 | 0.98 | 0.94 | 0.98 |
| **2025** | **0.95** | **0.95** | **0.96** | **0.86** | **0.97** |
| all | 0.95 | 0.96 | 0.96 | 0.93 | 0.97 |

| pos | n | mean gap, places | within 3 | within 5 |
| --- | --- | --- | --- | --- |
| TE | 87 | **1.7** | 84% | 97% |
| QB | 136 | 2.2 | 82% | 90% |
| RB | 252 | 3.7 | 63% | 79% |
| WR | 307 | **4.1** | 60% | 74% |

The room is tightest where the position is thin (TE, QB) and loosest where there
is most to argue about (WR, RB). 2025's TE at 0.86 is the loosest cell on record.

### Deviation is asymmetric: reaching is punished, fading is not

Measured against **the round the pick was taken in**:

| pos | reached 5+ places early | agreed | faded 5+ places late |
| --- | --- | --- | --- |
| QB | +2.2 (n=8) | +18.3 (n=119) | **+78.5 (n=9)** |
| RB | **−39.9 (n=32)** | −7.4 (n=183) | +5.2 (n=37) |
| WR | −10.7 (n=47) | +1.0 (n=209) | +1.0 (n=51) |
| TE | −15.5 (n=5) | −1.6 (n=81) | −13.5 (n=1) |
| **ALL** | **−20.0 (n=92)** | +1.5 (n=592) | **+9.5 (n=98)** |

**Reaching past ESPN's order cost 20 points against the round; letting a player
fade did not cost anything.** At running back reaching cost ~40. The QB fade
figure is +78.5 but rests on n=9 and should not be leant on.

### ⚠ The yardstick decides the answer, and the obvious one is wrong

Scored against the *position's* mean instead, the same split reads reached −31.6,
agreed +8.2, faded −20.0 — i.e. "agreeing with ESPN is best and both deviations
hurt". That is an artefact: **a reach is by definition an earlier pick**, so
measuring it against the position's overall mean rewards it for exactly the thing
under test, and measuring a fade against that mean penalises it the same way.
Against the round, the asymmetry appears and the conclusion flips for fading.
Both tables are printed by the script so the difference stays visible.
