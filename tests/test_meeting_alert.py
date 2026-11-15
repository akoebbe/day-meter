"""Hermetic desktop golden tests for the alert renderer (roadmap F6 phase 3).

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

The renderer's frame(now) is pure: it derives the yellow left-to-right sweep
fill from (now - alert_started) / alert.duration_s using time.mktime on the
injected structs, then bargraph.progress(frac, "y", "left", width=self.width).
The test drives mark_started(start) + frame(now) with explicit struct_times and
asserts the exact filled LED count. The fake recorder's progress mirrors
display/base.progress: floor(width * pct) yellow LEDs, the rest off,
left-justified (no flip).

Pinned sweep math (yellow = brightest bicolor, both RGB):
  width 24, elapsed 2s / duration 5s -> frac .4 -> floor(9.6) = 9
  width 24, elapsed 4s / duration 5s -> frac .8 -> floor(19.2) = 19
  width 12, elapsed 2s / duration 5s -> frac .4 -> floor(4.8) = 4
  width 8,  elapsed 2s / duration 5s -> frac .4 -> floor(3.2) = 3
  width 24, elapsed 5s / duration 5s -> frac 1.0 (clamped) -> floor(24.0) = 24
"""

import time
import unittest

import events
from fakes import FrameRecorder, frame_ascii
from renderers.meeting_alert import MeetingAlertRenderer
from meeting_alert_controller import MeetingAlert


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like the stored (local) event times."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


class AlertRendererTests(unittest.TestCase):
    def _setup(self, event_tuples, width=24):
        repo = events.EventsRepository()
        repo.load_events([{"start": st(*s), "end": st(*e)} for (s, e) in event_tuples])
        recorder = FrameRecorder()
        alert = MeetingAlert(duration_s=5, cadence_s=1)
        renderer = MeetingAlertRenderer(repo, recorder, alert, width)
        return renderer, alert

    def test_no_start_no_frame(self):
        # Before mark_started, frame is None (no alert to show).
        renderer, _ = self._setup(
            [((2026, 11, 11, 9, 30, 0), (2026, 11, 11, 10, 0, 0))])
        self.assertIsNone(renderer.frame(st(2026, 11, 11, 9, 30, 0)))

    def test_sweep_advances_across_cadence_steps(self):
        # Detection at 09:30:00; the sweep fill grows one cadence step at a time.
        # At elapsed 0s frac=0 -> 0 yellow; at 1s frac=.2 -> floor(4.8)=4; at
        # 2s frac=.4 -> floor(9.6)=9. Strictly increasing -> visible animation.
        renderer, _ = self._setup(
            [((2026, 11, 11, 9, 30, 0), (2026, 11, 11, 10, 0, 0))])
        renderer.mark_started(st(2026, 11, 11, 9, 30, 0))
        f0 = renderer.frame(st(2026, 11, 11, 9, 30, 0))
        f1 = renderer.frame(st(2026, 11, 11, 9, 30, 1))
        f2 = renderer.frame(st(2026, 11, 11, 9, 30, 2))
        self.assertEqual(frame_ascii(f0), "." * 24)
        self.assertEqual(frame_ascii(f1), "y" * 4 + "." * 20)
        self.assertEqual(frame_ascii(f2), "y" * 9 + "." * 15)
        self.assertEqual(frame_ascii(renderer.frame(st(2026, 11, 11, 9, 30, 4))),
                         "y" * 19 + "." * 5)
        self.assertEqual(frame_ascii(renderer.frame(st(2026, 11, 11, 9, 30, 5))),
                         "y" * 24)

    def test_width_12_golden_frame(self):
        # Width 12: elapsed 2s/5s -> frac .4 -> floor(12*.4)=4.
        renderer, _ = self._setup(
            [((2026, 11, 11, 9, 30, 0), (2026, 11, 11, 10, 0, 0))], width=12)
        renderer.mark_started(st(2026, 11, 11, 9, 30, 0))
        self.assertEqual(len(renderer.frame(st(2026, 11, 11, 9, 30, 2))), 12)
        self.assertEqual(frame_ascii(renderer.frame(st(2026, 11, 11, 9, 30, 2))),
                         "y" * 4 + "." * 8)

    def test_width_8_golden_frame(self):
        # Width 8: elapsed 2s/5s -> frac .4 -> floor(8*.4)=3.
        renderer, _ = self._setup(
            [((2026, 11, 11, 9, 30, 0), (2026, 11, 11, 10, 0, 0))], width=8)
        renderer.mark_started(st(2026, 11, 11, 9, 30, 0))
        self.assertEqual(len(renderer.frame(st(2026, 11, 11, 9, 30, 2))), 8)
        self.assertEqual(frame_ascii(renderer.frame(st(2026, 11, 11, 9, 30, 2))),
                         "y" * 3 + "." * 5)


if __name__ == "__main__":
    unittest.main()
