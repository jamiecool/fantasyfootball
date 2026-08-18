
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
