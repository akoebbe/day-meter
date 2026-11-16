"""Layer stack model (foundation).

Topmost-wins display stack: the evaluator walks the stack top-to-bottom
and the first occupied layer paints (single commit). Stdlib only (no
board imports) so it runs under desktop CPython and stdlib-only tests.
"""


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
    """Middle layer: countdown and time-left meeting renderers.

    Occupied when EITHER meeting renderer has a frame. Draw order is
    countdown then time-left so that when both are active the time-left
    frame is last written (today's effective last-writer behavior).
    """

    def __init__(self, events, countdown, time_left, cadence_s):
        super().__init__(cadence_s)
        self.events = events
        self.countdown = countdown
        self.time_left = time_left

    def occupied(self, now):
        return (self.countdown.frame(now) is not None
                or self.time_left.frame(now) is not None)

    def _draw(self, now, display):
        # Each render = set_frame(frame(now)), no commit.
        # Countdown first, time-left second (time-left wins when both active).
        self.countdown.render(now)
        self.time_left.render(now)


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
