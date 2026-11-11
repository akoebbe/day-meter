# AGENTS.md — Day Meter

Instructions for AI agents (and humans) working in this repository.

## What this is

Day Meter is a CircuitPython application that renders your Google Calendar day on a
24-LED bicolor bargraph: meetings today, a 10-minute countdown to the next meeting,
and remaining time of the current meeting. It runs standalone on an ESP32 — no host PC
needed at runtime.

The project's human-readable README exists **only** inside `backups/day_meter-2026-06-03/README.md`
(it was lost from this root). Restore it to the root if desired, but do not assume its text
still matches current behavior without reviewing.

## Ground rules (read first)

1. **The root of this directory is the source of truth** — it mirrors what is currently
   flashed on the ESP32 device. `backups/` contains historical snapshots; their folder
   names and file dates are **not reliable**. Never auto-sync or restore from a backup
   into root without an explicit content diff review. See `.agents/notes/snapshot-timeline.md`
   for provenance evidence.
2. **Secrets handling is critical.** `mysecrets.py` contains live credentials
   (WiFi, Google OAuth client + access/refresh tokens, Google Calendar ID, Adafruit IO keys).
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

## Architecture

Boot sequence (top of `main.py`), each step in a retry loop with yellow bargraph feedback:

1. WiFi connect (secrets from `mysecrets.secrets`).
2. RTC set via Adafruit IO: `IO_HTTP(...).receive_time()` — **geolocated time, UTC fallback**
   (`adafruit_ntp` is imported-but-commented out; do not assume NTP).
3. Google OAuth token refresh: `gcal.refresh_token()` (OAuth2 refresh grant via `adafruit_oauth2`).
4. Async app loop (`asyncio.run(main())`); any unhandled exception resets the whole board by design.

| Task | Interval | Purpose |
|---|---|---|
| `refresh_token_runner` | every 15 min (`gcal.REFRESH_TIME`) | keeps Google access token valid |
| `event_fetcher` | every 300 s | pulls calendar events (yesterday→tomorrow window, max 40) into `EventsRepository` |
| `ticker` | every 5 s | renders active screens, then `bargraph.commit_frame()` |
| `button_listener` | continuous | boot button cycles `ZoomDayRenderer` zoom level |

Renderers (`renderers/`, all draw frames of 24 chars mapped to LEDs via `bargraph.py`):

- `StaticHalfDayRenderer(start_hour=8)` — **active**: half-hour resolution from 08:00; green = meeting start, yellow/red = now marker.
- `MeetingCountdown(countdown_min=10)` — **active**: green left-justified fill for the next event within 10 min of start.
- `MeetingTimeLeft` — **active**: red right-justified fill for fraction of current event remaining.
- `ZoomDayRenderer` — button-driven; zoom levels map to {60, 30, 15, 10} minutes/LED over a 24-LED window near "now".
- `StaticDayRenderer` — instantiated but **not** in the active ticker (commented out).
- `MeetingCombined` — orphaned/experimental; not imported by `main.py`.

Data model: `EventsRepository.EVENTS` holds lists of `{"start", "end"}` as naive `time.struct_time`,
converted from Google's UTC ISO strings (`iso_to_time_struct` strips the `Z`). All-day events are
filtered out; an `_is_out_of_office_event` filter exists but is **commented out** in
`_is_storable_g_event`.

## Conventions & gotchas

- Follow existing style: `str.format()`, module-level driver objects, `gc.collect()` + memory log
  after heavy stages (2MB PSRAM board — avoid unbounded data; close HTTP responses).
- **Time handling is delicate and partly inconsistent.** `secrets["timezone"]` (`America/Chicago`)
  is read into an unused variable in `main.py`; `base_renderer.py` has dead `UTC_OFFSET = -5` code;
  event times are UTC-parsed while comparisons use local `time.localtime()`. Whatever the exact
  behavior on-device, **verify time assumptions before editing anything date/time related**, and
  do not "clean up" these without confirming what actually renders correctly.
- `bargraph.py`: `set_frame` only writes changed LEDs; frames are ulab/numpy arrays with a
  CPython-numpy fallback import (`try: import numpy / except: from ulab ...`). The `WifiAnimation`
  class is dormant (`wifi_animation = False`) and **buggy** — it calls `WifiAnimation.tick()` without
  an instance. Fix before ever enabling it.
- Google Calendar call in `gcal.py`: REST GET with `singleEvents=true`, `fields=items(start,end,eventType)`.
  One-time re-auth: uncomment the `gcal.initialize_client_keys()` line in `main.py` (device-code flow;
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
- `day_meter-2026-06-03` uniquely holds the original **git repository** (commits from Feb 2024), plus `README.md`, `requirements.txt`, and `.gitignore` — all lost from root.

## Agent state directory

Persistent agent context lives in `.agents/`:

- `AGENTS.md` (this file) — standing instructions; keep it current when conventions change.
- `.agents/notes/snapshot-timeline.md` — evidence for the backup provenance record above.
- Future feature work: add short notes under `.agents/notes/features/<topic>.md` as features are scoped, and reference them from this file.
