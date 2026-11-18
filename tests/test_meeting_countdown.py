"""Hermetic desktop golden/no-op tests for MeetingCountdown -- Phase 4,
day-meter-dev-test-suite plan.

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

MeetingCountdown.render(now) takes its render time as an argument, but it
selects the next event via get_next_event() WITHOUT passing now -- so the
internal time.localtime() read is frozen via fakes.freeze_clock, which still
covers the repo's now=None query; the renderer itself computes sec_until via
posix_tz.local_delta on the frozen structs (no time.mktime left in renderers).

Semantics pinned from source: writes only when 0 < sec_until <= countdown_min*60,
then the renderer calls set_frame with that fill: exactly ONE frame is recorded per
write (progress computes/returns its frame; only set_frame records); no-write cases
leave frames empty and last_frame None. The fill is floor(24 * pct) green LEDs.

Matrix coverage notes vs the plan bullets: "exactly 10 min -> 24 LEDs, inclusive <="
is pinned directly; the matrix's "2 min -> 19 LEDs" bullet does not match this renderer
-- at 2 min out (pct .2) the fill is only floor(4.8)=4 LEDs, and a 19-LED fill occurs
at 8 min out (pct .8): both are pinned with corrected labels; "20 min -> no write" is
superseded by the real threshold countdown_min*60 (over 10 min suffices), plus an
explicit just-over-boundary pin at 601 s.

Progress fills: left-justified green, count = floor(24 * pct).
"""

import time
import unittest

import events
from fakes import FrameRecorder, freeze_clock, frame_ascii
from renderers.meeting_countdown import MeetingCountdown


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like iso_to_time_struct's output."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


NOW = st(2026, 11, 11, 9, 0, 0)


class MeetingCountdownTests(unittest.TestCase):
    def _render(self, event_tuples):
        repo = events.EventsRepository()
        repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in event_tuples])
        recorder = FrameRecorder()
        renderer = MeetingCountdown(repo, recorder, 10)   # countdown_min passed explicitly: annotation is not a default
        with freeze_clock(NOW):
            renderer.render(NOW)
        return recorder

    def test_five_minutes_out_half_fill(self):
        # 300 s -> pct .5 -> floor(12.0) = 12 green LEDs, left-justified.
        rec = self._render([((2026, 11, 11, 9, 5, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "g" * 12 + "." * 12)

    def test_eight_minutes_out_19_leds(self):
        # Matrix's "19 LEDs" bullet, corrected: a left fill of 19 needs pct in [19/24, 5/6),
        # i.e. 8 min out (pct .8 -> floor(19.2) = 19).
        rec = self._render([((2026, 11, 11, 9, 8, 0), (2026, 11, 11, 9, 30, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "g" * 19 + "." * 5)

    def test_two_minutes_out_small_fill(self):
        # Pinned current behavior: at 2 min out (pct .2) the fill is floor(4.8) = 4 LEDs --
        # NOT the matrix's "(19 LEDs)" attribution, which does not match this renderer.
        rec = self._render([((2026, 11, 11, 9, 2, 0), (2026, 11, 11, 9, 30, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "g" * 4 + "." * 20)

    def test_exact_10_min_boundary_inclusive_full_frame(self):
        # sec_until == countdown_min*60 is included (<=): pct 1.0 -> floor(24) = all green.
        rec = self._render([((2026, 11, 11, 9, 10, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "g" * 24)

    def test_just_over_boundary_no_write(self):
        # 601 s > 600: no progress call and no set_frame at all.
        rec = self._render([((2026, 11, 11, 9, 10, 1), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(rec.frames, [])
        self.assertIsNone(rec.last_frame)

    def test_far_event_beyond_countdown_window_no_write(self):
        # 20 min out (matrix bullet): far outside the real threshold; nothing written.
        rec = self._render([((2026, 11, 11, 9, 20, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertEqual(rec.frames, [])
        self.assertIsNone(rec.last_frame)

    def test_during_meeting_followup_within_window(self):
        # A started at 08:45 (ongoing), B starts in 4 min -> get_next_event (strict start > now)
        # returns B; the fill is computed toward B: pct .4 -> floor(9.6) = 9 green LEDs.
        rec = self._render([
            ((2026, 11, 11, 8, 45, 0), (2026, 11, 11, 9, 5, 0)),
            ((2026, 11, 11, 9, 4, 0), (2026, 11, 11, 9, 30, 0)),
        ])
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), "g" * 9 + "." * 15)

    def test_no_events_no_write(self):
        # get_next_event() returns None -> no progress call and no set_frame.
        rec = self._render([])
        self.assertEqual(rec.frames, [])
        self.assertIsNone(rec.last_frame)

    def _frame(self, event_tuples, width):
        repo = events.EventsRepository()
        repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in event_tuples])
        recorder = FrameRecorder()
        renderer = MeetingCountdown(repo, recorder, 10, width)
        with freeze_clock(NOW):
            return renderer.frame(NOW)

    def test_width_24_full_frame_via_frame(self):
        # frame() at width 24 == the render() golden: 5 min out (pct .5) -> 12 green.
        frame = self._frame([((2026, 11, 11, 9, 5, 0), (2026, 11, 11, 10, 0, 0))], 24)
        self.assertEqual(frame_ascii(frame), "g" * 12 + "." * 12)

    def test_width_12_half_fill(self):
        # Same 5-min-out event (pct .5) at width 12 -> floor(12*.5)=6 green.
        frame = self._frame([((2026, 11, 11, 9, 5, 0), (2026, 11, 11, 10, 0, 0))], 12)
        self.assertEqual(frame_ascii(frame), "g" * 6 + "." * 6)

    def test_width_8_half_fill(self):
        # Same 5-min-out event (pct .5) at width 8 -> floor(8*.5)=4 green.
        frame = self._frame([((2026, 11, 11, 9, 5, 0), (2026, 11, 11, 10, 0, 0))], 8)
        self.assertEqual(frame_ascii(frame), "g" * 4 + "." * 4)

    def test_frame_at_width_11_half_fill(self):
        # Same 5-min-out event (pct .5) via frame_at at width 11 -> floor(5.5) green.
        repo = events.EventsRepository()
        repo.load_events([{"start": st(2026, 11, 11, 9, 5, 0), "end": st(2026, 11, 11, 10, 0, 0)}])
        recorder = FrameRecorder()
        renderer = MeetingCountdown(repo, recorder, 10)
        with freeze_clock(NOW):
            frame = renderer.frame_at(NOW, 11)
        self.assertEqual(frame_ascii(frame), "g" * 5 + "." * 6)

    def test_frame_at_width_7_half_fill(self):
        # Same 5-min-out event (pct .5) via frame_at at width 7 -> floor(3.5) green.
        repo = events.EventsRepository()
        repo.load_events([{"start": st(2026, 11, 11, 9, 5, 0), "end": st(2026, 11, 11, 10, 0, 0)}])
        recorder = FrameRecorder()
        renderer = MeetingCountdown(repo, recorder, 10)
        with freeze_clock(NOW):
            frame = renderer.frame_at(NOW, 7)
        self.assertEqual(frame_ascii(frame), "g" * 3 + "." * 4)


if __name__ == "__main__":
    unittest.main()
