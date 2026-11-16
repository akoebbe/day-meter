from .base_renderer import BaseRenderer
import time


            
class MeetingTimeLeft(BaseRenderer):
    def frame(self, now):
        current_event = self.events_repo.get_current_event()
        if current_event:
            sec_total = time.mktime(current_event['end']) - time.mktime(current_event['start'])
            sec_left = time.mktime(current_event['end']) - time.mktime(now)
            pct = sec_left/sec_total
            print("Meeting elapsed {0}/{1} s, {2:.1f}% left".format(sec_total - sec_left, sec_total, pct * 100))
            return self.bargraph.progress(pct, "r", "right", width=self.width)
        return None
