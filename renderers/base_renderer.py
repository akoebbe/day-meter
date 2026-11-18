from events import EventsRepository, start_of_hour, end_of_hour
import time
import math
class BaseRenderer:
    def __init__(self, events: EventsRepository, bargraph, width: int = 24):
        self.events_repo = events
        self.bargraph = bargraph
        self.width = width

    def frame(self, now):
        """Pure: return a self.width-LED frame list, or None (no write).

        Sub-width frames are intended to be composed (frame_math.compose) into a
        full-width frame before a hardware write; render() writes the frame at
        this renderer's width (board renderers are width=24 in v1).
        """
        raise NotImplementedError

    def render(self, now):
        next_frame = self.frame(now)
        if next_frame is not None:
            self.bargraph.set_frame(next_frame)