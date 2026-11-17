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

def column_layout(n, led_count=24, gutter=1):
    """(offset, width) pairs splitting led_count LEDs into n columns.

    n-1 gutter LEDs of width `gutter` separate the columns (gutters are OFF
    and belong to no column); extra LEDs beyond the even split go to the
    leftmost column. n = 1 yields a single full-width column.

    n=24/2:  [(0, 12), (13, 11)]
    n=24/3:  [(0, 8), (9, 7), (17, 7)]
    """
    if n < 1:
        raise ValueError("column count must be >= 1, got {0}".format(n))
    if gutter < 0:
        raise ValueError("gutter width must be >= 0, got {0}".format(gutter))
    if (n - 1) * gutter >= led_count:
        raise ValueError("gutters of {0} LED do not fit {1} columns in {2} LEDs".format(
            gutter, n, led_count))
    content = led_count - (n - 1) * gutter
    base = content // n
    extra = content % n
    columns = []
    offset = 0
    for i in range(n):
        width = base + (extra if i == 0 else 0)
        columns.append((offset, width))
        offset += width + gutter
    return columns


def compose(regions, led_count=24):
    """Place sub-width frames at offsets into one full-width frame.

    regions: list of (offset, frame) pairs; frame is a list of color ints
    placed starting at that LED offset. The regions must exactly tile
    led_count (contiguous, no overlaps, no gaps) or ValueError is raised
    (like diff()). Returns the composed led_count-LED frame.

    Example: compose([(0, [8-LED frame]), (8, [16-LED frame])]) -> 24-LED frame.
    """
    frame = [0] * led_count
    covered = [False] * led_count
    for offset, region in regions:
        if offset < 0 or offset + len(region) > led_count:
            raise ValueError(
                "region at offset {0} length {1} does not fit led_count {2}".format(
                    offset, len(region), led_count))
        for i, color in enumerate(region):
            idx = offset + i
            if covered[idx]:
                raise ValueError("regions overlap at LED index {0}".format(idx))
            frame[idx] = color
            covered[idx] = True
    if not all(covered):
        raise ValueError("regions do not exactly tile led_count {0}".format(led_count))
    return frame