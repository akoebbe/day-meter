from .base_renderer import BaseRenderer
import time


            
class MeetingTimeLeft(BaseRenderer):
    def render(self, now):
        current_event = self.events_repo.get_current_event()
        if current_event:
            sec_total = time.mktime(current_event['end']) - time.mktime(current_event['start'])
            sec_left = time.mktime(current_event['end']) - time.mktime(now)
            pct = sec_left/sec_total
            print("Meetings is {0}/{1} seconds complete, {2}% time left".format(sec_left, sec_total, pct * 100))
            next_frame = self.bargraph.progress(pct, "r", "right")
            self.bargraph.set_frame(next_frame)
