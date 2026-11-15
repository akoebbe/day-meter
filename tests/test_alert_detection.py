"""Hermetic desktop tests for the MeetingAlert controller (roadmap F6 phase 2).

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

The controller's on_tick(repo, now) takes `now` as an explicit argument (the
injectable clock from the plan), so no wall-clock freeze is needed: tests drive
a sequence of local struct_times and check which events it reports as starting.

Semantics pinned from meeting_alert_controller.py:
  - First tick only records the baseline (_last_now is None) -> no alert on an
    already-running meeting.
  - Subsequent ticks query the half-open window [_last_now, now) via
    EventsRepository.get_events_starting_between(log=False): `event["start"] >=
    start and event["start"] < end`. Consecutive windows tile the timeline, so a
    start is counted exactly once (no double-count) and none is missed.
  - On a detection, the alert is active for duration_s after the tick's `now`
    (posix_tz.add_seconds), exclusive at the deadline.
  - An event starting exactly on a tick boundary is caught by the NEXT window
    (its start < now fails on the boundary tick, then >= prev on the next).
"""

import time
import unittest

import events
from meeting_alert_controller import MeetingAlert


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like the stored (local) event times."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


def mk_repo(pairs):
    repo = events.EventsRepository()
    repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in pairs])
    return repo


class BootstrapTest(unittest.TestCase):
    def test_first_tick_no_alert_on_running_meeting(self):
        # Meeting 09:00-10:00 is already running when the first tick is 09:30.
        # Bootstrap records the baseline but must NOT alert (plan: no alert on
        # already-running meetings).
        repo = mk_repo([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        started = alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))
        self.assertEqual(started, [])
        self.assertFalse(alert.is_active(st(2026, 11, 11, 9, 30, 0)))


class DetectionTest(unittest.TestCase):
    def test_start_within_window_detected_next_tick(self):
        # Baseline 09:30; a meeting starts 09:30:30 (inside [09:30, 09:31));
        # the tick at 09:31 reports exactly that one event and activates.
        repo = mk_repo([((2026, 11, 11, 9, 30, 30), (2026, 11, 11, 9, 32, 0))])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        self.assertEqual(alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0)), [])
        started = alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0))
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0]["start"], st(2026, 11, 11, 9, 30, 30))
        self.assertTrue(alert.is_active(st(2026, 11, 11, 9, 31, 0)))

    def test_start_exactly_on_boundary_caught_next_tick(self):
        # Event starts exactly at 09:31:00. Window [09:30, 09:31) excludes it
        # (start < now fails); window [09:31, 09:32) catches it (start >= prev).
        repo = mk_repo([((2026, 11, 11, 9, 31, 0), (2026, 11, 11, 9, 33, 0))])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))
        self.assertEqual(alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0)), [])
        started = alert.on_tick(repo, st(2026, 11, 11, 9, 32, 0))
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0]["start"], st(2026, 11, 11, 9, 31, 0))

    def test_no_double_count_across_ticking(self):
        # One start, three ticks: detected exactly once, on the tick whose
        # window contains it; later windows no longer contain the start.
        repo = mk_repo([((2026, 11, 11, 9, 30, 30), (2026, 11, 11, 9, 32, 0))])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        counts = [
            len(alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))),
            len(alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0))),
            len(alert.on_tick(repo, st(2026, 11, 11, 9, 32, 0))),
        ]
        self.assertEqual(counts, [0, 1, 0])

    def test_concurrent_starts_all_reported(self):
        # Two meetings both start inside [09:30, 09:31): both reported on the
        # one tick that straddles the window.
        repo = mk_repo([
            ((2026, 11, 11, 9, 30, 10), (2026, 11, 11, 9, 40, 0)),
            ((2026, 11, 11, 9, 30, 40), (2026, 11, 11, 9, 40, 0)),
        ])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))
        started = alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0))
        self.assertEqual(len(started), 2)
        self.assertTrue(alert.is_active(st(2026, 11, 11, 9, 31, 0)))


class ExpiryTest(unittest.TestCase):
    def test_active_within_duration_inactive_after(self):
        # Detection at 09:31:00 with duration_s=5 -> active until 09:31:05
        # (exclusive): active through 09:31:04, inactive from 09:31:05 on.
        repo = mk_repo([((2026, 11, 11, 9, 30, 30), (2026, 11, 11, 9, 32, 0))])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))
        alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0))
        self.assertTrue(alert.is_active(st(2026, 11, 11, 9, 31, 4)))
        self.assertFalse(alert.is_active(st(2026, 11, 11, 9, 31, 5)))
        self.assertFalse(alert.is_active(st(2026, 11, 11, 9, 32, 0)))

    def test_new_start_extends_activity(self):
        # While an alert is active, a second start re-arms the deadline.
        repo = mk_repo([
            ((2026, 11, 11, 9, 30, 30), (2026, 11, 11, 9, 40, 0)),
            ((2026, 11, 11, 9, 31, 30), (2026, 11, 11, 9, 40, 0)),
        ])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))
        alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0))     # first start at 09:30:30
        # second start 09:31:30 lands in [09:31, 09:32): re-armed to 09:32:05
        started = alert.on_tick(repo, st(2026, 11, 11, 9, 32, 0))
        self.assertEqual(len(started), 1)
        # Exclusive deadline 09:32:05 (same convention as the expiry test above):
        # active through 09:32:04, inactive from 09:32:05 on.
        self.assertTrue(alert.is_active(st(2026, 11, 11, 9, 32, 4)))
        self.assertFalse(alert.is_active(st(2026, 11, 11, 9, 32, 5)))


class ResetTest(unittest.TestCase):
    def test_reset_clears_state(self):
        repo = mk_repo([((2026, 11, 11, 9, 30, 30), (2026, 11, 11, 9, 32, 0))])
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        alert.on_tick(repo, st(2026, 11, 11, 9, 30, 0))
        alert.on_tick(repo, st(2026, 11, 11, 9, 31, 0))
        self.assertTrue(alert.is_active(st(2026, 11, 11, 9, 31, 0)))
        alert.reset()
        self.assertFalse(alert.is_active(st(2026, 11, 11, 9, 31, 0)))
        # After reset the next tick is a fresh bootstrap (no alert).
        self.assertEqual(alert.on_tick(repo, st(2026, 11, 11, 9, 32, 0)), [])


if __name__ == "__main__":
    unittest.main()
