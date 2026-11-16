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
    bug-repo-drops-to-1-of-3-events.md   open bug (2026-11-15): repo drops to 1 of 3 events, 2 meetings not rendered; triage + decisive check, root cause unconfirmed
```

Rules of thumb:

- `AGENTS.md` = standing instructions (what the code is, how to work with it, hard rules).
  Keep it short enough to always read.
- `.agents/notes/*` = evidence, provenance, and rationale. Cite file paths / diffs used as proof.
- Record decisions when they are made; update `AGENTS.md` pointers if a note becomes load-bearing.
- Never store secrets here (see AGENTS.md "Secrets handling"). Notes may mention *which* secret keys
  exist, never their values.
