# Bug: repo drops to 1 of 3 events → 2 meetings not rendered

- **Date observed:** 2026-11-15, ~16:30+ local, running F6 alert code on the ESP32.
- **Status:** **RESOLVED** (2026-11-15). Root cause confirmed and fixed.
- **Priority:** was medium (correctness — silent data loss of scheduled meetings).

## Symptom

Console logs `Found 1 event between 08:00 and 19:59:59` where there are 3+ events that day. Only the earliest LED is lit; the later events are dark. Adding brand-new events to the calendar did not change the fetch result at all.

## Root cause (confirmed)

The Google `events.list` call in `gcal.py` **did not request an ordering**, so Google returned results in its *"unspecified, stable order"* — which empirically is a **partial, non-chronological page** that omits newly-created events. With the same `calendarId`, `timeMin`/`timeMax` window, and `maxResults=40`, adding `orderBy=startTime` returned the **complete** set in ascending order.

Decisive A/B on the device (2026-11-15), all else identical:

| | `orderBy` | items | Nov-15 events present |
|---|---|---|---|
| Without | (none) | 24 | 1 of 7 (only `15:00Z`) |
| With | `startTime` | 31 | all 7 (`14:00Z`–`22:30Z`) |

- Same `calendarId` (`andrew.koebbe@uniteus.com`), same window (`2026-11-15T00:00:00Z`–`2026-11-17T23:59:59Z`), same `maxResults=40` (31 < 40, no truncation), same OAuth token. The only variable was `orderBy`.
- This **disproves** the earlier calendarId-mismatch hypothesis: the 9 a.m. event was showing *because* it happened to be the oldest/most-stable item in the unordered page, not because other events live on a different calendar.
- Matches the documented behavior: *"The default is an unspecified, stable order"* and *"the number of events in the resulting page may be less than this value … even if there are more events matching the query."*
- Corroborated by the identical field report: https://stackoverflow.com/questions/36317584/google-calendar-api-does-not-return-newly-created-events (same "remove orderBy → new events buried" mechanism; author restored `orderBy=startTime`).

## Fix

`gcal.py` `get_calendar_events()`: added `&orderBy=startTime` to the `events.list` URL (chronological ascending, which is also the order the rest of the pipeline expects).

## Verification

- Device A/B already showed the fix working before the code change: with `orderBy`, the half-day frame lit all 7 Nov-15 events (`2.22.2....2.2....2......`) vs. 1 without (`..2.....................`).
- `python3 -m unittest discover tests` → 132/132 pass.

## Related latent bugs (still open, separate concerns)

1. **Pagination never read.** `gcal.py` never inspects `nextPageToken`. With `orderBy=startTime` the *first* page is chronological, but if a window ever holds >40 events the overflow is silent. Add pagination (loop on `nextPageToken`) before relying on large windows.
2. **`fields=items(start,end,eventType)`** hides `summary`/`status`/`htmlLink`, which would have surfaced this bug (the missing events are identifiable, not just absent). Optional to widen for debuggability.
