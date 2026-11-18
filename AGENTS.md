# AGENTS.md — Day Meter

Instructions for AI agents (and humans) working in this repository.

## What this is

Day Meter is a CircuitPython application that renders your Google Calendar day on a
24-LED bicolor bargraph: meetings today, a 10-minute countdown to the next meeting,
and remaining time of the current meeting. It runs standalone on an ESP32 — no host PC
needed at runtime.

The project's human-readable README is at `README.md` in the root (restored from git history on 2026-11-11;
reviewed against current code — features and hardware listed are accurate). `requirements.txt`
lists library dependencies for fresh installs; its version pins date to Feb 2024, so treat the
on-device `lib/` as authoritative rather than re-pinning from it blindly.

## Ground rules (read first)

1. **The root of this directory is the source of truth** — it mirrors what is currently
   flashed on the ESP32 device. `backups/` contains historical snapshots; their folder
   names and file dates are **not reliable**. Never auto-sync or restore from a backup
   into root without an explicit content diff review. See `.agents/notes/snapshot-timeline.md`
   for provenance evidence.
2. **Secrets handling is critical.** `mysecrets.py` contains live credentials
   (WiFi, Google OAuth client + access/refresh tokens, Google Calendar ID, timezone;
   Adafruit IO keys are no longer used — NTP replaced the old time-sync path).
   - Never print its values, include them in diffs/summaries/commits/logs, or echo them anywhere.
   - When a diff touches `mysecrets.py`, report that *it differs* without showing contents.
   - **Do not copy `mysecrets.py` from any backup** — snapshots contain different (likely stale)
     credentials; copying an old refresh token can break Google auth. Only the user manages it.
   - New/changed config keys: add them to `secrets.py.dist` (the template) as well.
   - Note: code imports `from mysecrets import secrets`, even though some comments say "secrets.py".
3. **Do not run this code on a host machine.** It is MicroPython/CircuitPython for the board.
   Local desktop Python is only useful for syntax-level review, and many modules
   (`board`, `wifi`, `microcontroller`, `.mpy` libs) will not import there.

## Hardware & device identity

- **Current board:** Adafruit QT Py ESP32-S3 (4MB flash / 2MB PSRAM), USB VID/PID `0x239A:0x8144`.
- **Firmware:** Adafruit CircuitPython 9.2.7 (build 2025-04-01). See `boot_out.txt` for the captured banner and board UID (`4F21AFA5A3C1`).
- An earlier board was a QT Py ESP32 PICO (UID `CAB0BF96D503`) that ran CP 8.0.x/9.x before the S3 migration; some snapshots still reflect it.
- **Display:** Adafruit Bi-Color (Red/Green) 24-Bar Bargraph w/I2C Backpack Kit, driven by `adafruit_ht16k33` over `board.STEMMA_I2C()`.

## Development & deployment workflow

1. Edit files here.
2. Copy the changed `.py` files and (if libraries changed) `lib/` to the board's `CIRCUITPY` drive
   (it mounts as a USB mass-storage volume; this directory mirrors it).
3. Watch the serial console: the boot sequence prints progress + free-heap after every stage
   (`Mem Free: ... bytes`). A successful boot ends in an asyncio loop that logs every 5s tick,
   every 300s calendar fetch, and every 15-minute token refresh.
4. `lib/` holds **compiled `.mpy` libraries** for the board (CP 9.x era). Update them with
   `circup --path . install` (per the old README) or by copying Adafruit's CircuitPython bundle
   mpy files; do not mix in desktop Python packages. PyCharm/VS Code stubs are referenced from a
   local extension directory in `.vscode/settings.json`.
5. `safemode.py` is a one-line board reset (`microcontroller.reset()`) — useful only on the device
   when the normal boot wedges. Don't treat it as part of the app.
6. Desktop test code lives in `tests/` (committed to git but **never copied** into the CIRCUITPY drive).
   Run with `python3 -m unittest discover tests`; scope and CI notes are in `.agents/notes/dev-testing-plan.md`.

## Architecture

Boot sequence (top of `main.py`), each step in a retry loop with yellow bargraph feedback:

1. WiFi connect (secrets from `mysecrets.secrets`).
2. RTC set via NTP: `adafruit_ntp.NTP(pool).datetime` — **UTC** (device RTC holds UTC;
   local conversion happens in app code, not at the hardware layer).
