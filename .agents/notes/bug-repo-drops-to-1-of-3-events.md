# Bug: repo drops to 1 of 3 events → 2 meetings not rendered

- **Date observed:** 2026-11-15, ~16:30+ local, running F6 alert code on the ESP32.
- **Status:** triaged, root cause NOT yet confirmed. **Open.**
- **Priority:** medium (correctness — silent data loss of scheduled meetings; unrelated to the layer/alert work in progress).

## Symptom

Console logs `Found 1 event between 08:00 and 19:59:59` where there are 3 events that day (9:00, 10:30, 16:30). Only the 9 a.m. LED is lit; the 10:30 (LED 5) and 4:30 (LED 17) LEDs are dark.

## Key facts

- The `Found N events` line is the **half-day renderer's** `get_events_starting_between(08:00, 19:59:59)` logging — it reads the **repo**, not Google directly. So the repo held only the 9 a.m. event at that instant.
- At 16:30 the repo had **all three** (the same log printed "Found 3 events"). The only mutator of the repo is `event_fetcher` (every 300 s) → a **later fetch** replaced the repo with just the 9 a.m. event. So the Google fetch is now returning only that one event.
- This is a **fetch/data** issue, independent of the layer-model / alert design being discussed.

## Triage: likely causes (ranked)

1. **Fetch window no longer spans the 10:30 / 4:30 events.** AGENTS note says it *should* be yesterday→tomorrow (would include all three) — verify the actual `timeMin`/`timeMax` in `gcal.py`. If truly yesterday→tomorrow, window is *not* the cause → see #2/#3. If it's actually now-relative, day-progress explains it.
2. **Google/token-side** — partial or rate-limited response, or the OAuth refresh returning a degraded event set, leaving only the 9 a.m. event.
3. **A filter dropping the two** — if `secrets["filter_out_of_office"]` is on and the 10:30/4:30 events are OOO-tagged, they'd be filtered out, leaving the 9 a.m.

Timezone/parse is **unlikely**: if parsing shifted times to UTC, the 9 a.m. event wouldn't land at its correct LED. Since 9a shows in the right slot, parsing looks correct → points at the fetch, not the parse.

## Decisive check (not yet done)

Print the raw `cal_events.EVENTS` on the device — the actual fetched `{start, end}` structs.
- 10:30 and 4:30 **absent** → fetch isn't returning them (inspect `gcal` window / raw response).
- Present but start-hours **outside** 08:00–19:59:59 → then it *is* the timezone/parse gotcha.

## Follow-ups (when we resume)

- Read `gcal.py` `timeMin`/`timeMax` and the repo filter path.
- Confirm which of cause 1/2/3 via the raw `EVENTS` print.
