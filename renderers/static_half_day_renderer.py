from .base_renderer import BaseRenderer
from events import start_of_hour, end_of_hour
from math import floor

class StaticHalfDayRenderer(BaseRenderer):
    def __init__(self, events, bargraph, start_hour: 8):
        self.start_hour = start_hour
        super().__init__(events, bargraph)


    def render(self, now):
        start = start_of_hour(now, self.start_hour)
        end = end_of_hour(now, self.start_hour + 11)
        
        events = self.events_repo.get_events_starting_between(start, end)
        
        next_frame = [""]*24
        
        for event in events:
            led_idx = self._time_to_led(event['start'])
            next_frame[led_idx] = "g"
        
        if (now < end and now >= start):
            next_frame[self._time_to_led(now)] = "y" if next_frame[self._time_to_led(now)] == "" else "r"
        
        self.bargraph.set_frame_from_text(next_frame)
            
        
    def _time_to_led(self, time):
        return ((time[3] - self.start_hour) * 2) + (floor(time[4]/30))