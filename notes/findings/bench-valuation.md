
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
