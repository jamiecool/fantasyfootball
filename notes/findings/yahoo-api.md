
## Yahoo API — BLOCKED on Yahoo's approval (checked 2026-08-10)

`fetch_yahoo_standings.py` is written, credentials are on disk, and the OAuth
handshake completes. The fantasy endpoints still refuse:

```text
oauth_problem="additional_authorization_required"
```

**Cause: Yahoo moved Fantasy Sports API access behind a manual approval process.**
The permission checkbox no longer exists in the app-creation UI — apply at
<https://sports.yahoo.com/developer/access/>, supplying the existing Client ID so the
scope attaches to the `JamieFantasyPrep` app (read-only, <1,000 users). Yahoo reviews
each submission by hand and states no turnaround time.

**Do not retry the endpoints until approval arrives** — the 401 is not a bug, a
credential problem, or a redirect-URI issue, all of which were ruled out. The token
exchange succeeds; only the scope is missing.

Once approved, `python fetch_yahoo_standings.py && python build_clean_data.py` writes
`rawdata/standings/standings_YYYY.csv` and lifts `standings` from 12 team-seasons to
~106. That is the highest-value data left: it turns every retrospective result from
"this roster scored well" into "this roster won", and gives the simulator something
real to validate against.

Local files `yahoo_credentials.json` / `yahoo_token.json` are gitignored — never commit.
