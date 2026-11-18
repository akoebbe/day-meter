"""Hermetic desktop golden/no-op tests for MeetingTimeLeft -- Phase 5,
day-meter-dev-test-suite plan.

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

MeetingTimeLeft.render(now) calls get_current_event() WITHOUT passing now -- the
internal time.localtime() read is frozen via fakes.freeze_clock; the duration
deltas come from posix_tz.local_delta on the stored local structs (the tz=None
repo path is the plain struct-field delta, matching the fake mktime math)

Semantics pinned from source (renderers/meeting_time_left.py): writes only when a
current event exists; pct = sec_left/sec_total with sec_* from posix_tz.local_delta on
the frozen structs, then progress(pct, "r", "right") + set_frame -- exactly ONE frame
recorded per write. Right-justified red fill: floor(24 * pct) trailing red LEDs, the
rest off (leading).

Zero-length-event note (documented only, no fixture pinned per plan scope): such an
event would make sec_total 0 and divide by zero at the pct line if it were current --
but strict-interior selection can never return a start == end event, so this path is
unreachable via render.

Current-event selection is STRICTLY INTERIOR to the event span (pinned from
events.py): `event['start'] < now AND event['end'] > now`. Consequences pinned below:
start == now or end == now is NOT current (no write), and pct can never reach exactly
1.0 -- a full 24-LED red frame is therefore unreachable through this renderer; the two
boundary no-write pins replace what an inclusive-start golden would have been.
All fixtures use fixed NOW = 2026-11-11 09:30:00.
"""

import time
import unittest

import events
import posix_tz
from fakes import FrameRecorder, freeze_clock, frame_ascii
from renderers.meeting_time_left import MeetingTimeLeft


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like iso_to_time_struct's output."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


NOW = st(2026, 11, 11, 9, 30, 0)


