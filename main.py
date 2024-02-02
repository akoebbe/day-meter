import board
import socketpool
import time
import rtc
import wifi
import asyncio
import bargraph
import gcal
from renderers import static_day_renderer, static_half_day_renderer, meeting_countdown, meeting_time_left, zoom_day_renderer
import ssl
import adafruit_requests
import gc
from adafruit_io.adafruit_io import IO_HTTP
from events import EventsRepository
import digitalio
from adafruit_debouncer import Button


pin = digitalio.DigitalInOut(board.BUTTON)
pin.switch_to_input(pull=digitalio.Pull.UP)
boot_button = Button(pin)

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

gc.collect()
print("Mem Free: {} bytes (start)".format(gc.mem_free()))


print("\n----------------------------------------\n")
print("Connecting to Wifi: {0}".format(secrets["ssid"]))
bargraph.progress(0.25, commit=True)
while True:
    try:
        wifi.radio.connect(secrets['ssid'], secrets['password'])
        break
    except Exception as inst:
        print(inst, "(Retrying)")
        time.sleep(1)

gc.collect()
print("Mem Free: {} bytes (wifi)".format(gc.mem_free()))

    
print("Connected with IP address of {0}".format(wifi.radio.ipv4_address))
print("\n----------------------------------------\n")

cal_events = EventsRepository()
#day_renderer = static_day_renderer.StaticDayRenderer(cal_events, bargraph)
half_day_renderer = static_half_day_renderer.StaticHalfDayRenderer(cal_events, bargraph, 8)
meeting_countdown_renderer = meeting_countdown.MeetingCountdown(cal_events, bargraph, 10)
meeting_time_left_renderer = meeting_time_left.MeetingTimeLeft(cal_events, bargraph)
zoom_day_renderer = zoom_day_renderer.ZoomDayRenderer(cal_events, bargraph)

gc.collect()
print("Mem Free: {} bytes (init)".format(gc.mem_free()))


pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

gc.collect()
print("Mem Free: {} bytes (request init)".format(gc.mem_free()))

bargraph.progress(0.5, commit=True)
print("Getting time from Adafruit.io internet")
while True:
    try:
        # ntp = adafruit_ntp.NTP(pool, tz_offset=0)
        # rtc.RTC().datetime = ntp.datetime

        aio_username = secrets["aio_username"]
        aio_key = secrets["aio_key"]
        location = secrets.get("timezone", None)
        io = IO_HTTP(aio_username, aio_key, requests)

        rtc.RTC().datetime = io.receive_time()
        # del IO_HTTP, io, location, aio_key, aio_username
        gc.collect()
        print("Mem Free: {} bytes (adafruit io)".format(gc.mem_free()))

        break
    except Exception as inst:
        print(inst, "(Retrying)")
        time.sleep(1)



print("Current time is {0}".format(time.localtime()))
print("\n----------------------------------------\n")


print("Refreshing Google Token")
bargraph.progress(0.75, commit=True)
gcal.refresh_token()
gc.collect()
print("Mem Free: {} bytes (google token)".format(gc.mem_free()))

print("\n----------------------------------------\n")

bargraph.progress(1, commit=True)


async def refresh_token_runner():
    while True:
        gcal.refresh_token()
        gc.collect()
        print("Mem Free: {} bytes (refresh_token_runner)".format(gc.mem_free()))
        await asyncio.sleep(gcal.REFRESH_TIME * 60)


async def event_fetcher():
    while True:
        g_events = gcal.get_calendar_events()
        cal_events.load_events_from_google(g_events)
        gc.collect()
        print("Mem Free: {} bytes (event_fetcher)".format(gc.mem_free()))
        await asyncio.sleep(300)

async def ticker():
    while True:
        #day_renderer.render(time.localtime())
        half_day_renderer.render(time.localtime())
        #zoom_day_renderer.render(time.localtime())
        meeting_countdown_renderer.render(time.localtime())
        meeting_time_left_renderer.render(time.localtime())
        # bargraph.progress((time.localtime().tm_min/60), justified="right")
        bargraph.commit_frame()

        gc.collect()
        print("Mem Free: {} bytes (ticker)".format(gc.mem_free()))

        await asyncio.sleep(5)

async def calendar_checker():
    while True:
        now = time.localtime()
        next_event = cal_events.get_next_event()
        if next_event:
            next_start = next_event["start"]
            next_end = next_event["end"]
            if next_start > now:
                print("Start is before now")

        gc.collect()
        print("Mem Free: {} bytes (calendar_checker)".format(gc.mem_free()))

        await asyncio.sleep(5)

async def button_listener():
    while True:
        boot_button.update()
        if boot_button.pressed:
            zoom_day_renderer.increment_zoom()
            print("Button pressed, new zoom level: {}".format(zoom_day_renderer.zoom_level))
        await asyncio.sleep(0)


async def main():
    refresh_token_task = asyncio.create_task(refresh_token_runner())
    event_fetcher_task = asyncio.create_task(event_fetcher())
    ticker_task = asyncio.create_task(ticker())
    button_task = asyncio.create_task(button_listener())
    
    await asyncio.gather(
        refresh_token_task, event_fetcher_task, ticker_task, button_task
    )

asyncio.run(main())

