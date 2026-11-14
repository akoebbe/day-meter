"""Renderer-facing Display contract (roadmap F1 seam).

Stdlib only -- no hardware imports. A concrete adapter implements
set_frame(frame) + commit() and declares LED_COUNT + PALETTE; the base
class provides set_frame_from_text() and progress() in terms of those.
These are exactly the methods renderers consume (see tests/fakes.py
FrameRecorder), which the 49-test suite pins.
"""
from . import frame_math


class Display:
    LED_COUNT = 24
    PALETTE = None  # char -> color int; adapters set in __init__ or as class attr

    def set_frame(self, frame):
        raise NotImplementedError

    def commit(self):
        raise NotImplementedError

    def set_frame_from_text(self, text):
        """Map chars via PALETTE and write the frame (no commit)."""
        self.set_frame(frame_math.frame_from_text(text, self.PALETTE))

    def progress(self, pct=.5, color="g", justified="left", commit=False):
        """Compute and return a progress frame (no commit unless commit=True)."""
        frame = frame_math.progress_frame(
            self.LED_COUNT, pct, color, self.PALETTE, justified)
        if commit:
            self.set_frame(frame)
            self.commit()
        return frame
