"""Pure frame-math tests (display/frame_math.py). Stdlib only."""
import unittest

from display import frame_math

PALETTE = {"g": 1, "r": 2, "y": 3, "": 0}


class FrameFromTextTest(unittest.TestCase):
    def test_maps_palette_chars(self):
        self.assertEqual(frame_math.frame_from_text("gygr", PALETTE), [1, 3, 1, 2])

    def test_unknown_char_raises_key_error(self):
        with self.assertRaises(KeyError):
            frame_math.frame_from_text("gxr", PALETTE)

    def test_preserves_length(self):
        self.assertEqual(len(frame_math.frame_from_text("gy" * 12, PALETTE)), 24)


class ProgressFrameTest(unittest.TestCase):
    def test_zero_pct_is_all_off(self):
        self.assertEqual(frame_math.progress_frame(24, 0.0, "g", PALETTE), [0] * 24)

    def test_half_pct_left(self):
        self.assertEqual(frame_math.progress_frame(24, 0.5, "g", PALETTE), [1] * 12 + [0] * 12)

    def test_full_pct(self):
        self.assertEqual(frame_math.progress_frame(24, 1.0, "g", PALETTE), [1] * 24)

    def test_right_justified(self):
        self.assertEqual(frame_math.progress_frame(
            24, 0.5, "g", PALETTE, justified="right"), [0] * 12 + [1] * 12)

    def test_color_char_respected(self):
        self.assertEqual(frame_math.progress_frame(24, 0.5, "r", PALETTE), [2] * 12 + [0] * 12)

    def test_parametrized_led_count(self):
        self.assertEqual(frame_math.progress_frame(10, 0.5, "g", PALETTE), [1] * 5 + [0] * 5)


class DiffTest(unittest.TestCase):
    def test_equal_frames_no_changes(self):
        self.assertEqual(frame_math.diff([1] * 24, [1] * 24), [])

    def test_changed_indices(self):
        frame = [0] * 24
        frame[3] = 1
        self.assertEqual(frame_math.diff([0] * 24, frame), [3])

    def test_length_mismatch_raises(self):
        with self.assertRaises(ValueError):
            frame_math.diff([0] * 24, [0] * 23)

class ComposeTest(unittest.TestCase):
    def test_tiles_24_as_8_plus_16(self):
        a = frame_math.progress_frame(8, 1.0, "g", PALETTE)
        b = frame_math.progress_frame(16, 0.5, "r", PALETTE)
        frame = frame_math.compose([(0, a), (8, b)])
        self.assertEqual(frame, [1] * 8 + [2] * 8 + [0] * 8)

    def test_tiles_24_as_12_plus_12(self):
        a = frame_math.progress_frame(12, 1.0, "g", PALETTE)
        b = frame_math.progress_frame(12, 0.0, "y", PALETTE)
        frame = frame_math.compose([(0, a), (12, b)])
        self.assertEqual(frame, [1] * 12 + [0] * 12)

    def test_full_width_single_region(self):
        a = frame_math.progress_frame(24, 0.5, "g", PALETTE)
        frame = frame_math.compose([(0, a)])
        self.assertEqual(frame, [1] * 12 + [0] * 12)

    def test_three_equal_columns(self):
        a = frame_math.progress_frame(8, 1.0, "g", PALETTE)
        b = frame_math.progress_frame(8, 1.0, "r", PALETTE)
        c = frame_math.progress_frame(8, 1.0, "y", PALETTE)
        frame = frame_math.compose([(0, a), (8, b), (16, c)])
        self.assertEqual(frame, [1] * 8 + [2] * 8 + [3] * 8)

    def test_gap_raises(self):
        a = frame_math.progress_frame(8, 1.0, "g", PALETTE)
        b = frame_math.progress_frame(15, 0.5, "r", PALETTE)
        with self.assertRaises(ValueError):
            frame_math.compose([(0, a), (8, b)])

    def test_overlap_raises(self):
        a = frame_math.progress_frame(8, 1.0, "g", PALETTE)
        b = frame_math.progress_frame(16, 0.5, "r", PALETTE)
        with self.assertRaises(ValueError):
            frame_math.compose([(0, a), (7, b)])

    def test_region_extends_beyond_led_count_raises(self):
        b = frame_math.progress_frame(16, 0.5, "r", PALETTE)
        with self.assertRaises(ValueError):
            frame_math.compose([(0, b)], led_count=8)

    def test_custom_led_count(self):
        a = frame_math.progress_frame(6, 1.0, "g", PALETTE)
        b = frame_math.progress_frame(6, 1.0, "r", PALETTE)
        frame = frame_math.compose([(0, a), (6, b)], led_count=12)
        self.assertEqual(len(frame), 12)
        self.assertEqual(frame, [1] * 6 + [2] * 6)
