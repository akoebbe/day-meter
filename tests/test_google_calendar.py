"""Desktop tests for gcal.GoogleCalendar against a fake HTTP session.

gcal.py no longer builds wifi/socketpool/requests/OAuth2 at import time
(refactor todo item 8): the HTTP session is injected at boot and the secrets
are read in GoogleCalendar.__init__. These tests stub the board-only modules
(adafruit_oauth2, mysecrets) into sys.modules so the module imports on
desktop, then drive get_calendar_events()/refresh_token() against a fake
session.
"""

import sys
import types
import unittest

# A payload the fake session hands back: two events in the items array.
_ITEMS = [
    {"start": "2026-11-18T14:00:00Z", "end": "2026-11-18T15:00:00Z", "eventType": "default"},
    {"start": "2026-11-18T16:00:00Z", "end": "2026-11-18T16:30:00Z", "eventType": "default"},
]

SECRETS = {
    "google_calendar": "test-calendar-id",
    "google_client_id": "client-id",
    "google_client_secret": "client-secret",
    "google_access_token": "access-token",
    "google_refresh_token": "refresh-token",
}


class FakeOAuth2(object):
    """Stand-in for adafruit_oauth2.OAuth2; records its inputs and calls."""

    def __init__(self, session, client_id, client_secret, scopes,
                 access_token=None, refresh_token=None):
        self.session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.refresh_calls = 0

    def refresh_access_token(self):
        self.refresh_calls += 1

    def request_codes(self):
        self.verification_url = "https://example.com/verify"
        self.user_code = "TEST-CODE"

    def wait_for_authorization(self):
        return True


class FakeResponse(object):
    def __init__(self, payload):
        self._payload = payload
        self.closed = False

    def json(self):
        return self._payload

    def close(self):
        self.closed = True


class FakeSession(object):
    """Records GETs and returns a scripted response."""

    def __init__(self, payload):
        self.payload = payload
        self.urls = []
        self.headers_list = []
        self.last_response = None

    def get(self, url, headers=None):
        self.urls.append(url)
        self.headers_list.append(headers)
        self.last_response = FakeResponse(self.payload)
        return self.last_response


class gcal_stub(object):
    """Patches sys.modules so gcal imports on desktop.

    Injects a fake adafruit_oauth2 (FakeOAuth2) and a fake mysecrets (SECRETS);
    drops any cached gcal so the module body re-runs fresh. Restores sys.modules
    on exit. Enter *before* importing gcal.
    """

    def __init__(self):
        self._saved = {}

    def __enter__(self):
        oauth = types.ModuleType("adafruit_oauth2")
        oauth.OAuth2 = FakeOAuth2
        mysecrets = types.ModuleType("mysecrets")
        mysecrets.secrets = SECRETS
        self._saved = {
            name: sys.modules.get(name)
            for name in ("adafruit_oauth2", "mysecrets", "gcal")
        }
        sys.modules["adafruit_oauth2"] = oauth
        sys.modules["mysecrets"] = mysecrets
        sys.modules.pop("gcal", None)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for name, module in self._saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
        return False


class GoogleCalendarImportTests(unittest.TestCase):
    """Item 8: gcal must import cleanly with no at-import side effects."""

    def setUp(self):
        self.stub = gcal_stub()
        self.stub.__enter__()
        import gcal
        self.gcal = sys.modules["gcal"]

    def tearDown(self):
        self.stub.__exit__(None, None, None)

    def test_import_builds_no_session_or_auth(self):
        # The old module built pool/requests/google_auth at import time.
        self.assertFalse(hasattr(self.gcal, "pool"))
        self.assertFalse(hasattr(self.gcal, "requests"))
        self.assertFalse(hasattr(self.gcal, "google_auth"))

    def test_constants_survive(self):
        # main.py still reads gcal.REFRESH_TIME / gcal.MAX_EVENTS.
        self.assertEqual(self.gcal.REFRESH_TIME, 15)
        self.assertEqual(self.gcal.MAX_EVENTS, 40)


class GoogleCalendarFetchTests(unittest.TestCase):

    def setUp(self):
        self.stub = gcal_stub()
        self.stub.__enter__()
        import gcal
        self.gcal = sys.modules["gcal"]

    def tearDown(self):
        self.stub.__exit__(None, None, None)

    def test_constructor_reads_secrets(self):
        session = FakeSession({"items": []})
        cal = self.gcal.GoogleCalendar(session)
        self.assertEqual(cal.calendar_id, "test-calendar-id")
        self.assertIsInstance(cal._auth, FakeOAuth2)
        self.assertEqual(cal._auth.client_id, "client-id")
        self.assertEqual(cal._auth.access_token, "access-token")
        self.assertEqual(cal._auth.refresh_token, "refresh-token")

    def test_get_calendar_events_builds_ordered_url_and_parses_items(self):
        session = FakeSession({"items": _ITEMS})
        cal = self.gcal.GoogleCalendar(session)
        items = cal.get_calendar_events()
        self.assertEqual(items, _ITEMS)
        self.assertEqual(len(session.urls), 1)
        url = session.urls[0]
        # The critical params: ordered + UTC window + calendar id.
        self.assertIn("orderBy=startTime", url)
        self.assertIn("timeZone=UTC", url)
        self.assertIn("singleEvents=true", url)
        self.assertIn("maxResults=40", url)
        self.assertIn("test-calendar-id", url)
        self.assertIn("timeMin=", url)
        self.assertIn("timeMax=", url)
        # Auth header uses the injected access token.
        self.assertEqual(
            session.headers_list[0]["Authorization"],
            "Bearer access-token",
        )
        # Response closed after parse.
        self.assertTrue(session.last_response.closed)

    def test_refresh_token_calls_oauth(self):
        session = FakeSession({"items": []})
        cal = self.gcal.GoogleCalendar(session)
        cal.refresh_token()
        self.assertEqual(cal._auth.refresh_calls, 1)

    def test_error_payload_raises(self):
        session = FakeSession({"error": {"code": 401, "message": "unauthorized"}})
        cal = self.gcal.GoogleCalendar(session)
        with self.assertRaises(RuntimeError):
            cal.get_calendar_events()


if __name__ == "__main__":
    unittest.main()
