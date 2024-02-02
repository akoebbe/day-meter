from .base_renderer import BaseRenderer
from events import start_of_hour, end_of_hour


class StaticDayRenderer(BaseRenderer):
    def render(self, now):
        start = start_of_hour(now, 0)
        end = end_of_hour(now, 23)
        
        events = self.events_repo.get_events_starting_between(start, end)
        
        next_frame = [""]*24
        
        # Populate the frame with meetings
        for event in events:
            next_frame[event['start'][3]] = "g"

        # Add the current time marker    
        next_frame[now[3]] = "y" if next_frame[now[3]] == "" else "r"
        
        self.bargraph.set_frame_from_text(next_frame)