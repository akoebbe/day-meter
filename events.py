import time

class EventsRepository():

    # TODO: Make this a class
    EVENTS = []

    def load_events(self, events_list):
        self.EVENTS = events_list

    def load_events_from_google(self, g_events):
        new_events = []
        for g_event in g_events:
            if self._is_storable_g_event(g_event):
                new_events.append({"start": iso_to_time_struct(g_event["start"]["dateTime"]), "end": iso_to_time_struct(g_event["end"]["dateTime"])})
        self.EVENTS = new_events

    def get_current_event(self):
        now = time.localtime()
        
        current_events = [event for event in self.EVENTS if event["start"] < now and event["end"] > now]
        if len(current_events) > 0:
            return current_events[0]
        
        return None
    
    def get_events_starting_between(self, start, end):
        if isinstance(start, int):
            start = time.localtime(start)
        if isinstance(end, int):
            end = time.localtime(start)
            
        found = [event for event in self.EVENTS if event["start"] >= start and event["start"] < end]
        
        print("Found {0} events between {1} and {2}".format(len(found), time_struct_to_iso(start), time_struct_to_iso(end)))
        
        return found

    def get_next_event(self):
        now = time.localtime()
        
        upcoming_events = [event for event in self.EVENTS if event["start"] > now]
        if len(upcoming_events) > 0:
            return upcoming_events[0]
        return None

    def _is_storable_g_event(self, g_event):
        return not self._is_all_day_event(g_event) and not self._is_out_of_office_event(g_event)
    
    def _is_all_day_event(self, g_event):
        return "date" in g_event["start"]

    def _is_out_of_office_event(self, g_event):
        return g_event["eventType"] == "outOfOffice"
        

def time_struct_to_iso(time):
    return  "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}{:s}".format(
        time[0],
        time[1],
        time[2],
        time[3],
        time[4],
        time[5],
        "Z",
    )

def iso_to_time_struct(datetime):
    """Formats ISO-formatted datetime returned by Google Calendar API into
    a struct_time.
    :param str datetime: Datetime string returned by Google Calendar API
    :return: struct_time

    """
    times = datetime.split("T")
    the_date = times[0]
    the_time = times[1]
    year, month, mday = [int(x) for x in the_date.split("-")]
    the_time = the_time.split("-")[0]
    if "Z" in the_time:
        the_time = the_time.split("Z")[0]
    hours, minutes, seconds = [int(x) for x in the_time.split(":")]

    new_date = time.struct_time(
            (
                year,
                month,
                mday,
                hours,
                minutes,
                seconds,
                0,
                -1,
                -1
            )
        )
    return new_date

def start_of_hour(time_struct, hour=0):
    start = time.struct_time(
            (
                time_struct[0],
                time_struct[1],
                time_struct[2],
                hour,
                0,
                0,
                time_struct[6],
                time_struct[7],
                time_struct[8],
            )
    )

    return start

def end_of_hour(time_struct, hour=23):
    end = time.struct_time(
            (
                time_struct[0],
                time_struct[1],
                time_struct[2],
                hour,
                59,
                59,
                time_struct[6],
                time_struct[7],
                time_struct[8],
            )
    )

    return end