# Planned features (backlog, NOT in priority order)

Recorded 2026-11-11 from owner discussion. Order here is incidental — it is how the ideas
came up, not a priority ranking. Each feature gets its own `<topic>.md` under this directory
when scoping actually begins; this file stays the shared backlog.

## F1. Multiple display types

Support displays beyond the 24-bar bicolor bargraph: hub75 LED matrices, e-ink panels,
and OLED/LCD over I2C or SPI.

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

## Shared seams these features all lean on

1. **Display abstraction** (F1, plus the desktop test system): pure frame logic + driver adapters.
2. **Deterministic clock injection**: `render(now)` already exists; repository queries still call
   `time.localtime()` internally (`get_current_event`, `get_next_event`) — needs injectable now
   before any renderer feature can be tested reliably or extended (affects F1–F4 and the test plan).
3. **Time/timezone resolution**: current handling mixes UTC-parsed events with local `localtime()`
   (see AGENTS.md gotchas). Any feature that re-derives times from "now" should settle this first;
   golden tests pin *current* behavior so changes are deliberate and visible.

## Dependency notes (not priorities)

- The desktop test system + CI is the agreed starting point before any F1–F4 work — it de-risks
  all four, especially renderer-heavy ones (F1, F4).
- F3 and zoom/timeline scrolling interact: a rotary encoder likely replaces/augments the button-zoom
  UI, so scoping them together avoids two competing interaction models.