3. Google OAuth token refresh: `google_cal.refresh_token()` (OAuth2 refresh grant via `adafruit_oauth2`).
4. Async app loop (`asyncio.run(main())`); any unhandled exception resets the whole board by design.

| Task | Interval | Purpose |
|---|---|---|
| `refresh_token_runner` | every 15 min (`gcal.REFRESH_TIME`) | keeps Google access token valid |
| `event_fetcher` | every 300 s | pulls calendar events (yesterday→tomorrow window, max 40) into `EventsRepository` |
| `alert_runner` | every `alert_cadence_s` (default 0.2 s) | detects meeting starts (`alert.on_tick` + `alert_renderer.mark_started`); paints the alert layer (topmost) |
| `base_runner` | every 5 s | paints the meetings/base layers, gated off while the alert is active |
| `button_listener` | continuous | boot button cycles `ZoomDayRenderer` zoom level |

Display is driven by a **topmost-wins layer stack** (`renderers/stack.py`, stdlib-only). Three layers, top first: `alert_layer` (occupied while `alert.is_active(now)`) → `meetings_layer` (occupied when the countdown or time-left has a frame) → `base_layer` (always occupied; `half_day_renderer`). Each layer's `paint()` is the single commit point — if occupied it draws + `display.commit()`, else no write. The two runners own disjoint layers (alert runner → alert layer only; base runner → the lower two, gated by `not alert.is_active(now)`), so their cadences are decoupled and the alert owns the commit while active.

Renderers (`renderers/`, all draw frames of 24 chars mapped to LEDs via the injected `Display` (`display/base.py`)):

- `StaticHalfDayRenderer(start_hour=8)` — **active**: half-hour resolution from 08:00; green = meeting start, yellow/red = now marker.
- `MeetingCountdown(countdown_min=10)` — **active**: green left-justified fill for the next event within 10 min of start.
- `MeetingTimeLeft` — **active**: red right-justified fill for fraction of current event remaining.
- `ZoomDayRenderer` — button-driven; zoom levels map to {60, 30, 15, 10} minutes/LED over a 24-LED window near "now".
- `MeetingCombined` — orphaned/experimental; not imported by `main.py`.

Data model: `EventsRepository.EVENTS` holds lists of `{"start", "end"}` as naive `time.struct_time`.
Events arrive as UTC ISO strings from Google; `iso_to_time_struct` strips the `Z`, then
`utc_to_local` (from `posix_tz.py`) converts to local wall-clock time at store time
(`load_events_from_google`). All-day events are filtered out unconditionally; Google out-of-office
events are filtered only when `secrets["filter_out_of_office"]` is true (opt-in, default off —
`EventsRepository` takes a `filter_out_of_office` kwarg, wired at `main.py`).

## Conventions & gotchas

- Follow existing style: `str.format()`, module-level driver objects, `gc.collect()` + memory log
  after heavy stages (2MB PSRAM board — avoid unbounded data; close HTTP responses).
- **Time handling is UTC-native; local conversion is explicit.** Device RTC holds UTC (NTP, no offset).
  `secrets["timezone"]` is a POSIX TZ string (e.g. `CST6CDT,M3.2.0/2:00,M11.1.0/2:00`);
  `main.py` parses it via `posix_tz.parse_posix_tz` (try/except → `tz=None` fallback = identity).
  `EventsRepository` converts events UTC→local at store (`load_events_from_google`) and converts
  `now` to local at query (`get_current_event`/`get_next_event`); all comparisons are local-vs-local.
  **Verify time assumptions before editing anything date/time related** — the B2 conversion point
  (store vs. query) must stay consistent across the codebase.
- `display/` (F1 seam): `frame_math.py` = pure stdlib frame math (plain lists, no
  numpy); `base.py` = `Display` contract (`set_frame` / `set_frame_from_text` / `progress`
  / `commit` — the three renderer methods are frozen by the test suite);
  `bicolor24.py` = first adapter (I2C init in `__init__`, diff-writes changed LEDs,
  `commit()` prints ASCII then `bc24.show()`); `selector.py` builds the adapter from
  `secrets["display"]` (default `bicolor24`; unknown name → `ValueError` at boot).
