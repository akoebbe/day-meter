import board
import socketpool
import time


import rtc
import wifi
import asyncio
import gcal
from renderers import static_day_renderer, static_half_day_renderer, meeting_countdown, meeting_time_left, zoom_day_renderer, meeting_alert, stack as stack_mod
from meeting_alert_controller import MeetingAlert
import ssl
import adafruit_requests
import gc
import adafruit_ntp
from posix_tz import parse_posix_tz, utc_to_local
from events import EventsRepository
import digitalio
from adafruit_debouncer import Button
from display.selector import build_display


pin = digitalio.DigitalInOut(board.BUTTON)
pin.switch_to_input(pull=digitalio.Pull.UP)
boot_button = Button(pin)

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from mysecrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

display = build_display(secrets)
gc.collect()
print("Mem Free: {} bytes (start)".format(gc.mem_free()))


print("\n----------------------------------------\n")
print("Connecting to Wifi: {0}".format(secrets["ssid"]))
display.progress(0.25, commit=True)
while True:
    try:
        wifi.radio.connect(secrets['ssid'], secrets['password'])
        break
    except Exception as inst:
        print(inst, "(Retrying)")
        display.progress(0.25, commit=True, color="y")
        time.sleep(1)
        display.progress(0.25, commit=True)

gc.collect()
print("Mem Free: {} bytes (wifi)".format(gc.mem_free()))
    
print("Connected with IP address of {0}".format(wifi.radio.ipv4_address))
print("\n----------------------------------------\n")

pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())

gc.collect()
print("Mem Free: {} bytes (request init)".format(gc.mem_free()))

display.progress(0.5, commit=True)
while True:
    print("Getting time from NTP")
    try:
        ntp = adafruit_ntp.NTP(pool)
        rtc.RTC().datetime = ntp.datetime
        gc.collect()
        print("Mem Free: {} bytes (ntp)".format(gc.mem_free()))
        break
    except Exception as inst:
        print(inst, "(Retrying)")
        display.progress(0.5, commit=True, color="y")
        time.sleep(1)
        display.progress(0.5, commit=True)



print("Current time is {0}".format(time.localtime()))
print("\n----------------------------------------\n")

# ONE TIME USE for client oauth (uncommnet if you have to reset client keys)
# gcal.initialize_client_keys()

display.progress(0.75, commit=True)
while True:
    print("Refreshing Google Token")
    try:
        gcal.refresh_token()
        break
    except Exception as inst:
        print(inst, "(Retrying)")
        display.progress(0.75, commit=True, color="y")
        time.sleep(1)
        display.progress(0.75, commit=True)

gc.collect()
print("Mem Free: {} bytes (google token)".format(gc.mem_free()))

print("\n----------------------------------------\n")

display.progress(1, commit=True)
try:
    tz = parse_posix_tz(secrets.get("timezone"))
except (ValueError, TypeError, AttributeError):
    tz = None
cal_events = EventsRepository(tz=tz, filter_out_of_office=secrets.get("filter_out_of_office", False))
#day_renderer = static_day_renderer.StaticDayRenderer(cal_events, display)
half_day_renderer = static_half_day_renderer.StaticHalfDayRenderer(cal_events, display, 8)
meeting_countdown_renderer = meeting_countdown.MeetingCountdown(cal_events, display, 10)
meeting_time_left_renderer = meeting_time_left.MeetingTimeLeft(cal_events, display)
zoom_day_renderer = zoom_day_renderer.ZoomDayRenderer(cal_events, display)
alert = MeetingAlert(duration_s=secrets.get("alert_duration_s", 5), cadence_s=secrets.get("alert_cadence_s", 1))
alert_renderer = meeting_alert.MeetingAlertRenderer(cal_events, display, alert)
# Display layer stack (topmost-wins; single commit per layer)
alert_layer = stack_mod.AlertLayer(alert, alert_renderer, cadence_s=secrets.get("alert_cadence_s", 0.2))
meetings_layer = stack_mod.MeetingsLayer(cal_events, meeting_countdown_renderer, meeting_time_left_renderer, cadence_s=5)
base_layer = stack_mod.BaseLayer([half_day_renderer], cadence_s=5)
stack = [alert_layer, meetings_layer, base_layer]

gc.collect()
print("Mem Free: {} bytes (init)".format(gc.mem_free()))

async def refresh_token_runner():
    while True:
        print("Refreshing token")
        try:
            gcal.refresh_token()
        except Exception as e:
            print("Couldn't refresh token. Skipping this attempt. Exception: {}".format(e))
            continue            
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


async def alert_runner():
    while True:
        now = utc_to_local(time.localtime(), cal_events.tz)
        started = alert.on_tick(cal_events, now)
        if started:
            alert_renderer.mark_started(now)
        alert_layer.paint(now, display)
        gc.collect()
        print("Mem Free: {} bytes (alert_runner)".format(gc.mem_free()))
        await asyncio.sleep(secrets.get("alert_cadence_s", 0.2))


async def base_runner():
    while True:
        now = utc_to_local(time.localtime(), cal_events.tz)
        if not alert.is_active(now):
            for layer in (meetings_layer, base_layer):
                if layer.paint(now, display):
                    break
        gc.collect()
        print("Mem Free: {} bytes (base_runner)".format(gc.mem_free()))
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
    alert_task = asyncio.create_task(alert_runner())
    base_task = asyncio.create_task(base_runner())
    button_task = asyncio.create_task(button_listener())

    await asyncio.gather(
        refresh_token_task, event_fetcher_task, alert_task, base_task, button_task
    )

try:
    asyncio.run(main())
except Exception as e:
    print("Async loop failed. Resetting the microcontroller. Exception: {}".format(e))
    import microcontroller
    microcontroller.reset()
