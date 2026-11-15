"""Meeting-start alert controller (roadmap F6).

Detects events that begin between consecutive ticks and owns the alert's
lifetime. Pure (stdlib + posix_tz) -- no hardware. The alert renderer
(renderers/meeting_alert.py) and the main loop's alert_runner consume this.

Detection model: each tick queries the half-open window [prev_now, now) via
EventsRepository.get_events_starting_between(..., log=False). Because
consecutive tick windows tile the timeline, a start is counted exactly once
(no double-count) and no start is missed. The first tick only records the
baseline, so a meeting already running at boot never alerts.
"""
from posix_tz import add_seconds


class MeetingAlert:
    def __init__(self, duration_s=5, cadence_s=1):
        self.duration_s = duration_s
        self.cadence_s = cadence_s
        self._last_now = None
        self._active_until = None
        self._alert_events = None

    def on_tick(self, events_repo, now):
        """Advance detection by one tick. Returns the list of events that
        started in [prev_now, now) -- empty when none (or on the first tick).
        """
        started = []
        if self._last_now is not None:
            started = events_repo.get_events_starting_between(
                self._last_now, now, log=False)
        self._last_now = now
        if started:
            self._active_until = add_seconds(now, self.duration_s)
            self._alert_events = started
        return started

    def is_active(self, now):
        return self._active_until is not None and now < self._active_until

    @property
    def alert_events(self):
        return self._alert_events

    def reset(self):
        self._last_now = None
        self._active_until = None
        self._alert_events = None
