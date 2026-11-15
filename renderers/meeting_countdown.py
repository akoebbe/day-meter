from .base_renderer import BaseRenderer
import time

class MeetingCountdown(BaseRenderer):
    def __init__(self, events, bargraph, countdown_min: 10, width: int = 24):
        self.countdown_min = countdown_min
        super().__init__(events, bargraph, width)

    def frame(self, now):
        next_event = self.events_repo.get_next_event()
        if next_event:
            sec_until = time.mktime(next_event['start']) - time.mktime(now)
            if 0 < sec_until <= self.countdown_min * 60:
                pct = sec_until/(self.countdown_min*60)
                #print("Meetings starting in {0} seconds, {1}% time left".format(sec_until, pct * 100))
                return self.bargraph.progress(pct, width=self.width)
        return None