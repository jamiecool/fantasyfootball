
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
