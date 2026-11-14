"""Pure frame math for display adapters.

Stdlib only (no numpy/ulab, no board imports) so it runs under desktop
CPython and CPython-stdlib tests. Frames are plain lists of color ints.
"""
from math import floor


def frame_from_text(text, palette):
    """Map each char via palette ({'g': int, 'r': int, 'y': int, '': int})."""
    return [palette[c] for c in text]


def progress_frame(led_count, pct, color, palette, justified="left"):
    """floor(led_count * pct) LEDs of palette[color], rest palette[''].

    Left-justified by default; justified="right" flips the whole frame
    (mirror of the old np.flip behavior: color occupies the LAST slots).
    """
    filled = floor(led_count * pct)
    frame = [palette[""]] * led_count
    frame[:filled] = [palette[color]] * filled
    if justified == "right":
        frame = frame[::-1]
    return frame


def diff(current, next_frame):
    """Indices where current and next_frame differ; [] if identical.

    Raises ValueError on length mismatch.
    """
    if len(current) != len(next_frame):
        raise ValueError("frame length mismatch: {0} vs {1}".format(
            len(current), len(next_frame)))
    return [i for i in range(len(next_frame)) if current[i] != next_frame[i]]
