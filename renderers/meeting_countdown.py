from .base_renderer import BaseRenderer
from posix_tz import local_delta

class MeetingCountdown(BaseRenderer):
    def __init__(self, events, bargraph, countdown_min: 10, width: int = 24):
        self.countdown_min = countdown_min
        super().__init__(events, bargraph, width)

    def frame(self, now):
        return self.frame_at(now, self.width)

    def frame_at(self, now, width):
        """Self-width frame for the imminent next event, or None.

        width = the LED count the caller wants (column width in the
        MeetingsLayer compose; self.width for the standalone path).
        """
        next_event = self.events_repo.get_next_event(now=now)
        if next_event:
            sec_until = local_delta(now, next_event['start'], self.events_repo.tz)
            if 0 < sec_until <= self.countdown_min * 60:
                pct = sec_until/(self.countdown_min*60)
                #print("Meetings starting in {0} seconds, {1}% time left".format(sec_until, pct * 100))
                return self.bargraph.progress(pct, width=width)
        return None