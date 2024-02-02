from .base_renderer import BaseRenderer
import time

class MeetingCombined:
    def __init__(self, events, bargraph, countdown_min: 10):
        self.countdown_min = countdown_min
        super().__init__(events, bargraph)

    def render(self, now):
        until_frame = None
        time_left_frame = None

        next_frame = [""]*24

        next_event = self.events_repo.get_next_event()
        sec_until = time.mktime(next_event['start']) - time.mktime(now)
        if 0 < sec_until <= self.countdown_min * 60:
            pct = sec_until/(self.countdown_min*60)
            print("Meetings starting in {0} seconds, {1}% time left".format(sec_until, pct * 100))
            until_frame = self.bargraph.progress(pct, "g", "left")
            self.bargraph.set_frame(next_frame)
 
        current_event = self.events_repo.get_current_event()
        if current_event:
            sec_total = time.mktime(current_event['end']) - time.mktime(current_event['start'])
            sec_left = time.mktime(current_event['end']) - time.mktime(now)
            pct = sec_left/sec_total
            print("Meetings is {0}/{1} seconds complete, {2}% time left".format(sec_left, sec_total, pct * 100))
            time_left_frame = self.bargraph.progress(pct, "r", "right")

        
        self.bargraph.set_frame(next_frame)