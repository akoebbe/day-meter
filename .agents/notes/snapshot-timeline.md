# Snapshot timeline & provenance (verified 2026-11-11)

Folder names and file mtime in `backups/` are **untrusted** (per owner). The era of each
snapshot is determined from *content*: `boot_out.txt` board/firmware banner, git history,
and source diffs. Method: byte-level `diff`/`md5sum` between root and every backup, plus
`git log` inside the one snapshot containing a repo.

## Headline findings

1. **Root == `backups/day_meter-2026-11-11`.** All source files are byte-for-byte identical,
   including `mysecrets.py` (md5 match verified on at least `main.py`). The 11-11 snapshot is a
   faithful copy of the current device state. **Nothing in any backup supersedes root.**
2. **Root is the furthest-along version.** Each older snapshot's sources are strict subsets /
   earlier iterations (directionality verified per file below).
3. **Version control restored to root on 2026-11-11.** `.git` was *copied* from `day_meter-2026-06-03/.git`
   into project root; origin `akoebbe/day-meter.git` was verified exactly at d3e8d93 before committing, then
   new commit 30c1bf9 (current device state) was pushed. The 2024 `.gitignore` gap for `mysecrets.py` was
   fixed before staging; secret scan across all objects found zero token-like strings, and no live-secrets
   file was ever in the 2024 trees.

## Snapshot table (evidence-derived, not name-derived)

| Folder | Board & firmware (from its `boot_out.txt`) | Era | Distinctive content vs root |
|---|---|---|---|
| `day_meter-2026-06-03` | QT Py ESP32 **PICO**, CP **8.0.0-rc.2** (2023) | Original dev era | .git/ repo (**copied to project root 2026-11-11**; this remains the historical original): commits c437396 "Initial commit of my 'works for me' version" (2024-02-01), cf197fb "Added readme and requirements.txt", d3e8d93 "Corrected cost estimation" (both 2024-02-09); remote `git@github.com:akoebbe/day-meter.git`. Snapshot working tree had **uncommitted** changes to `main.py`, `gcal.py`, `bargraph.py`, `renderers/base_renderer.py`, `requirements.txt`. Only place with `README.md`, `requirements.txt`, `.gitignore` (ignores `secrets.py`, `settings.toml`, `lib/*`, `.vscode/` — **not** `mysecrets.py`). Its `events.py` has the out-of-office filter *enabled* (root: commented out). `.Trash-1000/files/` holds `renderers_old.py` and `adafruit_button` libs (abandoned experiment). `main.py` here is the oldest layout (renderer init before WiFi setup, no retry loops). |
| `day_meter-2025-05-06` | QT Py ESP32 **PICO**, CP 9.2.7 (UID CAB0BF96D503) | PICO-era on new firmware | `main.py`/`gcal.py` older than root: no retry loops, no yellow-progress feedback, no `initialize_client_keys()`. `events.py`, all renderers, `bargraph.py`, and the whole `lib/` set are identical to root. |
| `day_meter-2025-07-28` | QT Py ESP32-**S3** 4MB/2MB PSRAM (UID 4F21AFA5A3C1 — same UID as current), CP 9.2.7 | Board-migration era + experiments | Sources slightly older than root (`gcal.py` lacks `initialize_client_keys()`; no one-time-oauth comment in `main.py`). **Experiment artifacts lost from root:** a ~238-line `bargraph.py` configured via `os.getenv` helpers, plus extra libs: `adafruit_displayio_layout`, `adafruit_display_shapes`, `adafruit_display_text`, `adafruit_imageload`, `adafruit_bitmap_font`, `adafruit_ads1x15`. Contains `libArchive/` (Adafruit bundle zips whose names date **2025-12-31** — i.e., this folder received a library refresh later than its name implies) and `stubArchive/circuitpython_stubs-10.0.3.tar.gz`. |
| `day_meter-2026-11-11` | Same as root banner (S3, CP 9.2.7) | **Current state** | Byte-for-byte identical to root across all compared files. Has an empty `.Trash-*` entry; otherwise a mirror of the device. |

## Directionality notes (who added what, and when — inferred from content order)

- PICO→S3 migration happened between the 05-06-era state and the 07-28-era state (different
  board UIDs in boot banners).
- Retry loops + yellow bargraph feedback on boot failures: present only in root/11-11 (added after 05-06; also absent from 06-03).
- `gcal.initialize_client_keys()` one-time device-code re-auth helper: root-only among current-line sources.
- The out-of-office event filter was enabled at some point (visible in the 06-03 working tree) and is commented out in all current-line states.

## Recoverable "lost" artifacts inventory

Lost from root but safely recoverable (content reviewed before use):

| Item | Where | Caveat |
|---|---|---|
| `README.md` (project description, hardware list, circup workflow) | `day_meter-2026-06-03/README.md` | Written Feb 2024; behavior described may lag current code. |
| `requirements.txt` (circup library pin list) | `day_meter-2026-06-03/requirements.txt` | Pins predate the Dec 2025 lib refresh found in 07-28; don't re-pin root from it blindly. |
| `.gitignore` | `day_meter-2026-06-03/.gitignore` | Ignores `secrets.py` but **not** `mysecrets.py` — fix before restoring any git history (live-secrets gap). |
| Original git repo/history | `day_meter-2026-06-03/.git/` (historical copy) — **canonical repo now lives in project root** since 2026-11-11 | 3 commits, Feb 2024, + restore commit 30c1bf9; snapshot working tree had further uncommitted changes. |
| Env-configured experimental bargraph + displayio stack | `day_meter-2025-07-28/{bargraph.py,lib/}` | Abandoned experiment; useful reference only if that direction resumes. |
| `renderers_old.py`, `adafruit_button` libs | `day_meter-2026-06-03/.Trash-1000/files/` | Trashed by the original developer. |

## Rules for future work on backups

- Treat root as canonical; any restore = explicit, reviewed, per-file diff first.
- **Never** copy `mysecrets.py` from a backup (snapshots hold different/stale credentials).
- If git is restored in this project, add `mysecrets.py` to `.gitignore` before committing anything.
- Re-verify claims here with the same methods if the backups directory changes.
