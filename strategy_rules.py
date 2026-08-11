"""Draft rules we are willing to act on, with the evidence and an honest confidence.

Kept separate from build_dashboard.py because this is *content* -- it changes as
beliefs are tested, added and killed, and it should be easy to edit without
touching the dashboard code.

CONFIDENCE IS SET BY SAMPLE SIZE, not by how clean the point estimate looks.
Two findings were already retracted for resting on thin position x tier cells,
so anything under ~25 observations is capped at "low" however tidy it reads. A
claim whose interval spans the decision boundary cannot carry a recommendation.

  high      large n, interval clear of the boundary, survived challenge
  medium    directionally solid, or a mechanism we trust but have not measured here
  low       interesting, cannot carry a decision yet
  rejected  tested and failed -- kept so it is not re-adopted by accident
"""

RULES = [
    {"id": 1, "conf": "high", "area": "Pricing",
     "rule": "Cheap picks return more per dollar than expensive ones.",
     "why": "$1-2 picks returned 3.16x their share of the money (CI 2.52-3.83); "
            "$21-35 returned 0.79x (0.67-0.91) and $36+ 0.88x (0.80-0.97). "
            "$11-20 is the one band we cannot call — its interval crosses 1.0.",
     "n": "1,514 skill picks, 9 seasons, actual outcomes"},

    {"id": 2, "conf": "high", "area": "Pricing",
     "rule": "Expensive players are the RELIABLE ones, not the risky ones.",
     "why": "A $36+ pick's bad case is 0.51x its projection; a $1-2 pick's is "
            "0.20x. $36+ picks are startable 82% of the time (76-87) against 26% "
            "(22-29) at $1-2. Paying up buys certainty — it just costs more "
            "than the points alone are worth.",
     "n": "184 picks at $36+, 525 at $1-2"},

    {"id": 3, "conf": "high", "area": "Roster shape",
     "rule": "Do not commit to a roster shape. Stay liquid and let the room decide it.",
     "why": "Concentration explains nothing: r = +0.02 against drafted-roster "
            "quality. Seven deliberately different shapes on the 2026 board — "
            "from 38% to 91% of budget in three players — landed within 4.2% "
            "of each other.",
     "n": "106 team-seasons, plus a forward test on the 2026 board"},

    {"id": 4, "conf": "high", "area": "Mindset",
     "rule": "Do not try to out-rank the market. Buy price advantage, not better opinions.",
     "why": "Preseason ADP predicts final finish at rho 0.42 — roughly the "
            "ceiling for anyone. Two independent markets agree with each other at "
            "0.95 while either agrees with a projection model at 0.65-0.72, so the "
            "model is the outlier, not the insight.",
     "n": "~1,700 player-seasons, 9 seasons"},

    {"id": 5, "conf": "high", "area": "QB",
     "rule": "Never pay up for a quarterback. Target the QB9-15 band, roughly $3-8.",
     "why": "Buying QB1-3 costs $59 for every top-5 QB season it actually "
            "delivers. The QB9-15 band costs $22 for the same thing — 2.7x "
            "more efficient. That band produced Mahomes ($1), Josh Allen ($3), "
            "Herbert ($5) and Caleb Williams ($1). QB is also the flattest "
            "position: QB1 is only 1.29x the median starter, against 1.73x for RB1.",
     "n": "63 picks in the band, 27 at QB1-3, 9 seasons"},

    {"id": 6, "conf": "high", "area": "League quirk",
     "rule": "Assume the waiver wire will not save you. Drafted players matter more here.",
     "why": "IR is a 17th roster spot and there is no acquisition cap, so 12 teams "
            "hold 204 players against a 192-player draft — the wire is "
            "structurally drained. In 2025 in-season adds took 28.6% of roster "
            "spots but produced only 19.7% of the points.",
     "n": "mechanism confirmed in league settings; the 21.4% startable figure is 2025 only"},

    {"id": 7, "conf": "medium", "area": "RB",
     "rule": "Elite RB or lottery-ticket RB. Never mid-tier.",
     "why": "Mid-tier RB ($11-20) is the worst cell in the entire draft at 1.05 "
            "PAR per dollar. RB is the worst position per dollar overall (1.38) "
            "— but within RB, $36+ is the best tier (1.43). The league already "
            "barbells RB (220 picks at or under $5, 160 at $21+, only 134 between) "
            "and is right to.",
     "n": "514 RB picks, 9 seasons"},

    {"id": 8, "conf": "medium", "area": "WR",
     "rule": "Elite WR production costs $36+. There is no cheap route to it.",
     "why": "In nine seasons the 154 wide receivers bought at $1-2 and the 94 "
            "bought at $3-5 produced ZERO top-3 WR seasons between them. RB is "
            "nearly as stark. Cheap WRs can be startable; they are almost never "
            "difference-makers.",
     "n": "248 cheap WR picks producing 0 top-3 seasons"},

    {"id": 9, "conf": "medium", "area": "Bench",
     "rule": "Spend about $17 on the bench — not $7, and definitely not $55.",
     "why": "Bench players cover roughly 20 starter-weeks a season (even $36+ "
            "starters miss ~2.9 games) and are worth 100-173 points. A ~$17 bench "
            "beat a $7 bench with no loss of starter quality; a $55 bench bought 35 "
            "extra bench points while giving up 149 starter points.",
     "n": "forward test on the 2026 board; availability rates from 9 seasons"},

    {"id": 10, "conf": "medium", "area": "Bidding",
     "rule": "Bid to your true value and stop. Do not shade, and do not price-enforce.",
     "why": "A live auction settles at the SECOND-highest valuation plus a dollar, "
            "so the price is set by everyone else — shading is correct for "
            "sealed-bid FAAB, not here. Your edge is over the runner-up, not the "
            "whole room. Bidding to 'set the market' risks owning players you "
            "don't want.",
     "n": "auction theory — mechanism, not measured in this league"},

    {"id": 11, "conf": "rejected", "area": "Mindset",
     "rule": "REJECTED — pay the certainty premium less readily; the threshold "
             "objective rewards ceiling.",
     "why": "Modelled it once weekly data existed, and the load-bearing claim is "
            "false. Holding expected points equal and varying ONLY weekly "
            "variance, title odds are flat: 8.32% steady vs 8.47% spiky. Worse, "
            "it inverts with strength — for a top-2 roster, high variance is "
            "0.80x, actively destroying a fifth of your title equity. What the "
            "objective actually rewards is the MEAN, convexly (see rule 16). "
            "There IS a premium at the top (the 3 priciest picks return $0.62 on "
            "the dollar), but that is a pricing fact, not a reason to prefer "
            "boom-bust players.",
     "n": "refuted: 40k simulated seasons on 106 franchise-seasons of real weekly scores"},

    {"id": 16, "conf": "high", "area": "Mindset",
     "rule": "Maximise expected points. Full stop — the objective amplifies the "
             "mean, it does not reward variance.",
     "why": "P(title) against weekly team mean: 1.0% at 90% of league-average, "
            "3.2% at 95%, 8.3% at 100%, 16.9% at 105%, 28.6% at 110%. Title odds "
            "roughly DOUBLE per 5% of expected points. Because making top 6 is a "
            "steep S-curve in team strength, small edges in expected production "
            "compound instead of washing out — which is the opposite of the "
            "intuition that a short playoff makes the regular season a lottery.",
     "n": "40,000 simulated seasons, weekly scores resampled from 106 real "
          "franchise-seasons"},

    {"id": 17, "conf": "medium", "area": "Mindset",
     "rule": "Variance is a lever for the underdog, and a tax on the favourite. "
             "It is an in-season decision, not a draft strategy.",
     "why": "At equal talent variance is worth nothing (0.98x). But for a weak "
            "roster it is worth 1.47x, and for a strong one 0.80x. So it only "
            "pays once you KNOW you are behind — which is week 10, not draft "
            "night. Draft for the mean; if you are a bubble team in November, "
            "that is when you start streaming boom-bust.",
     "n": "same simulation; direction is robust to real skew and a 4-shark league"},

    {"id": 12, "conf": "low", "area": "TE",
     "rule": "TE around $21-35 MAY be the cheapest above-median starter. Unproven.",
     "why": "The 57% top-5 rate rests on 14 picks with a 95% interval of 29-80% "
            "— it spans a coin flip. Worse, over the last five years $20+ TEs "
            "finished TE9.8 on average, BELOW the median starter, and 0.94x median "
            "once Travis Kelce is excluded. A weak prior, not a plan.",
     "n": "14 picks — too thin to act on"},

    {"id": 13, "conf": "low", "area": "RB",
     "rule": "Cheap RBs are better lottery tickets than cheap WRs.",
     "why": "A $1-2 RB reaches top-12 3.0% of the time against 0.6% for a $1-2 WR, "
            "because an injured starter hands his backup a full workload while "
            "WR60 inherits nothing. Directionally clear, but small counts and the "
            "effect is a tail, not a mean.",
     "n": "132 RB and 154 WR picks at $1-2"},

    {"id": 14, "conf": "rejected", "area": "Timing",
     "rule": "REJECTED — nominating strategically moves prices.",
     "why": "The standard playbook says drain budgets early, inflate mid-tier "
            "names, trigger positional runs. We hold nomination order for all nine "
            "drafts and measured the effect on value at +1.5% early to -1.5% late. "
            "There is no late-draft bargain effect either.",
     "n": "1,695 picks with chronological nomination order"},

    {"id": 15, "conf": "rejected", "area": "Pricing",
     "rule": "REJECTED — the elite tier is underpriced.",
     "why": "A VBD valuation said so, but VBD allocates the pool proportionally to "
            "points above replacement, which assumes roster SPOTS are free. With 16 "
            "of them that is wrong, and it manufactured the result. The empirical "
            "tier test says the opposite: $36+ returns 0.88x its cost.",
     "n": "refuted by 1,514 picks of actual outcomes"},
]
