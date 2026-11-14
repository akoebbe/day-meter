"""Display base-contract tests (display/base.py). Stdlib only.

MemoryDisplay is a concrete Display proving the renderer-facing contract
(set_frame / set_frame_from_text / progress + commit) works on the base
class with no hardware -- the same interface FrameRecorder mirrors.
"""
import unittest

from display.base import Display

PALETTE = {"g": 1, "r": 2, "y": 3, "": 0}


class MemoryDisplay(Display):
    LED_COUNT = 24
    PALETTE = PALETTE

    def __init__(self):
        self.current = [0] * 24
        self.commits = 0

    def set_frame(self, frame):
        if len(frame) != self.LED_COUNT:
            raise ValueError("frame must be exactly {0} LEDs, got {1}".format(
                self.LED_COUNT, len(frame)))
        self.current = list(frame)

    def commit(self):
        self.commits += 1


class DisplayBaseTest(unittest.TestCase):
    def setUp(self):
        self.display = MemoryDisplay()

    def test_progress_returns_frame_without_committing(self):
        frame = self.display.progress(0.5)
        self.assertEqual(frame, [1] * 12 + [0] * 12)
        self.assertEqual(self.display.commits, 0)

    def test_progress_commit_writes_and_commits(self):
        self.display.progress(1, commit=True)
        self.assertEqual(self.display.current, [1] * 24)
        self.assertEqual(self.display.commits, 1)

    def test_set_frame_from_text_maps_and_writes_without_commit(self):
        d = MemoryDisplay()
        d.PALETTE = dict(PALETTE, o=0)
        d.set_frame_from_text("gy" + "o" * 22)
        self.assertEqual(d.current, [1, 3] + [0] * 22)
        self.assertEqual(d.commits, 0)

    def test_set_frame_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            self.display.set_frame([0] * 23)
