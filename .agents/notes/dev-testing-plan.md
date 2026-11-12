# Desktop development-test system for renderers (plan)

Goal: automated tests that exercise the screen-rendering logic on a dev machine (CPython),
not the board, ready to run in CI. Scope is renderer + event-logic behavior; physical I2C/USB
behavior stays manual/on-device by definition. Written 2026-11-11 from a re-read of current code
(see "What's already testable" — grounded in the actual API surface, not assumptions).

## What's already desktop-testable with ZERO product-code changes (verified)

- `renderers/*` and `events.py` import only stdlib (`time`, `math`) — they import fine under CPython
  today. No numpy needed: renderers pass plain frames between methods; the fake display can use
  tuples/lists instead of arrays.
- `BaseRenderer.__init__(events, bargraph)` + `render(now)`: both dependencies are injected and the
  clock is an explicit argument (`main.py` ticker calls `renderer.render(time.localtime())`).
  Tests supply fixed struct_times directly — no HTTP, no board.
- The only display methods renderers ever call (grep-verified): `progress(pct, color, justified)`,
  `set_frame(frame)`, `set_frame_from_text(24-char string)`. A fake object implementing just those
  three is a complete test double for every renderer class.

## Test doubles (`tests/fakes.py`)

`FrameRecorder`: duck-typed stand-in for the injected `bargraph` module:
- `set_frame(frame)` → stores frame (as tuple of color ints).
- `set_frame_from_text(text)` → converts using a test-local copy of bargraph's color map
  (`{'g':1,'r':2,'y':3,'':0}` matching `Bicolor24.LED_GREEN/RED/YELLOW/OFF` ordering — verify exact
  constant values once and document them here) then delegates to `set_frame`.
- `progress(pct, color='g', justified='left')` → returns a frame computed the same way as
  `bargraph.progress` (no commit; renderer calls set_frame itself), so golden tests exercise real
  fill math.
- Record: keep a list of all frames written per render call; expose `last_frame` and an ASCII
  rendering helper (`g/r/y/.`) so test failures are human-readable at a glance.

Clock policy (Phase 1): monkeypatch `time.localtime` in a small test-base helper — covers the two
repository methods that read the clock internally (`get_current_event`, `get_next_event`). No API
change to ship value first; an explicit optional `now=None` parameter can be added later when this
feature work actually touches those paths (see shared seam 2 in roadmap.md).

## Test suites

1. `tests/test_events.py` — pure logic, no fakes needed:
   - `iso_to_time_struct`: round-trip with `time_struct_to_iso`; pinned edge behavior (strips `Z`;
     offset-bearing strings like `+05:30` currently break — pin that as documented behavior).
   - Filters via `load_events_from_google` with synthetic Google-shaped dicts (`{"start": {"dateTime"|"date"...}}`,
     `eventType`): all-day events excluded; **out-of-office is currently NOT filtered** (line commented out)
     — test must assert current behavior, not the commented-out intent.
   - `get_current_event` / `get_next_event` with monkeypatched now: before/during/after, no events,
     multiple overlaps (pinned "first match" semantics).
   - `get_events_starting_between`: KNOWN BUG — when int args are passed it converts `end =
     time.localtime(start)` instead of `time.localtime(end)`. Strategy: write a test pinning the bug
     first (documented), flip to correct expectation only after owner approves the fix. Same
     discipline for anything else tests reveal.
   - `start_of_hour` / `end_of_hour` boundary math.
2. `tests/test_renderers_*.py` — golden-frame tests, one module per renderer class:
   - For each active renderer (`StaticHalfDayRenderer(start_hour=8)`, `MeetingCountdown(10)`,
     `MeetingTimeLeft`, `ZoomDayRenderer`) build a small matrix of (events × now): e.g. half-day:
     no meetings / meeting at 09:00–10:00 with now 09:30 / spanning midday; countdown: next event at
     −5 min, −2 min, −20 min (no-op), during-meeting (no-op); time-left: early/mid/late meeting, no
     meeting. Assert exact expected 24-char/frame output from the FrameRecorder.
   - Expected values are computed by hand once per case and eyeballed through the ASCII helper before
     being committed as goldens — a wrong golden is worse than none; review each table in PR notes.
   - ZoomDayRenderer: one case per zoom level × event placement (window offset near now).
3. Out of scope for Phase 1–2 (honest gaps to document): `bargraph.py` itself cannot import on desktop
   (module-level `board`/`Bicolor24` init), so its text→LED color constants and diff-write behavior are
   not covered until the seam refactor in Phase 4; `MeetingCombined` stays untested until/unless F4 adopts it.

## CI (GitHub Actions — origin is a GitHub repo)

`.github/workflows/ci.yml`, single job to start:
- ubuntu-latest, Python 3.12 (add 3.11 to matrix if cheap), **no pip installs needed** — the tested
  code paths are stdlib-only; `python -m unittest discover -v tests` is the whole step. This
  zero-dependency property of the current design makes CI trivially light.
- Triggers: push + pull_request on main.
- Stretch (add later, each independent): mpy-cross syntax-check job for board-side files; a
  MicroPython-on-qemu job running the same unittest subset that's CP-compatible; coverage report.

Framework choice: stdlib `unittest` deliberately — no third-party dep to pin, and it is the closest
match to the MicroPython `unittest` module if any self-tests ever run on-device. Switching later
is cheap because suites are plain classes/cases.

## Repo layout & device-copy hygiene

```
tests/
  fakes.py            FrameRecorder + clock monkeypatch helper
  test_events.py
  test_static_half_day_renderer.py   (etc., per renderer)
.github/workflows/ci.yml
```
- `tests/` is committed to git but **never copied to the CIRCUITPY drive** — AGENTS.md deploy
  workflow gets an explicit line about this.
- New files are desktop-only by construction: no `board`, `wifi`, `microcontroller`, `adafruit_*`,
  or `.mpy` imports anywhere under `tests/`.

## Phases (with exit criteria)

1. **P1 — skeleton + events suite.** tests/fakes.py, test_events.py green, CI job running on GitHub.
   Exit: `unittest discover` passes locally and in CI; zero product-code changes.
2. **P2 — golden matrix for the four active renderers** (+ zoom). Exit: one reviewed golden table per
   renderer class committed with ASCII previews in PR notes; suite stable across runs (no wall-clock
   dependence).
3. **P3 — CI hardening.** Lint job or mpy-cross check added; workflow triggers tuned; first real bug
   caught in CI is handled by the pin-then-fix discipline from test_events above.
4. **P4 — bargraph seam refactor (pairs with feature F1).** Split `bargraph.py` into pure frame math
   (testable, framework-free) + hardware adapter (`Bicolor24Driver`); renderer-facing contract frozen
   as the Display abstraction; then hub75/eink/OLED adapters slot in. Exit: bargraph's own unit tests
   exist and F1 has a concrete adapter interface to implement against.

## Alignment with planned features (roadmap.md)

- P1–P2 directly de-risk **F4** (overlapping events → golden cases for concurrent-event frames).
- The Display abstraction deferred to P4 is exactly what **F1** needs; the test doubles are its first
  implementations.
- **F2** later gains a `tests/test_calendar_sources.py` pattern: adapter in, normalized `{start,end}`
  out — same golden discipline.
- **F3** input tests will follow the same injection pattern (fake controller object into whatever
  consumes button/encoder events).
