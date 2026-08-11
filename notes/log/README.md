# Session log

One file per person per session: `YYYY-MM-DD-<you>.md`. Never edit someone else's.

This exists so two people can both keep notes without colliding. `CLAUDE.md` is the
durable index — decisions, traps, findings, things that turned out to be wrong — and
changes there should be deliberate rather than a running diary. Day-to-day "here is
what I tried and what it showed" goes here.

Worth writing down, from experience on this project:

- what you tested and what the number was, including the interval
- what you expected and did not get, which is usually the more useful half
- anything you had to fix in the data to make an analysis work — those are the
  findings that get silently re-broken later

`.gitattributes` sets `merge=union` on this directory, so if two people do somehow
write the same filename, git keeps both sides rather than raising a conflict.
