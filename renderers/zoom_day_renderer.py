from .base_renderer import BaseRenderer
from events import EventsRepository, start_of_hour, end_of_hour
from math import floor
from time import struct_time


class ZoomDayRenderer(BaseRenderer):
    zoom_map = {
        0: 60,
        1: 30,
        2: 15,
        3: 10,
    }

    def __init__(self, events: EventsRepository, bargraph, zoom: int = 1):
        self.zoom_level = zoom
        super().__init__(events, bargraph)

    def render(self, now:struct_time):
        start = start_of_hour(now, 0)
        end = end_of_hour(now, 23)
        
        events = self.events_repo.get_events_starting_between(start, end)

        next_frame = [""]*self._led_count()
        
        for event in events:
            led_idx = self._time_to_led(event['start'])
            next_frame[led_idx] = "g"
        
        now_led = self._time_to_led(now)

        if (now < end and now >= start):
            next_frame[now_led] = "y" if next_frame[now_led] == "" else "r"

        start_led = max(now_led - 3, 0)
        if len(next_frame) - start_led < 24:
            start_led = len(next_frame) - 24

        #print(next_frame)
        #print("Start LED: {}".format(start_led))

        window = next_frame[start_led:start_led + 24]
        #print(window)

        self.bargraph.set_frame_from_text(window)
    
    def increment_zoom(self):
        self.zoom_level = (self.zoom_level + 1) % len(self.zoom_map)

    def _time_to_led(self, time):
        return ((time[3]) * int(60/self.zoom_map[self.zoom_level])) + (floor(time[4]/self.zoom_map[self.zoom_level]))
    
    def _led_count(self):
        return int(60 * 24 / self.zoom_map[self.zoom_level])