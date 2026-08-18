
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
