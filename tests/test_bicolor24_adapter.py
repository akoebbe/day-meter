"""Hardware-adapter logic tests (display/bicolor24.py). Stdlib only.

The Bicolor24 driver + board.STEMMA_I2C() exist only on the device, so these
tests run the adapter's pure logic against a FakeBicolor24Driver with
board/ht16k33 stubbed in sys.modules. Covers: palette mapping to driver
constants, frame writes (incl. reverse flag), commit (show + ASCII), and
progress with commit. The diff-write optimization is pinned at the
frame_math.diff level in test_frame_math.py (the adapter's set_frame is a thin
wrapper over frame_math.diff + __setitem__).
"""
import unittest

from fakes import hardware_stub


def _make_adapter(reverse=False):
    """Build a Bicolor24Adapter against the fake driver, inside the stub."""
    with hardware_stub():
        from display.bicolor24 import Bicolor24Adapter
        return Bicolor24Adapter(reverse=reverse)


class PaletteTest(unittest.TestCase):
    def test_palette_maps_to_driver_constants(self):
        adapter = _make_adapter()
        d = adapter._driver
        self.assertEqual(adapter.PALETTE['g'], d.LED_GREEN)
        self.assertEqual(adapter.PALETTE['r'], d.LED_RED)
        self.assertEqual(adapter.PALETTE['y'], d.LED_YELLOW)
        self.assertEqual(adapter.PALETTE[''], d.LED_OFF)


class SetFrameTest(unittest.TestCase):
    def test_writes_all_24_on_first_frame(self):
        adapter = _make_adapter()
        d = adapter._driver
        adapter.set_frame([1] * 24)
        # After one full write, every slot is green in the reconstruction.
        self.assertEqual(d.frame(), [1] * 24)

    def test_rejects_wrong_length(self):
        adapter = _make_adapter()
        with self.assertRaises(ValueError):
            adapter.set_frame([0] * 23)

    def test_reverse_flips_frame_before_write(self):
        adapter = _make_adapter(reverse=True)
        d = adapter._driver
        # A green fill on the left (slots 0..3), reversed, lands in slots 20..23.
        adapter.set_frame([1, 1, 1, 1] + [0] * 20)
        self.assertEqual(d.frame()[20], 1)
        self.assertEqual(d.frame()[23], 1)
        self.assertEqual(d.frame()[0], 0)


class CommitTest(unittest.TestCase):
    def test_commit_shows_driver(self):
        adapter = _make_adapter()
        d = adapter._driver
        adapter.set_frame([1] * 24)
        shown_before = d.shows
        adapter.commit()
        self.assertEqual(d.shows, shown_before + 1)

    def test_commit_ascii_matches_current_frame(self):
        adapter = _make_adapter()
        d = adapter._driver
        frame = [0] * 24
        frame[0] = 1
        frame[1] = 2
        adapter.set_frame(frame)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            adapter.commit()
        # commit prints str(i) if i>0 else '.'; only slot 0 and 1 are non-zero.
        self.assertEqual(buf.getvalue().splitlines()[0], "12......................")


class ProgressTest(unittest.TestCase):
    def test_progress_commit_writes_and_commits(self):
        adapter = _make_adapter()
        d = adapter._driver
        adapter.progress(0.5, commit=True)
        self.assertEqual(d.frame(), [1] * 12 + [0] * 12)
        self.assertEqual(d.shows, 1)

    def test_progress_no_commit_does_not_write(self):
        adapter = _make_adapter()
        d = adapter._driver
        frame = adapter.progress(0.5)
        self.assertEqual(frame, [1] * 12 + [0] * 12)
        self.assertEqual(d.shows, 0)             # no commit
        # No writes to the driver either (progress returns the frame; renderer
        # calls set_frame itself when it wants to commit).
        self.assertEqual(d.frame(), [0] * 24)


if __name__ == "__main__":
    unittest.main()
