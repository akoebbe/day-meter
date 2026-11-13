"""Hermetic desktop golden-frame + index-math tests for ZoomDayRenderer -- Phase 6,
day-meter-dev-test-suite plan.

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

Unlike Phases 4-5 this renderer reads NO wall clock in its render path: start/end come
from the explicit now argument (start_of_hour(now, 0) / end_of_hour(now, 23)), and
get_events_starting_between is called with struct arguments, so no time.localtime() read
happens and there are no mktime deltas -- freeze_clock is therefore not needed (same
reasoning as Phase 3), and behavior is TZ-independent by construction (struct field-wise
comparisons only).

Semantics pinned from source (renderers/zoom_day_renderer.py:19-55): one green LED per
event start at _time_to_led; marker "y" if its own LED empty else "r" (marker wins, written
last); visible window is exactly 24 LEDs -- starts at max(now_led - 3, 0) and is clamped to
len(frame) - 24 when too little remains; set_frame_from_text receives that 24-char window,
so the fake records exactly one frame per render. _led_count() == int(60*24/zoom_map[z]) =
{z0:24, z1:48, z2:96, z3:144} for zoom_map {0:60, 1:30, 2:15, 3:10}. Default constructor zoom is 1.

Expected frames below are built by arithmetic (index -> char dict joined over 24 slots),
never hand-counted ASCII. All NOWs use date 2026-11-11.
"""

import time
import unittest

import events
from fakes import FrameRecorder, frame_ascii
from renderers.zoom_day_renderer import ZoomDayRenderer


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like iso_to_time_struct's output."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


DAY = (2026, 11, 11)


def ascii_of(spec):
    """Build the 24-char expected window from {led_index_in_window: char}."""
    f = ["."] * 24
    for idx, ch in spec.items():
        f[idx] = ch
    return "".join(f)


def _render(event_spans=(), zoom=1, now=None):
    repo = events.EventsRepository()
    repo.load_events([{"start": st(*DAY + a), "end": st(*DAY + b)}
                      for (a, b) in event_spans])
    recorder = FrameRecorder()
    renderer = ZoomDayRenderer(repo, recorder, zoom)
    renderer.render(now if now is not None else st(*DAY, 9, 35, 0))
    return renderer, recorder


class ZoomDayRendererTests(unittest.TestCase):
    def test_zoom_level_frame_lengths_and_led_index(self):
        # Whitebox pins of the per-zoom frame length and LED index math.
        _, rec = _render()
        r = ZoomDayRenderer(events.EventsRepository(), rec)
        for z, count in ((0, 24), (1, 48), (2, 96), (3, 144)):
            r.zoom_level = z
            self.assertEqual(r._led_count(), count)
        t = st(*DAY, 9, 35, 0)
        for z, led in ((0, 9), (1, 19), (2, 38), (3, 57)):
            r.zoom_level = z
            self.assertEqual(r._time_to_led(t), led)

    def test_default_zoom_is_one(self):
        # main.py constructs ZoomDayRenderer without a zoom arg -> level 1.
        _, rec = _render()
        r = ZoomDayRenderer(events.EventsRepository(), rec)
        self.assertEqual(r.zoom_level, 1)

    def test_increment_zoom_cycles_and_wraps(self):
        # (zoom + 1) % len(zoom_map), map has four entries.
        _, rec = _render()
        r = ZoomDayRenderer(events.EventsRepository(), rec)  # default zoom 1
        levels = [r.zoom_level]
        for _ in range(4):
            r.increment_zoom()
            levels.append(r.zoom_level)
        self.assertEqual(levels, [1, 2, 3, 0, 1])

    def test_z1_empty_day_marker_at_offset_three(self):
        # z1: now_led = 9*2 + floor(35/30) = 19; start_led = max(16,0); 48-16 >= 24
        # -> window [16..40), marker at offset 3.
        _, rec = _render(zoom=1)
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), ascii_of({3: "y"}))

    def test_z0_full_day_frame_events_and_red_over_green(self):
        # z0 frame IS the whole day (24 LEDs); window clamp lands at 0. Greens from events
        # at 07:30/13:00/20:05; marker (now 13:45) sits on the 13:00 start LED -> red wins.
        _, rec = _render(event_spans=[((7, 30, 0), (8, 0, 0)), ((13, 0, 0), (14, 0, 0)),
                                      ((20, 5, 0), (21, 0, 0))],
                         zoom=0, now=st(*DAY, 13, 45, 0))
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), ascii_of({7: "g", 13: "r", 20: "g"}))

    def test_z2_window_offset_and_inwindow_event(self):
        # z2, now 15:07: now_led = 60; start_led = 57 -> window [57..81); event at 16:00
        # (led 64) shows at offset 7; an event at 23:59 (led 95) is outside the window.
        _, rec = _render(event_spans=[((16, 0, 0), (17, 0, 0)), ((23, 59, 0), (23, 59, 59))],
                         zoom=2, now=st(*DAY, 15, 7, 0))
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), ascii_of({3: "y", 7: "g"}))

    def test_z3_end_of_day_clamp_window_and_red_pin(self):
        # z3, now 23:55: now_led = 143; naive start would be 140 but only 4 LEDs remain ->
        # clamped to len-24 = 120 (the clamp branch). Event at 23:59 (led 143) lands on the
        # marker LED -> red over green, last slot of the window.
        _, rec = _render(event_spans=[((23, 59, 0), (23, 59, 59))],
                         zoom=3, now=st(*DAY, 23, 55, 0))
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), ascii_of({23: "r"}))

    def test_z1_early_day_max_branch_marker_at_led_zero(self):
        # z1, now 00:15: now_led = floor(15/30) = 0; max(-3, 0) = 0 -> window [0..24),
        # marker at offset 0 (the max() clamp branch).
        _, rec = _render(zoom=1, now=st(*DAY, 0, 15, 0))
        self.assertEqual(len(rec.frames), 1)
        self.assertEqual(frame_ascii(rec.last_frame), ascii_of({0: "y"}))


if __name__ == "__main__":
    unittest.main()
