# Planned features (backlog, NOT in priority order)

Recorded 2026-11-11 from owner discussion. Order here is incidental — it is how the ideas
came up, not a priority ranking. Each feature gets its own `<topic>.md` under this directory
when scoping actually begins; this file stays the shared backlog.

## F1. Multiple display types

Support displays beyond the 24-bar bicolor bargraph: hub75 LED matrices, e-ink panels,
and OLED/LCD over I2C or SPI.
> **Status:** seam shipped (`display/` package, runtime selection via `secrets["display"]`).
Remaining F1 = concrete new-display adapters — each: new adapter class + one
`display/selector.py` entry + its lib in `lib/`.


Architecture surface:
- `bargraph.py` currently couples frame math (text→array, diff-write) to one concrete driver
  (`Bicolor24`) with module-level hardware init at import time. Needs a **display abstraction**:
  a small interface (frame set / text-frame set / commit; LED count + palette per display) with
  adapters per hardware type. The pure frame logic moves out so it is unit-testable on desktop.
- Renderers currently emit either 24-char frames or raw array fills via the injected `bargraph`
  module (`progress`, `set_frame`, `set_frame_from_text`). Display abstraction should define a
  renderer-facing contract independent of LED count (hub75 matrices have many more pixels than 24).

## F2. Additional calendar sources (Outlook, etc.)

Today: Google Calendar via REST in `gcal.py` + OAuth device flow; events normalized into
`EventsRepository.load_events_from_google`. Architecture surface: a **calendar source adapter**
interface (auth, fetch window → list of `{start, end}` struct_times) with Google as one impl and
Outlook as the next. Keep normalization at the `EventsRepository` boundary so renderers never see
source-specific shapes.

## F3. Physical input controls

Buttons or a rotary encoder to change render mode / scroll through the timeline. Today: one boot
button cycles `ZoomDayRenderer` zoom via `button_listener`. Architecture surface: an **input
controller abstraction** (events → semantic actions like "next mode", "scroll +N") so encoder vs
button is swappable and so renderers gain explicit mode/offset state rather than ad-hoc globals.

## F4. Overlapping / multiple concurrent events

Renderers must handle several events happening at once. Today: `EventsRepository.get_current_event`
returns only the *first* overlapping event; countdown/time-left logic assumes a single relevant
event. Architecture surface: repository queries should return **lists** of concurrent events, and
the renderer contract needs a defined policy for combining them (stacked fills? priority by start?
dedicated multi-event screen?). This also makes `MeetingCombined`'s direction relevant again — it is
currently orphaned in `renderers/meeting_combined.py`.
> **Status:** scoped + implemented in `.agents/notes/features/concurrent-meetings-columns.md` —
**all phases done**. The meetings layer composes up to 3 side-by-side columns (n=1 stays
full-width; 2 = 12/11; 3 = 8/7/7) with ≥1-LED OFF gutters so meetings stay distinguishable.
Reading A ordering (owner-picked): earliest start leftmost, imminent countdown rightmost. Config:
`meetings_max_columns` / `meetings_gutter_leds` (defaults 3/1, in `secrets.py.dist`). Desktop-green
(156 tests, both TZs) **and on-device verified** on the real board (real `Bicolor24Adapter`
composes one 24-LED frame per tick; gutters OFF; no sub-width `set_frame`).

## F5. Configurable half-day renderer window start hour (day-boundary wrap)

Today: `StaticHalfDayRenderer` takes a `start_hour` kwarg (wired at `main.py` as `8`), but the
12-hour window is computed with `start_of_hour(now, start_hour)` / `end_of_hour(now, start_hour + 11)`
— both on the same calendar date. If `start_hour ≥ 13`, the end hour exceeds 23 and
`struct_time` is invalid (no day-boundary wrap).

Feature: owner-configurable start hour (new secret key, e.g. `half_day_start_hour`, default `8`).
The 12-hour window must wrap when it crosses midnight: `start_hour=18` → window
`18:00:00` → `05:59:59` next day.

Architecture surface:
- `events.start_of_hour` / `end_of_hour` don't handle day overflow — either make them day-boundary
  aware, or compute the end in `StaticHalfDayRenderer` with an explicit date increment.
- New secret key in `secrets.py.dist`; wired at `main.py` renderer instantiation.
- Test: a window that wraps midnight returns events from both calendar days.

## F6. Meeting-start alert animation

When a meeting begins, the display plays a brief animation (≈5 s) before falling back to the
regular display (e.g. `MeetingTimeLeft`).
> **Status:** scoped in `.agents/notes/features/meeting-start-alert.md` (detection via
`get_events_starting_between` on `[prev, now)` windows, `MeetingAlert` controller,
width-capable renderers, faster alert cadence). v1 = full-width alert then fallback;
side-by-side column layout is the follow-on.

Architecture surface:
- **Width-resizability (hard requirement):** `MeetingCountdown`, `MeetingTimeLeft`, and the new
  alert renderer must each be resizable to **full width (24)**, **half width (12)**, and
  **1/3 width (8)** LEDs. The display is partitioned into up to 3 equal-width columns; a renderer
  emits its frame scaled to its assigned width (LED-index mapping scales with width). Requires the
  `Display` contract / `frame_math` to support sub-width rendering — renderers currently emit fixed
  24-char frames. This is what lets the alert (or the alert plus a regular renderer) share the display.
- A new alert renderer (or a display-level state machine in the ticker) that detects the transition
  to a new current event (`get_current_event` returns a different event than on the previous tick)
  and renders an animation sequence for a fixed duration.
- The ticker loop needs transient alert state: on event-start transition, switch to the alert
  renderer for N ticks (≈5 s at the current 5-s cadence = 1 tick; configurable), then resume.
- Animation pattern (e.g. a sweep, blink, or fill) — scope when implementing.
- Interacts with F4 (concurrent events): if multiple events start simultaneously, alert once.

## Shared seams these features all lean on

1. **Display abstraction** (F1, plus the desktop test system): pure frame logic + driver adapters. *(shipped: `display/` package — `frame_math` pure, `Display` contract, `Bicolor24Adapter` first adapter; concrete new-display adapters remain.)*
2. **Deterministic clock injection**: `render(now)` already existed; `get_current_event`/`get_next_event`
   now take `now=None` (default = `utc_to_local(time.localtime(), self.tz)`). *(shipped.)*
3. **Time/timezone resolution**: device RTC holds UTC (NTP); events convert UTC→local at store
   (`load_events_from_google`) via `posix_tz.utc_to_local`; `now` converts to local at query.
   `tz=None` = identity (original behavior). *(shipped: POSIX TZ, B2 conversion.)*

## Dependency notes (not priorities)

- The desktop test system + CI is the agreed starting point before any F1–F4 work — it de-risks
  all four, especially renderer-heavy ones (F1, F4).
- F3 and zoom/timeline scrolling interact: a rotary encoder likely replaces/augments the button-zoom
  UI, so scoping them together avoids two competing interaction models.
