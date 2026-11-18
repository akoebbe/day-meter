from .base_renderer import BaseRenderer
from posix_tz import local_delta


            
class MeetingTimeLeft(BaseRenderer):
    def frame(self, now):
        return self.frame_at(now, self.width)

    def frame_at(self, now, width):
        """Self-width frame for the first current event, or None.

        width = the LED count the caller wants (column width in the
        MeetingsLayer compose; self.width for the standalone path).
        """
        current_events = self.events_repo.get_current_events(now=now)
        return self.frame_for_event(current_events[0] if current_events else None, now, width)

    def frame_for_event(self, current_event, now, width):
        if current_event:
            sec_total = local_delta(current_event['start'], current_event['end'], self.events_repo.tz)
            sec_left = local_delta(now, current_event['end'], self.events_repo.tz)
            pct = sec_left/sec_total
            print("Meeting elapsed {0}/{1} s, {2:.1f}% left".format(sec_total - sec_left, sec_total, pct * 100))
            return self.bargraph.progress(pct, "r", "right", width=width)
        return None