- **Frame LED notation:** represent a 24-LED frame in prose/notes with color-square emoji — ⬛ off, 🟥 red, 🟨 yellow, 🟩 green — a 1:1 stand-in for the digits `commit()` actually prints (`.`, `1`, `2`, `3`). Those digits are the palette ints from `adafruit_ht16k33` (`LED_OFF=0`, `LED_RED=1`, `LED_GREEN=2`, `LED_YELLOW=3`), emitted by `display/bicolor24.py` `commit()`. Prefer the emoji over a raw digit string when quoting a frame to a human.
- Google Calendar call in `gcal.py`: REST GET with `timeZone=UTC`, `singleEvents=true`,
  `orderBy=startTime`, `fields=items(start,end,eventType)`. `timeZone=UTC` is required because `iso_to_time_struct`
  strips `Z` only — it never parses offsets. `orderBy=startTime` is **required**: without it Google returns an
  "unspecified, stable order" — empirically a *partial* page that omits newly-created events (root cause of the
  2026-11-15 missing-events bug, see `.agents/notes/bug-repo-drops-to-1-of-3-events.md`).
  One-time re-auth: uncomment the `google_cal.initialize_client_keys()` line in `main.py` (device-code flow;
  prints URL + code, then outputs tokens to paste into `mysecrets.py`).
- `settings.toml` is currently an empty file (gitignored upstream); nothing reads it yet.
- `sd/placeholder.txt`: hidden from the Python namespace when a physical SD card is inserted (`/sd`).
  No SD functionality exists in current code.

## Backups

Four snapshots under `backups/day_meter-*`. Verified findings (method + details in
`.agents/notes/snapshot-timeline.md`):

- Root is **byte-for-byte identical** to `day_meter-2026-11-11` — that snapshot *is* the current device state.
- No backup contains source code newer than root; root is the furthest-along version.
- `day_meter-2025-07-28` uniquely holds an experimental env-configured `bargraph.py`, a displayio-based library stack, and bundle archives whose filenames date 2025-12-31 (newer than the folder name claims).
- `day_meter-2026-06-03` holds the original copies of `README.md` and `requirements.txt` (both restored to root on 2026-11-11; backup copies are historical), plus the **untouched original git repository** that was copied into this project's root on 2026-11-11.

## Version control

- Root is under git since 2026-11-11 (restored by copying `backups/day_meter-2026-06-03/.git` into root). Origin = `git@github.com:akoebbe/day-meter.git`; tip after restore = commit `30c1bf9`. The backup keeps its `.git` as a historical artifact.
- `.gitignore` excludes live secrets (`mysecrets.py`, `secrets.py`), `backups/`, compiled `lib/*`, `.vscode/`, `settings.toml`, and macOS artifacts. Note the Feb-2024 repo did **not** ignore `mysecrets.py`; that gap was fixed *before* the restore commit — keep it closed.
- Before committing anything: run `git status --porcelain` and confirm no `backups/`, `lib/`, `.vscode/`, or secrets paths are staged; never echo secret values into commit messages or logs.

## Planned features & development testing

- Backlog of six planned features (**not in priority order** — other display types beyond the bargraph;
  additional calendar sources such as Outlook; physical button/rotary-encoder input; overlapping/concurrent
  event rendering; configurable half-day window start hour; meeting-start alert animation) lives at
  `.agents/notes/features/roadmap.md`.
- The desktop automated test system for renderers (golden-frame tests, stdlib `unittest`, GitHub Actions CI)
  is planned in `.agents/notes/dev-testing-plan.md`; it lands before feature work begins.
- Shared architectural seams: a display abstraction (pure frame math + driver adapters — **shipped**,
  see `display/` package), injectable clock into repository queries (**shipped** — `now=` kwarg on
  `get_current_event`/`get_next_event`), and UTC-native time handling (**shipped** — POSIX TZ, B2
  conversion at store, see gotchas above). Each feature gets its own
  `.agents/notes/features/<topic>.md` when scoped.
- The topmost-wins **layer stack** (`renderers/stack.py`) — **shipped**: three layers (alert / meetings / base), single commit point per layer, cadences decoupled (smooth alert sweep at `alert_cadence_s`, base/meetings at 5 s). See the Architecture section above.

## Agent state directory

Persistent agent context lives in `.agents/`:

- `AGENTS.md` (this file) — standing instructions; keep it current when conventions change.
- `.agents/notes/snapshot-timeline.md` — evidence for the backup provenance record above.
- `.agents/notes/refactor-todo.md` — ten-item refactor working list (tiered A/B/C); check items off as they land.
- Future feature work: the shared backlog lives in `.agents/notes/features/roadmap.md`; individual `<topic>.md`
  notes get added there as each feature is scoped.
