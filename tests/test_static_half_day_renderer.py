"""Hermetic desktop golden-frame tests for StaticHalfDayRenderer -- Phase 3,
day-meter-dev-test-suite plan.

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

All frames are machine-computed goldens (real renderer code + FrameRecorder).
No wall clock is read anywhere in these tests: render(now) receives its time
argument explicitly and start_of_hour/end_of_hour are pure struct math.

Window semantics pinned from the source: window = [08:00:00, 19:59:59] on now's
date; one green LED per event start at ((hour-8)*2)+floor(minute/30); a yellow
"now" marker (red when it lands on an already-green LED) written only while
start <= now < end. Note the plan matrix's "09:30 over 09:00 meeting -> red"
expectation is NOT what the code does: green marks event STARTS only, so at
09:30 the marker sits on its own empty LED and is yellow (case 3 pins this).
"""

import time
import unittest

import events
from fakes import FrameRecorder, frame_ascii
from renderers.static_half_day_renderer import StaticHalfDayRenderer


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like iso_to_time_struct's output."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


class StaticHalfDayRendererTests(unittest.TestCase):
    def _renderer(self, event_tuples):
        repo = events.EventsRepository()
        repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in event_tuples])
        recorder = FrameRecorder()
        return StaticHalfDayRenderer(repo, recorder, 8), recorder

    def _check(self, renderer, recorder, expected_ascii):
        renderer.render(st(2026, 11, 11, self.NOW_H, self.NOW_M, self.NOW_S))
        self.assertEqual(len(recorder.frames), 1)          # exactly one frame written
        self.assertEqual(frame_ascii(recorder.last_frame), expected_ascii)

    def test_empty_day_noon_yellow_marker(self):
        # No events; marker at 12:00 -> LED ((12-8)*2)+0 = 8.
        self.NOW_H, self.NOW_M, self.NOW_S = 12, 0, 0
        renderer, recorder = self._renderer([])
        self._check(renderer, recorder, ("." * 8) + "y" + ("." * 15))

    def test_meeting_starting_exactly_now_red_over_green(self):
        # 09:00 event at LED 2; now == start -> marker overwrites green with red.
        self.NOW_H, self.NOW_M, self.NOW_S = 9, 0, 0
        renderer, recorder = self._renderer([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))])
        self._check(renderer, recorder, ("." * 2) + "r" + ("." * 21))

    def test_now_mid_meeting_yellow_on_own_led(self):
        # Pinned current behavior: green marks the event START (LED 2 only); at 09:30 the
        # marker lands on LED 3 (empty) and is yellow -- not red-over-green.
        self.NOW_H, self.NOW_M, self.NOW_S = 9, 30, 0
        renderer, recorder = self._renderer([((2026, 11, 11, 9, 0, 0), (2026, 11, 11, 10, 0, 0))])
        self._check(renderer, recorder, ("." * 2) + "gy" + ("." * 20))

    def test_0800_window_start_boundary_and_prewindow_exclusion(self):
        # A 07:30 event is outside the window (no LED); a 08:00 event maps to LED 0 and at
        # now == 08:00:00 the marker lands on it -> red.
        self.NOW_H, self.NOW_M, self.NOW_S = 8, 0, 0
        renderer, recorder = self._renderer([
            ((2026, 11, 11, 7, 30, 0), (2026, 11, 11, 7, 59, 0)),
            ((2026, 11, 11, 8, 0, 0), (2026, 11, 11, 8, 30, 0)),
        ])
        self._check(renderer, recorder, "r" + ("." * 23))

    def test_late_event_near_window_end(self):
        # Event starting 19:30 -> LED ((19-8)*2)+1 = 23 (last); now at 15:00 -> marker LED 14.
        self.NOW_H, self.NOW_M, self.NOW_S = 15, 0, 0
        renderer, recorder = self._renderer([((2026, 11, 11, 19, 30, 0), (2026, 11, 11, 20, 0, 0))])
        self._check(renderer, recorder, ("." * 14) + "y" + ("." * 8) + "g")

    def test_now_past_window_end_no_marker(self):
        # now = 20:30 >= end (19:59:59): marker guard fails; the 19:00 event (LED 22) still
        # renders green.
        self.NOW_H, self.NOW_M, self.NOW_S = 20, 30, 0
        renderer, recorder = self._renderer([((2026, 11, 11, 19, 0, 0), (2026, 11, 11, 19, 30, 0))])
        self._check(renderer, recorder, ("." * 22) + "g" + ".")

    def test_marker_one_second_before_window_end(self):
        # Boundary pin: end is 19:59:59 (end_of_hour(now, 19)), so at 19:59:58 the marker
        # still writes -- on LED ((19-8)*2)+floor(59/30) = 23.
        self.NOW_H, self.NOW_M, self.NOW_S = 19, 59, 58
        renderer, recorder = self._renderer([])
        self._check(renderer, recorder, ("." * 23) + "y")


if __name__ == "__main__":
    unittest.main()
