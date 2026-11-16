"""Stack layer model tests -- foundation of the display layer stack.

Tests the topmost-wins occupancy rule and single-commit paint point
in renderers/stack.py. Run from repo root with no installs or board
hardware:
    python3 -m unittest discover tests
"""

import time
import unittest

from fakes import OFF, GREEN, RED, YELLOW
from renderers import stack as stack_mod


NOW = time.struct_time((2026, 11, 11, 9, 30, 0, 0, -1, -1))


class RecordingDisplay(object):
    """Display that records frames written and commits (no diff-write)."""

    def __init__(self):
        self.frames = []
        self.commits = 0

    def set_frame(self, frame):
        self.frames.append(list(frame))

    def set_frame_from_text(self, text):
        from fakes import COLOR_MAP
        self.set_frame([COLOR_MAP[c] for c in text])

    def progress(self, pct=0.5, color="g", justified="left", width=None):
        from math import floor
        from fakes import COLOR_MAP
        led_count = width if width is not None else 24
        filled = floor(led_count * pct)
        frame = [OFF] * led_count
        frame[:filled] = [COLOR_MAP[color]] * filled
        if justified == "right":
            frame = frame[::-1]
        return frame

    def commit(self):
        self.commits += 1


class StubRenderer(object):
    """Stub renderer recording which methods were called.

    Mimics the BaseRenderer interface: frame() returns a frame or None;
    render() writes the frame to the display (no commit).
    """

    def __init__(self, display, frame=None):
        self.display = display
        self.calls = []
        self._frame = frame

    def frame(self, now):
        self.calls.append("frame")
        return self._frame

    def render(self, now):
        self.calls.append("render")
        if self._frame is not None:
            self.display.set_frame(list(self._frame))


class FakeAlert(object):
    """Stand-in for meeting_alert_controller.MeetingAlert."""

    def __init__(self, active=False, duration_s=5):
        self._active = active
        self.duration_s = duration_s

    def is_active(self, now):
        return self._active


class StackTests(unittest.TestCase):
    """Tests for the layer stack model (renderers/stack.py)."""

    def test_topmost_wins_alert_occupied(self):
        """3-layer stack, alert occupied: alert paints, base does not.
        Exactly one frame and one commit; base renderer.render not called."""
        display = RecordingDisplay()
        base_renderer = StubRenderer(display, frame=[GREEN] * 24)
        alert_renderer = StubRenderer(display, frame=[YELLOW] * 24)
        fake_alert = FakeAlert(active=True)
        # Meetings layer in stack but not reached (break on alert)
        meetings = stack_mod.MeetingsLayer(
            None, StubRenderer(display, None), StubRenderer(display, None), cadence_s=5)

        alert_layer = stack_mod.AlertLayer(fake_alert, alert_renderer, cadence_s=0.2)
        base_layer = stack_mod.BaseLayer([base_renderer], cadence_s=5)
        stack = [alert_layer, meetings, base_layer]

        for layer in stack:
            if layer.paint(NOW, display):
                break

        # Exactly one frame (the alert's yellow), one commit
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(display.frames[0], [YELLOW] * 24)
        self.assertEqual(display.commits, 1)
        # Base renderer.render NOT called (short-circuit via break)
        self.assertEqual(base_renderer.calls, [])
        # Alert renderer.render WAS called
        self.assertEqual(alert_renderer.calls, ["render"])

    def test_topmost_wins_base_when_alert_not_occupied(self):
        """3-layer stack, alert not occupied, no meetings: base layer paints.
        Alert paint returns False (no frame, no commit from alert)."""
        display = RecordingDisplay()
        base_renderer = StubRenderer(display, frame=[GREEN] * 24)
        alert_renderer = StubRenderer(display, frame=[YELLOW] * 24)
        fake_alert = FakeAlert(active=False)
        # Meetings not occupied (stub renderers with frame=None)
        meetings = stack_mod.MeetingsLayer(
            None, StubRenderer(display, None), StubRenderer(display, None), cadence_s=5)

        alert_layer = stack_mod.AlertLayer(fake_alert, alert_renderer, cadence_s=0.2)
        base_layer = stack_mod.BaseLayer([base_renderer], cadence_s=5)
        stack = [alert_layer, meetings, base_layer]

        for layer in stack:
            if layer.paint(NOW, display):
                break

        # Exactly one frame (the base's green), one commit
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(display.frames[0], [GREEN] * 24)
        self.assertEqual(display.commits, 1)
        # Base renderer.render WAS called
        self.assertEqual(base_renderer.calls, ["render"])
        # Alert renderer.render NOT called (paint returned False)
        self.assertEqual(alert_renderer.calls, [])

    def test_meetings_last_writer_time_left_wins(self):
        """Both meeting renderers occupied: countdown.render before
        time_left.render; time-left frame is last written; one commit."""
        display = RecordingDisplay()
        countdown = StubRenderer(display, frame=[GREEN] * 24)
        time_left = StubRenderer(display, frame=[RED] * 24)

        meetings_layer = stack_mod.MeetingsLayer(None, countdown, time_left, cadence_s=5)

        painted = meetings_layer.paint(NOW, display)

        self.assertTrue(painted)
        self.assertEqual(display.commits, 1)
        # Two frames written: countdown (green) then time-left (red)
        self.assertEqual(len(display.frames), 2)
        self.assertEqual(display.frames[0], [GREEN] * 24)
        self.assertEqual(display.frames[1], [RED] * 24)
        # countdown: frame called during occupied, render during _draw
        self.assertIn("render", countdown.calls)
        self.assertIn("frame", countdown.calls)
        # time_left: render called during _draw
        self.assertIn("render", time_left.calls)

    def test_base_layer_uses_render_not_frame(self):
        """BaseLayer calls .render (not .frame) on its base renderers."""
        display = RecordingDisplay()
        base_renderer = StubRenderer(display, frame=[GREEN] * 24)
        base_layer = stack_mod.BaseLayer([base_renderer], cadence_s=5)

        base_layer.paint(NOW, display)

        self.assertIn("render", base_renderer.calls)
        self.assertNotIn("frame", base_renderer.calls)

    def test_alert_layer_cadence(self):
        """AlertLayer stores cadence_s from construction (0.2 default)."""
        alert_layer = stack_mod.AlertLayer(None, None, cadence_s=0.2)
        self.assertEqual(alert_layer.cadence_s, 0.2)


if __name__ == "__main__":
    unittest.main()
