from events import EventsRepository, start_of_hour, end_of_hour
import time
import math
import adafruit_datetime as datetime

UTC_OFFSET = -5
timezone = datetime.timezone.utc
timezone._offset = datetime.timedelta(  # pylint: disable=protected-access
    seconds=UTC_OFFSET * 3600
)

class BaseRenderer:
    def __init__(self, events: EventsRepository, bargraph):
        self.events_repo = events
        self.bargraph = bargraph

    def render(self, now):
        raise NotImplementedError