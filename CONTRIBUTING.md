# Working on this together

Two people, one small repo, and a draft in a few weeks. This is mostly about not
stepping on each other.

## The loop

```bash
git pull --rebase
git checkout -b <topic>          # e.g. te-tier-analysis, board-filters
# work
python build_all.py              # must pass before you push
git push -u origin <topic>       # then open a PR
```

Rebase rather than merge on pull — the history stays readable, which matters when
you are trying to work out why a number changed.

`main` should always build. If `build_all.py` fails on `main`, that is the priority.

## Files that conflict badly, and what to do

**`cleandata/` — never commit anything from it.** It is all generated and all
gitignored: the database, the CSVs, the parquet, the 4MB dashboard. If you find
yourself resolving a conflict in there, something has gone wrong with the ignore
rules. Regenerate instead of merging.

**Live-feed snapshots are dated, so they never collide.** `fetch_yahoo_adp.py` and
friends write `<name>__YYYY-MM-DD.json`; the loaders glob for the newest. Two people
fetching on the same day write the same content to the same filename, which merges
trivially; on different days they write different files. This also gives us a history
of how ADP moved, which we do not otherwise have — the reason Underdog's edge rests on
Jamie's judgement rather than a measurement is that nobody kept the daily snapshots.

**`shared/board_state.json` is the one file you will both genuinely edit.** Targets,
notes and draft plans live there. Keys are written sorted and one per line so git can
merge two people's additions line by line, which handles the common case — you star
different players, both sets survive. What will not auto-merge is both of you editing
the SAME note or reordering the same plan; that is a normal conflict and the resolution
is obvious from the text. Pull before a long session on the board.

**`CLAUDE.md` is split so you do not both write to it.** It was 1,296 lines and the
single most-edited file in the repo, which is the worst possible shape for two authors.
It is now a ~500-line durable index — how to run things, how the league works, what has
already gone wrong — and it should change rarely and deliberately.

Everything that grows moved out:

| | |
|---|---|
| `notes/findings/*.md` | one file per analysis. Adding one? New file, plus a line in its README |
| `notes/findings/README.md` | the findings audit. Read it before citing any result |
| `notes/backlog.md` | what is worth doing next |
| `notes/log/YYYY-MM-DD-<you>.md` | one file per person per session. Never edit someone else's |

Two people writing up different analyses now touch different files and cannot conflict.
`notes/log/` additionally has `merge=union` set, so even a same-day filename collision
keeps both sides rather than stopping the world.

**`CLAUDE.local.md` is gitignored.** Personal preferences and scratch for your own
sessions, read alongside `CLAUDE.md`, never shared and never in a diff.

**`dashboard_template.html` is the one real hazard.** ~2,800 lines now that it carries
both leagues, and it is the highest-churn file in the repo. Not yet split into partials.
If you are both touching the dashboard, say which tab you are in first — the `drawX()`
functions are reasonably separable, so conflicts are usually resolvable if you stay
inside your own.

The two leagues are separated by a naming convention rather than by a file: **everything
belonging to Perennial Push is `x`-prefixed** — `xBoard()`, `xDrawPlan()`, `xplans`,
`#p-xboard`, `xState`. PBAFFL's equivalents are unprefixed. So one person can work on
`last`/`drawLast` while the other is in `xlast`/`xDrawLast` without touching a shared
line. `PPP` is the second league's data, `D` is everything.

**Do not patch `cleandata/dashboard.html`.** It is generated, gitignored, and rewritten
by every build. Changes go in `dashboard_template.html` and `build_dashboard.py`. This
is trap 11 in `CLAUDE.md` and it has already cost one rebuild-proof feature.

**`strategy_rules.py` is an append-to-a-list file.** Two people adding rules will
collide on the tail and can duplicate an `id`. Take the next free id, add at the end,
and if you both hit it the resolution is mechanical. Worth splitting into one file per
rule if it becomes a habit.

## Conventions worth keeping

**Confidence is set by sample size, not by how clean the estimate looks.** Two findings
were retracted early for resting on thin position × tier cells. Anything under ~25
observations is capped at "low" however tidy it reads, and a claim whose interval spans
the decision boundary cannot carry a recommendation. Rejected rules stay visible so
they are not re-adopted by accident.

**Report the interval, do not use it to quietly drop a finding.** WR $21–35 and RB
$11–20 return the same 0.75× per dollar; only WR got written up, because WR has more
picks. That described our sample size, not the league. If you can only call one, say
that.

**No projection touches pricing.** They are the weakest input we have and they live in
analytics. If you want to change that, the bar is evidence, not preference.

**Assert the shape of anything parsed.** A regex silently dropped rows from the 2025
draft HTML; a stat source served the wrong season and was only caught because a total
contradicted a known injury. Row counts, join rates, and reconciliation checks belong
in the script, printed on every run.

**Say what a number cannot support.** Most of the value in `CLAUDE.md` is the list of
things that turned out to be wrong.

## Secrets

`yahoo_credentials.json` and `yahoo_token.json` are gitignored and must never be
committed. The repo is private partly because the data contains leaguemates' real team
names and their full spending history from a private league — worth remembering before
making it public or pasting output anywhere.

## Getting oriented

Read `README.md` for the pipeline, then `CLAUDE.md` for why things are the way they
are. The "traps already hit" section is the fastest way to avoid repeating one.
