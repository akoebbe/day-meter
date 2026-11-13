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

    def progress(self, pct=.5, color="g", justified="left"):
        # Mirror of bargraph.progress fill math (bargraph.py:36-48); no commit arg.
        led_count = floor(24 * pct)
        frame = [OFF] * 24
        frame[:led_count] = [COLOR_MAP[color]] * led_count
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
