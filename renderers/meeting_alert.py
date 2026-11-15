"""Meeting-start alert renderer (roadmap F6).

Width-aware: frame(now) returns a self.width-LED yellow left-to-right sweep.
The fill fraction is elapsed alert time / duration_s, so at a 1 s cadence the
sweep advances one frame per cadence step (5 visible frames over a 5 s alert).
Pure (no hardware): the controller (meeting_alert_controller.MeetingAlert)
detects the start and the loop calls mark_started(); the renderer only derives
the animation from elapsed time. render(now) writes the full-width frame at
this renderer's width (v1 = 24) via the BaseRenderer delegation.
"""
from .base_renderer import BaseRenderer
import time


class MeetingAlertRenderer(BaseRenderer):
    def __init__(self, events, bargraph, alert, width=24):
        super().__init__(events, bargraph, width)
        self.alert = alert
        self.alert_started = None

    def mark_started(self, now):
        """Called by the loop when the controller reports a meeting start."""
        self.alert_started = now

    def frame(self, now):
        if self.alert_started is None:
            return None
        sec_elapsed = time.mktime(now) - time.mktime(self.alert_started)
        frac = max(0.0, min(1.0, sec_elapsed / self.alert.duration_s))
        return self.bargraph.progress(frac, "y", "left", width=self.width)
