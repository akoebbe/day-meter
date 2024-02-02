import time
import socketpool
import wifi
import ssl
import adafruit_requests
from events import time_struct_to_iso
from adafruit_oauth2 import OAuth2

try:
    from secrets import secrets
except ImportError:
    print("Google secrets are kept in secrets.py, please add them there!")
    raise

pool = socketpool.SocketPool(wifi.radio)

requests = adafruit_requests.Session(pool, ssl.create_default_context())
scopes = ["https://www.googleapis.com/auth/calendar.readonly"]

# Calendar ID
CALENDAR_ID = "andrew.koebbe@uniteus.com"

# Maximum amount of events to fetch
MAX_EVENTS = 40

# Amount of time to wait between refreshing the calendar, in minutes
REFRESH_TIME = 15

# Initialize an OAuth2 object with GCal API scope
scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
google_auth = OAuth2(
    requests,
    secrets["google_client_id"],
    secrets["google_client_secret"],
    scopes,
    secrets["google_access_token"],
    secrets["google_refresh_token"],
)

def refresh_token():
    try:
        print("Trying to refresh Google Auth Token:", end="")
        google_auth.refresh_access_token()
    except Exception as e:
        print("Failed")
        raise RuntimeError("Unable to refresh access token - has the token been revoked?")
    
    print("Success")

def get_calendar_events():
    """Returns events on a specified calendar.
    Response is a list of events ordered by their start date/time in ascending order.
    """
    
    yesterday = time.localtime(time.time() - 60*60*24)
    tomorrow = time.localtime(time.time() + 60*60*24)
    start_of_yesterday = time.struct_time(
            (
                yesterday[0],
                yesterday[1],
                yesterday[2],
                0,
                0,
                0,
                yesterday[6],
                yesterday[7],
                yesterday[8],
            )
    )
    
    end_of_tomorrow = time.struct_time(
            (
                tomorrow[0],
                tomorrow[1],
                tomorrow[2],
                23,
                59,
                59,
                tomorrow[6],
                tomorrow[7],
                tomorrow[8],
            )
    )
    
    print("Fetching calendar events between {0} and {1}".format(time_struct_to_iso(start_of_yesterday), time_struct_to_iso(end_of_tomorrow)))

    headers = {
        "Authorization": "Bearer " + google_auth.access_token,
        "Accept": "application/json",
        "Content-Length": "0",
    }
    
    url = (
        "https://www.googleapis.com/calendar/v3/calendars/{0}/events"
        "?maxResults={1}"
        "&orderBy=startTime"
        "&singleEvents=true"
        "&timeMin={2}"
        "&timeMax={3}"
        "&maxAttendees=1"
        "&fields=items(start,end,eventType)"
        .format(CALENDAR_ID, MAX_EVENTS, time_struct_to_iso(start_of_yesterday), time_struct_to_iso(end_of_tomorrow))
    )
    
    print(url)
    
    resp = requests.get(url, headers=headers)
    resp_json = resp.json()
    if "error" in resp_json:
        raise RuntimeError("Error:", resp_json)
    resp.close()
    # parse the 'items' array so we can iterate over it easier
    resp_items = resp_json["items"]
    if not resp_items:
        print("No events scheduled for today!")
        resp_items = []
    print("Found {0} calendar items.".format(len(resp_items)))
    # del resp
    return resp_items
