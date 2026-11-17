# F4 — Concurrent meetings, side-by-side columns

Detailed scope (and now implementation record) for the roadmap feature "Overlapping /
multiple concurrent events". The meetings display layer (layer 2 of the `renderers/stack.py`
topmost-wins stack) splits into **1 / 2 / 3 columns** so it can show up to **3 concurrent
meetings** at once, each column rendering one meeting's **countdown** (green, upcoming) or
**time-left** (red, in-progress) frame. A **≥1-LED OFF gutter** separates the columns so the
owner can tell the meetings apart.

Recorded 2026-11-16; implemented the same day (phases 1–4 below; desktop suite green both
TZs). Phase 5 (on-device end-to-end) is the only remaining step. This is the side-by-side
layout that `meeting-start-alert.md` (F6) explicitly deferred to a follow-on, and the F4
renderer-contract question ("dedicated multi-event screen?") answered concretely:
**columns**, not stacked fills or a dedicated screen.

## Owner requirement (verbatim)

> "The 2nd layer (meeting layer) should accomodate handling up to 3 meetings at once by
> dividing the display in to 1, 2, or 3 columns to show the meeting countdown and meeting
> time left. This should work for staggered meetings or meetings that happen at the same
> time. If only one meeting display is active, it should be in 1 column (full display) mode,
> if another meeting needs to be rednderred, it should compress the first meeting frame in to
> the left half of the display and the new meeting frame will be on the right side. Basically
> the meeting that start first will be on the right. There should be at least one LED buffer
> betweeen the individual meeting frames so that I can distinguish them."