class MeetingTimeLeftTests(unittest.TestCase):
    def _render(self, event_tuples):
        repo = events.EventsRepository()
        repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in event_tuples])
        recorder = FrameRecorder()
        renderer = MeetingTimeLeft(repo, recorder)
        with freeze_clock(NOW):
            renderer.render(NOW)
        return recorder

    def test_start_boundary_exclusive_no_write(self):
        # Meeting starting exactly at NOW: the current-event predicate is strict
        # (start < now), so this is NOT current -> no progress call and no set_frame.
        rec = self._render([((2026, 11, 11, 9, 30, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(rec.frames, [])
        self.assertIsNone(rec.last_frame)

    def test_early_meeting_mostly_red(self):
        # Meeting started at 09:24 (6 min before NOW), ends 10:00: sec_total = 2160 s,
        # sec_left = 1800 s -> pct 5/6 ~ .8333 -> floor(20.0) = exactly 20 trailing reds,
        # 4 leading off. (early/mostly-red state per plan matrix)
        rec = self._render([((2026, 11, 11, 9, 24, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "." * 4 + "r" * 20)

    def test_mid_meeting_half_red(self):
        # Meeting 09:00-10:00 seen from NOW (halfway): sec_left = 1800 s of 3600 s ->
        # pct .5 -> floor(12.0) = 12 trailing reds, 12 leading off (right-justified
        # mirror of a left half fill). (mid state per plan matrix)
        rec = self._render([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "." * 12 + "r" * 12)

    def test_near_end_small_right_fill(self):
        # Meeting 09:18-09:33 seen from NOW (ends in 3 min): sec_total = 900 s,
        # sec_left = 180 s -> pct .2 -> floor(4.8) = 4 trailing reds, 20 leading off.
        # (near-end state per plan matrix)
        rec = self._render([((2026, 11, 11, 9, 18, 0), (2026, 11, 11, 9, 33, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "." * 20 + "r" * 4)

    def test_no_current_event_no_write(self):
        # Only an upcoming event (start > now): get_current_event() returns None ->
        # no progress call and no set_frame.
        rec = self._render([((2026, 11, 11, 10, 0, 0), (2026, 11, 11, 11, 0, 0))])
        self.assertEqual(rec.frames, [])
        self.assertIsNone(rec.last_frame)

    def test_ended_exclusive_end_no_write(self):
        # Event ending exactly at NOW: strict `end > now` predicate fails -> not current
        # -> no write (boundary twin of the start test above).
        rec = self._render([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 9, 30, 0))])
        self.assertEqual(rec.frames, [])
        self.assertIsNone(rec.last_frame)

    def _frame(self, event_tuples, width):
        repo = events.EventsRepository()
        repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in event_tuples])
        recorder = FrameRecorder()
        renderer = MeetingTimeLeft(repo, recorder, width)
        with freeze_clock(NOW):
            return renderer.frame(NOW)

    def test_width_24_half_red_via_frame(self):
        # Mid-meeting (09:00-10:00 from 09:30) -> pct .5; width 24 -> 12 trailing red.
        frame = self._frame([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))], 24)
        self.assertEqual(frame_ascii(frame), "." * 12 + "r" * 12)

    def test_width_12_half_red(self):
        # Same mid-meeting event (pct .5) at width 12 -> floor(6) trailing red.
        frame = self._frame([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))], 12)
        self.assertEqual(frame_ascii(frame), "." * 6 + "r" * 6)

    def test_width_8_half_red(self):
        # Same mid-meeting event (pct .5) at width 8 -> floor(4) trailing red.
        frame = self._frame([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))], 8)
        self.assertEqual(frame_ascii(frame), "." * 4 + "r" * 4)

    def test_frame_at_width_11_half_red(self):
        # Same mid-meeting event (pct .5) via frame_at at width 11 -> floor(5.5) trailing red.
        repo = events.EventsRepository()
        repo.load_events([{"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)}])
        recorder = FrameRecorder()
        renderer = MeetingTimeLeft(repo, recorder)
        with freeze_clock(NOW):
            frame = renderer.frame_at(NOW, 11)
        self.assertEqual(frame_ascii(frame), "." * 6 + "r" * 5)

    def test_frame_at_width_7_half_red(self):
        # Same mid-meeting event (pct .5) via frame_at at width 7 -> floor(3.5) trailing red.
        repo = events.EventsRepository()
        repo.load_events([{"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)}])
        recorder = FrameRecorder()
        renderer = MeetingTimeLeft(repo, recorder)
        with freeze_clock(NOW):
            frame = renderer.frame_at(NOW, 7)
        self.assertEqual(frame_ascii(frame), "." * 4 + "r" * 3)

    def test_frame_for_event_matches_first_current(self):
        # The column path: frame_for_event on each stored event vs the singular
        # frame() (first current by start).
        repo = events.EventsRepository()
        repo.load_events([
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 9, 30, 0), "end": st(2026, 11, 11, 11, 0, 0)},
        ])
        recorder = FrameRecorder()
        renderer = MeetingTimeLeft(repo, recorder)
        with freeze_clock(NOW):
            self.assertEqual(
                renderer.frame_for_event(repo.get_current_events(now=NOW)[0], NOW, 24),
                renderer.frame(NOW))
    def test_dst_crossing_durations_tz_aware(self):
        # tz-aware repo (Chicago): a 01:00-06:00 wall span on 2026-11-01 crosses
        # the fall transition (CDT->EST). Durations must be real elapsed seconds,
        # not the wall-clock difference:
        #   sec_total = local_delta(01:00 -> 06:00) = 21600 s (06:00Z -> 12:00Z)
        #   sec_left  = local_delta(04:00 -> 06:00) =  7200 s (10:00Z -> 12:00Z)
        #   pct = 7200/21600 = 1/3 -> floor(24 * pct) = 8 trailing red.
        # No freeze_clock: `now` is passed explicitly, so the repo's
        # time.localtime() fallback is never hit.
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        repo = events.EventsRepository(tz=tz)
        repo.load_events([{"start": st(2026, 11, 1, 1, 0, 0),
                            "end": st(2026, 11, 1, 6, 0, 0)}])
        renderer = MeetingTimeLeft(repo, FrameRecorder())
        now = st(2026, 11, 1, 4, 0, 0)
        frame = renderer.frame(now)
        self.assertEqual(frame_ascii(frame), "." * 16 + "r" * 8)


if __name__ == "__main__":
    unittest.main()
