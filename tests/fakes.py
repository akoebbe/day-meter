"""Desktop test doubles for the Day Meter renderer/event suite.

Stdlib only -- nothing in this file imports board, wifi, microcontroller,
adafruit_*, numpy/ulab or any product module. FrameRecorder is a duck-type of
the three bargraph module-level functions renderers actually call:
set_frame, set_frame_from_text, progress (see base_renderer.py for the stored
reference and bargraph.py for the real module).

Color values mirror Adafruit Bicolor24 constants as used by the color_map at
bargraph.py:17:
    LED_OFF=0  LED_GREEN=1  LED_RED=2  LED_YELLOW=3
Verify against the bundled driver once on-device; if it ever shows a mismatch,
document it here first.
"""

import time
from math import floor

OFF = 0
GREEN = 1
RED = 2
YELLOW = 3

# Test-local copy of bargraph.py:17 (same keys, same values).
COLOR_MAP = {"g": GREEN, "r": RED, "y": YELLOW, "": OFF}
_INT_TO_ASCII = {OFF: ".", GREEN: "g", RED: "r", YELLOW: "y"}


class FrameRecorder(object):
    """Stand-in for the bargraph module injected into BaseRenderer.

    No commit/diff semantics -- those are hardware behaviour of
    bargraph.set_frame/commit_frame and out of scope for golden tests (the seam
    refactor that covers them pairs with roadmap F1).
    """

    def __init__(self):
        self.frames = []          # every frame written by set_frame, in order
        self.last_frame = None    # tuple of 24 color ints; None until first write

    def set_frame(self, frame):
        stored = tuple(int(c) for c in frame)
        if len(stored) != 24:
            raise RuntimeError(
                "frame must be exactly 24 LEDs, got {0}".format(len(stored)))
        self.frames.append(stored)
        self.last_frame = stored

    def set_frame_from_text(self, text):
        # Mirror of bargraph.py:23-29: map chars via color_map, delegate to set_frame.
        mapped = [COLOR_MAP[c] for c in text]
        self.set_frame(mapped)

    def progress(self, pct=.5, color="g", justified="left", width=None):
        # Mirror of bargraph.progress fill math (bargraph.py:36-48); no commit arg.
        led_count = width if width is not None else 24
        filled = floor(led_count * pct)
        frame = [OFF] * led_count
        frame[:filled] = [COLOR_MAP[color]] * filled
        if justified == "right":
            frame = frame[::-1]     # bargraph flips the whole frame (np.flip)
        return frame


def frame_ascii(frame):
    """Render a stored frame as 24 chars of g/r/y/. for human-readable failures."""
    return "".join(_INT_TO_ASCII[int(c)] for c in frame)


class freeze_clock(object):
    """Hermetic wall clock.

    Patches BOTH time.localtime and time.mktime: EventsRepository reads the
    clock inside get_current_event/get_next_event even when renderers are handed
    a fixed `now`, and MeetingCountdown/MeetingTimeLeft compute pct from mktime
    deltas. The fake mktime is a linear mapping of struct fields -- deterministic
    on any machine/timezone, no DST dependence:
        seconds = (tm_mday*24 + tm_hour)*3600 + tm_min*60 + ts[5]
    """

    def __init__(self, now_struct):
        self.now = now_struct

    def _localtime(self, *args, **kwargs):
        return self.now

    @staticmethod
    def _mktime(ts):
        return (ts[2] * 24 + ts[3]) * 3600 + ts[4] * 60 + ts[5]

    def __enter__(self):
        self._orig_localtime = time.localtime
        self._orig_mktime = time.mktime
        time.localtime = self._localtime
        time.mktime = self._mktime
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        time.localtime = self._orig_localtime
        time.mktime = self._orig_mktime
        return False


def mktime_delta(start_struct, end_struct):
    """Exact deterministic seconds delta under freeze_clock (for expected-pct math)."""
    return freeze_clock._mktime(end_struct) - freeze_clock._mktime(start_struct)

# ---------------------------------------------------------------------------
# Hardware-adapter test doubles (display/bicolor24.py).
#
# The real Bicolor24 driver + board.STEMMA_I2C() exist only on the device, so
# hardware_stub injects desktop stand-ins into sys.modules to let the adapter
# import and run its pure logic (diff-write / commit / palette) with no I2C.
# FakeBicolor24Driver's constants mirror the bundled driver
# (LED_OFF=0, LED_GREEN=1, LED_RED=2, LED_YELLOW=3).
# ---------------------------------------------------------------------------


class FakeBicolor24Driver(object):
    """Desktop stand-in for adafruit_ht16k33.bargraph.Bicolor24.

    The adapter (display/bicolor24.py) uses only: the LED_* color constants,
    per-LED __setitem__, and show(). Records every write so tests can
    reconstruct the frame and count commits without real I2C.
    """
    LED_OFF = 0
    LED_GREEN = 1
    LED_RED = 2
    LED_YELLOW = 3

    def __init__(self, i2c=None, auto_write=False):
        self._written = {}   # index -> last color int the adapter set
        self.shows = 0

    def __setitem__(self, index, value):
        self._written[index] = value

    def show(self):
        self.shows += 1

    def frame(self, led_count=24):
        """Reconstruct the full 24-slot frame from recorded writes."""
        return [self._written.get(i, 0) for i in range(led_count)]

class hardware_stub(object):
    """Patches sys.modules so display/bicolor24.py imports on desktop.

    Injects a fake `board` (with STEMMA_I2C()) and a fake
    adafruit_ht16k33.bargraph.Bicolor24 (= FakeBicolor24Driver). Restores
    sys.modules on exit. Enter *before* importing display.bicolor24.
    """

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        import sys
        import types
        self._saved = {
            name: sys.modules.get(name)
            for name in (
                "board", "adafruit_ht16k33", "adafruit_ht16k33.bargraph",
                "display.bicolor24",
            )
        }
        board = types.ModuleType("board")
        board.STEMMA_I2C = lambda: object()
        pkg = types.ModuleType("adafruit_ht16k33")
        bargraph = types.ModuleType("adafruit_ht16k33.bargraph")
        bargraph.Bicolor24 = FakeBicolor24Driver
        pkg.bargraph = bargraph
        sys.modules["board"] = board
        sys.modules["adafruit_ht16k33"] = pkg
        sys.modules["adafruit_ht16k33.bargraph"] = bargraph
        sys.modules.pop("display.bicolor24", None)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        import sys
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        return False
