# Refactor Todo — Day Meter

Working list of ten refactor items, tiered by value. Check items off as they land.

## Tier A — Correctness (do first)

- [x] **1. `secrets.py.dist` template drift → fresh-install KeyError**
  `gcal.py:21` reads `secrets['google_calendar']` at import, but the template lacks that key
  (and still carries the unused `google_auth_user`). A fresh install from the template dies with
  `KeyError: 'google_calendar'`.
  Fix: add `'google_calendar' : ''` (comment style like the others), delete the
  `google_auth_user` line. Do NOT touch `mysecrets.py`.
  Verify: desktop test that the gcal import path works against a template-shaped secrets dict.

- [ ] **2. Renderer duration math mixes wall-clock + `time.mktime`**
  `renderers/meeting_countdown.py:20`, `renderers/meeting_time_left.py:21-22`,
  `renderers/meeting_alert.py:28` (and `renderers/meeting_combined.py:16,25-26` if that file
  survives item 5). Events and `now` are local wall-clock `struct_time`, but durations go
  through `time.mktime`, which is tz-free on the board. Correct only while `now` and the event
  share the same DST state — latent today (windows don't cross a transition), wrong across a
  DST boundary.
  Fix: one DST-aware local-time delta helper in `posix_tz.py`; replace all four call sites.
  Keep `tz=None` identity semantics (repo queries fall back to `utc_to_local(..., self.tz)`).
  Verify: desktop test with `now` and an event straddling a DST edge.

## Tier B — Dead/broken code removal (low risk; grep-verified no live importers)

- [ ] **3. `main.py` `calendar_checker` (lines 178-191)** — defined but never scheduled
  (`main()` creates only refresh_token/event_fetcher/alert/base/button tasks), and buggy
  anyway: `now = time.localtime()` is UTC while event starts are local. Delete the function.

- [ ] **4. `bicolor24.py` `WifiAnimation` block (lines 43-69) + `import asyncio`** — dormant
  and broken: `WifiAnimation.tick()` is called on the class, and `np` / `bc24` / `set_frame` /
  `commit_frame` are all undefined at that scope. Delete the class, the module flag, and the
  `asyncio` import it was the only user of.

- [ ] **5. `renderers/meeting_combined.py`** — orphaned (no importer) and a broken duplicate
  of countdown + time-left (`get_next_event()` with no `now` arg and no None-guard).
  ⚠️ Owner decision: `.agents/notes/features/concurrent-meetings-columns.md:256` pins it as
  "stays orphaned; revisit only if the owner wants it later." Delete only if the owner approves.
  If it stays, item 2 still fixes its `mktime` calls.

- [ ] **6. `renderers/static_day_renderer.py`** — imported at `main.py:10` but the
  instantiation (`main.py:113`) is commented out and it is never in the ticker. Delete the
  file and the import entry.

- [ ] **7. `renderers/base_renderer.py:4-10`** — commented `adafruit_datetime` block and
  `UTC_OFFSET = -5`; AGENTS.md already flags the constant as dead/harmless. Delete lines 4-10,
  keep the live imports at 1-3.

## Tier C — Structural seams (unblock roadmap F2/F3)

- [ ] **8. `gcal.py` side-effectful module-level init** — `pool`/`requests` (:15-17),
  `CALENDAR_ID` (:21), duplicated `scopes` (:18 and :30), `google_auth = OAuth2(...)`
  (:31-38). Everything builds at import, so the module can't be imported without wifi+secrets.
  F2 (Outlook) needs a calendar-source adapter behind `EventsRepository`.
  Fix: encapsulate into a `GoogleCalendar` class (auth + fetch encapsulated; secrets + session
  injected at boot); keep `refresh_token_runner` (main.py) working against the injected object;
  keep `initialize_client_keys` (:40, one-time re-auth) reachable.
  Verify: desktop import of the new class against a fake HTTP session.

- [ ] **9. `events.py` `EventsRepository` cleanup** — drop the dead class attribute
  `EVENTS = []` and the stale `# TODO: Make this a class` (:6-7). Two load paths:
  `load_events` (:14, used by tests) vs `load_events_from_google` (:17, production);
  keep both or reconcile deliberately — don't change the Google-JSON contract.
  This module is the F2 normalization boundary; tighten it before F2 lands.

- [ ] **10. `main.py` boot: factor the retry loops + drop the dead `requests` Session**
  — the wifi (:45-53), NTP (:68-80), and token (:91-100) steps are three hand-rolled
  `while True` loops with the same yellow-progress / `display.progress` pattern; factor a
  retry helper. Also `requests = ...` at :62 (with its `ssl` context) is never read — `gcal`
  builds its own session — so it is wasted work on a 2 MB PSRAM board. Delete it, then trim
  the now-dead `import ssl` / `import adafruit_requests` from main.py (keep the NTP uses).

## Verification (apply to every item)

- Desktop: `python3 -m unittest discover tests` from the repo root (stdlib-only, no pip).
- On-device: copy changed `.py` files to the CIRCUITPY volume; watch serial — per-stage
  `Mem Free` prints, and a healthy boot ends in the 5 s asyncio tick log.
- Commit hygiene: `git status --porcelain`; confirm no `backups/`, `lib/`, `.vscode/`, or
  secret paths are staged; no secret values in commit messages.

## Not in the top 10 (minor)

- `iso_to_time_struct` offset-string fragility (events.py) — documented/pinned behavior, strips
  `Z` only; leave alone.
- `MeetingAlert.cadence_s` is stored (meeting_alert_controller.py) but unused — `alert_runner`
  reads the secret directly; optional tidy.