Summary: 1 column = full width (today's behavior preserved); 2 columns = two half frames with
a gutter; 3 columns = three ~1/3 frames with two gutters. Staggered or simultaneous meetings
both work. Always a ≥1-LED OFF gutter between frames.

## Left/right ordering — resolved (Reading A)

The verbatim requirement contains two **contradicting** clauses:

1. *"compress the first meeting frame in to the **left** half … the new meeting frame will be
   on the **right** side"* → **older / first-started = left**, newer = right (chronological).
2. *"Basically the meeting that **start[s] first** will be on the **right**"* → earliest-started
   = **right**.

The owner was shown the two example frames (S4 below = Reading A, S4b = Reading B) and **picked
Reading A** (chronological left→right). If the owner later wants B, it is a one-line flip in
`MeetingsLayer._draw` (the current-meeting left-to-right ordering and the countdown placement).

Column assignment rule (Reading A, implemented):

- Gather the active meetings to show: **current meetings** (each a red time-left frame) first,
  then the **imminent countdown** (green, only if within the 10-min window).
- Sort the current meetings **by start time** (earliest start = first).
- **Reading A:** earliest start → leftmost column, later starts fill rightward; the countdown
  takes the rightmost remaining column.

## Column layout (verified)

1-LED gutters (configurable, see Configurable knobs), **extra LEDs go to the leftmost column**
(the natural bias for "compress the first frame into the left half"). Content LEDs =
`24 − (n−1)·gutter`; split into `n` columns as evenly as possible.

| n  | columns (offset, width) | layout |
|----|--------------------------|--------|
| 1  | `[(0, 24)]`             | full width, no gutter (today's behavior) |
| 2  | `[(0, 12), (13, 11)]`   | left = 12, gutter @ index 12, right = 11 |
| 3  | `[(0, 8), (9, 7), (17, 7)]` | left = 8, gutter @ 8, mid = 7, gutter @ 16, right = 7 |

Rule: `content = 24 − (n−1)·gutter`; `base = content // n`; `extra = content % n`; leftmost
column = `base + extra`, the rest = `base`; offsets accumulate `+gutter` per gutter. All three
tile exactly to 24 (verified). A sub-width frame can **never** reach `Bicolor24Adapter.set_frame`
(it `ValueError`s on length ≠ 24), so `MeetingsLayer._draw` composes to **exactly** 24 LEDs.

Pure `frame_math.column_layout(n, led_count=24, gutter=1)` returns the `(offset, width)` pairs
(stdlib-only, mirrors `frame_math`). Gutter width and the "extra goes left" bias are the two
tunables.

**Gutter = OFF region:** the ≥1-LED buffer is an *off* gap between columns. `compose` requires
regions to **exactly tile** `led_count` or it `ValueError`s — leaving a gutter as a bare gap is
**not** allowed. `MeetingsLayer._draw` therefore inserts an explicit `(offset − gutter,
[0]*gutter)` region before every non-first column so the tiling covers all 24 indices.

## Example frames (state matrix)

Colors — one square per LED (emoji): `⬛` = off, `🟩` = green (countdown), `🟥` = red
(time-left), `🟨` = yellow (alert). The Text column is the same frame in ASCII (`·` = off,
`g`/`r` = green/red), matching `tests/fakes.py` `frame_ascii`. Right-justified (red) = color in
the **last** `floor(w·pct)` slots; left-justified (green) = color in the **first**
`floor(w·pct)` slots. `pct` is the frame's fill fraction (time-left = fraction of meeting
remaining; countdown = fraction of the 10-min window remaining). Every row is exactly 24 glyphs.

| State | Columns | Text (left→right) |
|-------|---------|-------------------|
| **S1** no meeting | `[24]` | `························` |
| **S2** 1 current, 50% left | `[24]` | `············rrrrrrrrrrrr` |
| **S3** 1 next, 5 min out | `[24]` | `gggggggggggg············` |
| **S4** 2 staggered, **Reading A** | `[12,11]` | `······rrrrrr·rrrrrrrrrrr` |
| **S4b** 2 staggered, **Reading B** (not selected) | `[11,12]` | `rrrrrrrrrrr·······rrrrrr` |
| **S5** 1 current 50% + next 5min | `[12,11]` | `······rrrrrr·ggggg······` |
| **S6** 3 simultaneous, 50% each | `[8,7,7]` | `····rrrr·····rrr·····rrr` |

(S4/S4b use the two staggered meetings as example: an older meeting at 50% left, a newer
meeting just started at ~100% left — the column widths are 12/11, not the meeting durations.)

Per-width fill table (`floor(width · pct)`), for golden tests:

| width | pct 1.00 | 0.75 | 0.50 | 0.25 | 0.00 |
|-------|----------|------|------|------|------|
| 24    | 24       | 18   | 12   | 6    | 0    |
| 12    | 12       | 9    | 6    | 3    | 0    |
| 11    | 11       | 8    | 5    | 2    | 0    |
| 8     | 8        | 6    | 4    | 2    | 0    |
| 7     | 7        | 5    | 3    | 1    | 0    |

## Architecture changes (all additive; width=24 goldens stay green)

1. **`events.py` — `get_current_events(now=None)` (list).** Returns *all* events with
   `start < now < end`, sorted by `start` (earliest first), or `[]`. Derived from the same
   comprehension as `get_current_event`; the singular `get_current_event` is re-expressed as
   `get_current_events(now)` first-element so both share one source of truth. Existing callers
   (`MeetingTimeLeft.frame`) keep working unchanged.

2. **`renderers/stack.py` — `MeetingsLayer` rewrite (compose semantics).**
   - `occupied(now)`: true when **any** column would render — i.e. there is ≥1 current meeting,
     or the countdown is within window.
   - `_draw(now, display)`: build the column list (current meetings by start order, up to
     `max_columns` + optional countdown, Reading A); `n = len(columns)`;
     `regions = column_layout(n, LED_COUNT, gutter_leds)`; per column a per-width frame via the
     renderer's `frame_at`/`frame_for_event`; explicit OFF gutter region before every
     non-first column; `composed = frame_math.compose(regions, LED_COUNT)`; one
     `display.set_frame(composed)`. **No sub-width frame ever reaches the adapter**; exactly
     one `set_frame`, and `paint` commits once.
   - Replaces last-writer-wins with composed, gutter-separated columns. The two runner cadences
     are **unchanged** (base runner owns this layer at 5 s, gated off while the alert is
     active).

3. **Per-column width API on renderers.** Column width **varies per tick** (n=1 → 24, n=2 →
   12/11, n=3 → 8/7/7), so the layer cannot rely on a single fixed-width instance per column.
   **Option B** (width-parameterized frame method) is used: `MeetingTimeLeft.frame_at(now,
   width)` / `MeetingCountdown.frame_at(now, width)` (pure, no instance churn); `frame(now)` =
   `frame_at(now, self.width)` for backward compat. `self.bargraph.progress(pct, …, width=width)`
   already accepts a per-call width. `MeetingTimeLeft.frame_for_event(current_event, now, width)`
   is the pure per-event variant used for the multi-column time-left frames.

4. **`display/frame_math.py` — `column_layout(n, led_count=24, gutter=1)`** (pure). Returns the
   `(offset, width)` pairs from the layout table. Stdlib-only.

5. **`main.py` wiring.** No new coroutine; the existing `base_runner` already owns
   `MeetingsLayer`. The layer construction passes the `events` repo (for
   `get_current_events`) plus the two config kwargs (below). No new secret keys were required
   for the core feature; the two optional keys were added by owner request.

6. **`secrets.py.dist`.** Two optional config keys (see Configurable knobs).

7. **`MeetingCombined`** (`renderers/meeting_combined.py`): with the column approach,
   `MeetingCombined` is **not** the vehicle for the layout — the columns live in
   `MeetingsLayer`. It **stays orphaned** (not part of the F4 change).

## Configurable knobs (owner requested both)

Defaults are code constants in `MeetingsLayer` (`max_columns=3`, `gutter_leds=1`); either can be
overridden via secrets (user manages `mysecrets.py`; template keys in `secrets.py.dist`):

- `meetings_max_columns` (default 3) — max side-by-side columns.
- `meetings_gutter_leds` (default 1) — OFF-LED gutter width between columns.

Wired at `main.py` layer construction: `max_columns=secrets.get("meetings_max_columns", 3)`,
`gutter_leds=secrets.get("meetings_gutter_leds", 1)`.

## `>3` concurrent meetings

`max_columns` is a **hard limit** (default 3). If more than `max_columns` current events exist,
the **earliest `max_columns` by start** are shown and the extras (latest starts) are dropped, not
queued. Verified by `test_meetings_four_currents_shows_earliest_three` (4 events, one with a
distinct pct, → the all-50% 3-column frame; the dropped event would have changed the frame).

## Files changed (implementation)

| File | Change |
|------|--------|
| `events.py` | `get_current_events(now=None)`; `get_current_event` re-expressed as first element. |
| `display/frame_math.py` | `column_layout(n, led_count=24, gutter=1)` pure helper. |
| `renderers/stack.py` | `MeetingsLayer` compose rewrite + `max_columns`/`gutter_leds` ctor kwargs. |
| `renderers/meeting_time_left.py` | `frame` → `frame_at(now, self.width)`; `frame_for_event(event, now, width)`. |
| `renderers/meeting_countdown.py` | `frame` → `frame_at(now, self.width)` (per-width, 10-min window). |
| `main.py` | `MeetingsLayer` construction passes `max_columns` / `gutter_leds` from secrets. |
| `secrets.py.dist` | `meetings_max_columns`, `meetings_gutter_leds`. |
| `tests/test_events.py` | `CurrentEventsListTests` (4). |
| `tests/test_frame_math.py` | `ColumnLayoutTest` (8). |
| `tests/test_meeting_time_left.py` | width goldens (11/7) + `frame_for_event` match. |
| `tests/test_meeting_countdown.py` | width goldens (11/7). |
| `tests/test_stack.py` | `MeetingsLayer` compose cases (replace last-writer-wins pin); configurable-knob cases. |

## Test plan (stdlib `unittest`, desktop, no board imports)

- **`events.get_current_events`** (`tests/test_events.py`): returns *all* overlapping events
  sorted by start; `get_current_event` == first element; `[]` when none.
- **`column_layout`** (`tests/test_frame_math.py`): n=1/2/3 tile exactly to 24; gutter width
  honored.
- **`MeetingsLayer` compose** (`tests/test_stack.py`): 1 current → full width; 2 current →
  composed + OFF gutter @12; 3 current → two gutters @8/@16; current + countdown → green right
  column; no events → not occupied (no write/commit); 4 current → capped at 3 (earliest, drop
  latest); `max_columns=2`; `gutter_leds=2`. Each asserts exactly one composed 24-frame and one
  commit via `RecordingDisplay`.
- **Width goldens** (`tests/test_meeting_time_left.py` / `test_meeting_countdown.py`): for the
  per-width frames, length == width and filled LEDs == `floor(width·pct)` (reuse `frame_ascii`).
- **Regression gate:** `python3 -m unittest discover tests` **and** `TZ=UTC python3 -m unittest
  discover tests` green (156 tests at implementation time: 132 baseline → +12 phase 1 → +5
  phase 2 → −1 last-writer +6 compose +2 knobs = 156).

## Implementation phases (each independently shippable)

1. **List query + layout helper (pure, no device change).** `events.get_current_events` +
   `get_current_event` re-derived + `frame_math.column_layout` + tests. *No on-device behavior
   change yet.* — **done**
2. **Per-width frame API.** `frame_at(now, width)` on `MeetingTimeLeft` / `MeetingCountdown` +
   width golden tests at 24/12/11/8/7. `render`/`frame` at width=24 unchanged → existing
   goldens green. — **done**
3. **`MeetingsLayer` rewrite (compose) + tests.** Replace last-writer with compose; update
   `tests/test_stack.py` MeetingsLayer cases. *This is where the on-device behavior changes.* —
   **done**
4. **Owner ordering confirmation + optional config.** Confirm A vs B (owner picked **A** — no
   flip needed); add `meetings_max_columns` / `meetings_gutter_leds` secrets (owner requested
   both). — **done**
5. **On-device end-to-end.** Real QT Py ESP32-S3 (Adafruit CircuitPython 9.2.7) with the real
   `Bicolor24Adapter` (I2C HT16K33): confirm gutters OFF, single composed 24-frame per tick, one
   commit, **no sub-width `set_frame`** (would `ValueError` on the adapter). — **done**

## On-device verification (phase 5, done)

Ran on the real board (deployed `main.py` + `renderers/`, `display/`, `events.py`). A temporary
`main.py` drove the **real `Bicolor24Adapter`** + **real `MeetingsLayer.compose`** with fake events;
the `set_frame` length-check is the guard that proves no sub-width frame reached the adapter. Four
scenarios, each **one composed 24-LED frame, one commit, gutter LEDs OFF**:

| Scenario | Composed frame (real adapter) | set_frame | Gutter |
|----------|-------------------------------|-----------|--------|
| 1 current, full width | `.................1111111` | 1 | — |
| 2 current, 50% each, Reading A | `.........111.......11111` | 1 | idx 12 OFF |
| 3 current, 50% each | `......11.....111.....111` | 1 | idx 8 & 16 OFF |
| 2 current + countdown | `......11.....111.2222222` | 1 | idx 8, 16 OFF |

(`1` = red, `2` = green, `.` = off; the real `Bicolor24Adapter.commit()` prints these.) Reading A
confirmed on hardware: earliest start leftmost, green countdown rightmost. `main.py` restored and
the app re-ran clean (WiFi → NTP → token → calendar fetch → app loop). `mysecrets.py` untouched;
the board's copy predates the two new keys and `main.py`'s `secrets.get(..., default)` covers it.

## Risks / open questions

- **Sub-width `set_frame` rejected** by `Bicolor24Adapter`: the rewrite **must** compose before
  `set_frame`; a stray sub-width write `ValueError`s at runtime. `MeetingsLayer._draw` is the
  single write point (compose → one `set_frame`), so it is guarded; the golden tests asserting
  the composed frame is exactly 24 LEDs are the backstop.
- **Compose requires exact tiling** — `frame_math.compose` `ValueError`s if regions do not cover
  all `led_count`; a gutter left as a bare gap is not enough. `_draw` inserts explicit OFF
  gutter regions so the tiling is exact (verified: `[(0,12),(12,1),(13,11)]` tiles; `[(0,12),
  (13,11)]` does not).
- **Gutter = off LEDs:** with 3 columns the gutters fall at fixed indices (8 and 16); a
  meeting's red bar visually "pauses" across the gutter. That is the intended separation and
  matches "distinguish them."
- **`MeetingCombined`** stays orphaned; not the F4 vehicle (columns live in `MeetingsLayer`).
  Revisit only if the owner wants a combined renderer later.
- **Reading B** is a one-line flip in `MeetingsLayer._draw` if the owner ever changes their
  mind (earliest start → rightmost; countdown leftmost).
