# .agents/ — persistent agent context for Day Meter

This directory holds durable knowledge that survives across sessions: provenance,
decisions, and conventions that are too detailed for `AGENTS.md` but too important to
re-derive every time.

Layout convention:

```
.agents/
  README.md                 (this file)
  notes/
    snapshot-timeline.md    backup provenance record (evidence-based; folder dates untrusted)
    features/<topic>.md     future feature scopes — one file per topic, added as work starts
```

Rules of thumb:

- `AGENTS.md` = standing instructions (what the code is, how to work with it, hard rules).
  Keep it short enough to always read.
- `.agents/notes/*` = evidence, provenance, and rationale. Cite file paths / diffs used as proof.
- Record decisions when they are made; update `AGENTS.md` pointers if a note becomes load-bearing.
- Never store secrets here (see AGENTS.md "Secrets handling"). Notes may mention *which* secret keys
  exist, never their values.
