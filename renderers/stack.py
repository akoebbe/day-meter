"""Layer stack model (foundation).

Topmost-wins display stack: the evaluator walks the stack top-to-bottom
and the first occupied layer paints (single commit). Stdlib only (no
board imports) so it runs under desktop CPython and stdlib-only tests.
"""

from display import frame_math


class Layer:
    """Base layer in the display stack.

    Subclasses implement occupied(now) and _draw(now, display).
    paint(now, display) is the ONLY commit point per layer: if occupied,
    _draw writes frame(s) (no commit) and paint commits once.
    """

    def __init__(self, cadence_s):
        self.cadence_s = cadence_s

    def occupied(self, now):
        raise NotImplementedError

    def paint(self, now, display):
        """Topmost-wins commit point.

        If occupied: _draw (writes frames, no commit), then display.commit().
        Returns True. Otherwise returns False (no write, no commit).
        """
        if self.occupied(now):
            self._draw(now, display)
            display.commit()
            return True
        return False

    def _draw(self, now, display):
        """Write frame(s) to display WITHOUT committing. Subclass hook."""
        raise NotImplementedError


class AlertLayer(Layer):
    """Top layer: the meeting-start alert sweep."""

    def __init__(self, alert, renderer, cadence_s):
        super().__init__(cadence_s)
        self.alert = alert
        self.renderer = renderer

    def occupied(self, now):
        return self.alert.is_active(now)

    def _draw(self, now, display):
        # renderer.render(now) = set_frame(frame(now)), no commit.
        self.renderer.render(now)


class MeetingsLayer(Layer):
    """Middle layer: countdown and time-left meeting renderers, composed
    into side-by-side columns (up to self.max_columns) for concurrent
    meetings.

    Occupied when any current event exists or the countdown has a frame.
    _draw composes the current meetings (earliest start -> leftmost) and the
    imminent countdown (green) into ONE full-width frame (frame_math.compose)
    with explicit OFF gutters (self.gutter_leds wide) between the columns.
    Reading A: earliest start is leftmost; the countdown takes the rightmost
    free column.
    """

    LED_COUNT = 24

    def __init__(self, events, countdown, time_left, cadence_s,
                 max_columns=3, gutter_leds=1):
        super().__init__(cadence_s)
        self.events = events
        self.countdown = countdown
        self.time_left = time_left
        self.max_columns = max_columns
        self.gutter_leds = gutter_leds

    def occupied(self, now):
        return (len(self.events.get_current_events(now=now)) > 0
                or self.countdown.frame(now) is not None)

    def _draw(self, now, display):
        """Compose the columns into ONE full-width frame (single set_frame)."""
        current = self.events.get_current_events(now=now)
        # Reading A order: current meetings by start ascending (earliest ->
        # leftmost), up to self.max_columns; the imminent countdown (green)
        # takes the rightmost free column if in window and a column is open.
        n_current = min(len(current), self.max_columns)
        has_countdown = (self.countdown.frame(now) is not None
                         and n_current < self.max_columns)
        n = n_current + (1 if has_countdown else 0)
        if n == 0:
            return
        layout = frame_math.column_layout(n, self.LED_COUNT, self.gutter_leds)
        regions = []
        col_index = 0
        for i in range(n_current):
            offset, width = layout[col_index]
            regions = self._append_column(regions, col_index, offset,
                                          self.time_left.frame_for_event(current[i], now, width))
            col_index += 1
        if has_countdown:
            offset, width = layout[col_index]
            regions = self._append_column(regions, col_index, offset,
                                          self.countdown.frame_at(now, width))
        display.set_frame(frame_math.compose(regions, self.LED_COUNT))

    def _append_column(self, regions, index, offset, frame):
        """Append a column frame plus its leading OFF gutter (when not first)."""
        if index > 0:
            regions = (regions
                        + [(offset - self.gutter_leds,
                            [0] * self.gutter_leds)])
        return regions + [(offset, frame)]


class BaseLayer(Layer):
    """Bottom layer: the always-occupied floor.

    Holds a list of base renderers (v1: [half_day_renderer]).
    cycle_base_view() advances the index (mechanism only; button hookup = F3).
    Uses render (not frame) — the half-day view overrides render() and
    has no frame().
    """

    def __init__(self, renderers, cadence_s):
        super().__init__(cadence_s)
        self.renderers = renderers
        self.current = 0

    def occupied(self, now):
        return True  # always the floor

    def _draw(self, now, display):
        # render() writes the frame without committing (no commit here).
        self.renderers[self.current].render(now)

    def cycle_base_view(self):
        """Advance to the next base view. Mechanism only (F3 wires this)."""
        self.current = (self.current + 1) % len(self.renderers)
