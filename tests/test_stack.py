"""Stack layer model tests -- foundation of the display layer stack.

Tests the topmost-wins occupancy rule and single-commit paint point
in renderers/stack.py. Run from repo root with no installs or board
hardware:
    python3 -m unittest discover tests
"""

import time
import unittest

from fakes import OFF, GREEN, RED, YELLOW, frame_ascii, freeze_clock
from renderers import stack as stack_mod
import events
from renderers.meeting_countdown import MeetingCountdown
from renderers.meeting_time_left import MeetingTimeLeft


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like iso_to_time_struct's output."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


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
        # Meetings layer in stack but not reached (break on alert); needs a
        # real repo because occupied() queries the current events.
        repo = events.EventsRepository()
        repo.load_events([])
        meetings = stack_mod.MeetingsLayer(
            repo, StubRenderer(display, None), StubRenderer(display, None), cadence_s=5)

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
        # Meetings not occupied (empty repo; stub renderers frame=None).
        repo = events.EventsRepository()
        repo.load_events([])
        meetings = stack_mod.MeetingsLayer(
            repo, StubRenderer(display, None), StubRenderer(display, None), cadence_s=5)

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

    def _meetings_layer(self, display, events_list):
        repo = events.EventsRepository()
        repo.load_events(events_list)
        countdown = MeetingCountdown(repo, display, 10)
        time_left = MeetingTimeLeft(repo, display)
        return stack_mod.MeetingsLayer(repo, countdown, time_left, cadence_s=5)

    def test_meetings_compose_single_current_full_width(self):
        """One current event (50% left): one composed full-width frame,
        one commit, one set_frame."""
        display = RecordingDisplay()
        layer = self._meetings_layer(display, [
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
        ])
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(len(display.frames[0]), 24)
        self.assertEqual(frame_ascii(display.frames[0]), "." * 12 + "r" * 12)
        self.assertEqual(display.commits, 1)

    def test_meetings_compose_two_currents_with_gutter(self):
        """Two concurrent 50% events (earliest start = 08:30 -> leftmost,
        Reading A): [12, 11] layout, OFF gutter at index 12, one frame,
        one commit."""
        display = RecordingDisplay()
        layer = self._meetings_layer(display, [
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 8, 30, 0), "end": st(2026, 11, 11, 10, 30, 0)},
        ])
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(frame_ascii(display.frames[0]),
                         "." * 6 + "r" * 6 + "." * 7 + "r" * 5)
        self.assertEqual(display.frames[0][12], OFF)
        self.assertEqual(display.commits, 1)

    def test_meetings_compose_three_currents_with_gutters(self):
        """Three concurrent 50% events (by start 08:00/08:30/09:00 ->
        left-to-right, Reading A): [8, 7, 7] layout, OFF gutters at 8 and
        16, one frame, one commit."""
        display = RecordingDisplay()
        layer = self._meetings_layer(display, [
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 8, 30, 0), "end": st(2026, 11, 11, 10, 30, 0)},
            {"start": st(2026, 11, 11, 8, 0, 0), "end": st(2026, 11, 11, 11, 0, 0)},
        ])
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(frame_ascii(display.frames[0]),
                         "." * 4 + "r" * 4 + "." * 5 + "r" * 3 + "." * 5 + "r" * 3)
        self.assertEqual(display.frames[0][8], OFF)
        self.assertEqual(display.frames[0][16], OFF)
        self.assertEqual(display.commits, 1)

    def test_meetings_compose_current_plus_countdown_right_column(self):
        """Current 50% event + a next event 5 min out: [12, 11] layout, red
        current left column, green countdown RIGHT column (Reading A)."""
        display = RecordingDisplay()
        layer = self._meetings_layer(display, [
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 9, 35, 0), "end": st(2026, 11, 11, 10, 0, 0)},
        ])
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(frame_ascii(display.frames[0]),
                         "." * 6 + "r" * 6 + "." + "g" * 5 + "." * 6)
        self.assertEqual(display.commits, 1)

    def test_meetings_no_events_not_occupied(self):
        """No current events and no imminent countdown: paint returns False
        (no frame written, no commit)."""
        display = RecordingDisplay()
        layer = self._meetings_layer(display, [])
        with freeze_clock(NOW):
            self.assertFalse(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 0)
        self.assertEqual(display.commits, 0)

    def test_meetings_four_currents_shows_earliest_three(self):
        """Four concurrent events: capped at max_columns (3), earliest start
        -> leftmost; the extra (09:20 start, ~83% left) is dropped. The
        frame is the all-50% three-column one - it would differ if the
        dropped event were included."""
        display = RecordingDisplay()
        layer = self._meetings_layer(display, [
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 8, 30, 0), "end": st(2026, 11, 11, 10, 30, 0)},
            {"start": st(2026, 11, 11, 8, 0, 0), "end": st(2026, 11, 11, 11, 0, 0)},
            {"start": st(2026, 11, 11, 9, 20, 0), "end": st(2026, 11, 11, 10, 20, 0)},
        ])
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(frame_ascii(display.frames[0]),
                         "." * 4 + "r" * 4 + "." * 5 + "r" * 3 + "." * 5 + "r" * 3)
        self.assertEqual(display.commits, 1)

    def test_meetings_max_columns_two(self):
        """max_columns=2: four concurrent events collapse to the two earliest
        by start in a [12, 11] layout (same 2-column frame as two meetings)."""
        display = RecordingDisplay()
        repo = events.EventsRepository()
        repo.load_events([
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 8, 30, 0), "end": st(2026, 11, 11, 10, 30, 0)},
            {"start": st(2026, 11, 11, 8, 0, 0), "end": st(2026, 11, 11, 11, 0, 0)},
            {"start": st(2026, 11, 11, 9, 20, 0), "end": st(2026, 11, 11, 10, 20, 0)},
        ])
        layer = stack_mod.MeetingsLayer(repo,
                                        MeetingCountdown(repo, display, 10),
                                        MeetingTimeLeft(repo, display),
                                        cadence_s=5, max_columns=2)
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(frame_ascii(display.frames[0]),
                         "." * 6 + "r" * 6 + "." * 7 + "r" * 5)
        self.assertEqual(display.commits, 1)

    def test_meetings_gutter_leds_two(self):
        """gutter_leds=2: two concurrent 50% events use a 2-LED OFF gutter,
        layout [11, 11] (offsets 0 and 13), one frame, one commit."""
        display = RecordingDisplay()
        repo = events.EventsRepository()
        repo.load_events([
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 8, 30, 0), "end": st(2026, 11, 11, 10, 30, 0)},
        ])
        layer = stack_mod.MeetingsLayer(repo,
                                        MeetingCountdown(repo, display, 10),
                                        MeetingTimeLeft(repo, display),
                                        cadence_s=5, gutter_leds=2)
        with freeze_clock(NOW):
            self.assertTrue(layer.paint(NOW, display))
        self.assertEqual(len(display.frames), 1)
        self.assertEqual(frame_ascii(display.frames[0]),
                         "." * 6 + "r" * 5 + "." * 8 + "r" * 5)
        self.assertEqual(display.frames[0][11], OFF)
        self.assertEqual(display.frames[0][12], OFF)
        self.assertEqual(display.commits, 1)

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
