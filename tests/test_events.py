"""Hermetic desktop tests for events.py -- Phase 2, day-meter-dev-test-suite plan.

Run from repo root with no installs or board hardware:
    python3 -m unittest discover tests

Clock discipline: get_current_event/get_next_event are exercised via the new
optional `now` kwarg (decision D2) and, for the default path, via freeze_clock --
keeping every expectation independent of wall clock, timezone and DST.
"""

import time
import unittest

import events
from fakes import freeze_clock


def st(y, mo, d, h, mi, s):
    """A struct_time shaped exactly like iso_to_time_struct's output."""
    return time.struct_time((y, mo, d, h, mi, s, 0, -1, -1))


class IsoHelperTests(unittest.TestCase):
    def test_round_trip(self):
        original = st(2026, 11, 11, 9, 30, 45)
        self.assertEqual(events.iso_to_time_struct(events.time_struct_to_iso(original)), original)

    def test_iso_output_format(self):
        self.assertEqual(events.time_struct_to_iso(st(2026, 1, 2, 3, 4, 5)), "2026-01-02T03:04:05Z")

    def test_z_suffix_stripped(self):
        # Pinned current behavior: the trailing Z is dropped.
        self.assertEqual(events.iso_to_time_struct("2026-11-11T09:30:00Z"), st(2026, 11, 11, 9, 30, 0))

    def test_positive_offset_crashes(self):
        # Pinned current behavior: "+HH:MM" splits into four colon fields -> ValueError.
        self.assertRaises(ValueError, events.iso_to_time_struct, "2026-11-11T09:30:00+05:00")

    def test_negative_offset_silently_mis_parses(self):
        # Pinned current behavior: "-HH:MM" is chopped at the first "-" and never applied,
        # so a 09:30 time with -05:00 offset parses as nominal 09:30 (wrong by 5h).
        self.assertEqual(events.iso_to_time_struct("2026-11-11T09:30:00-05:00"), st(2026, 11, 11, 9, 30, 0))


class LoadEventsFromGoogleTests(unittest.TestCase):
    def _google_events(self):
        return [
            {"start": {"dateTime": "2026-11-11T09:00:00Z"}, "end": {"dateTime": "2026-11-11T10:00:00Z"}, "eventType": "default"},
            {"start": {"date": "2026-11-11"}, "end": {"date": "2026-11-12"}},
            {"start": {"dateTime": "2026-11-11T14:00:00Z"}, "end": {"dateTime": "2026-11-11T15:00:00Z"}, "eventType": "outOfOffice"},
        ]

    def test_stores_datetime_and_excludes_all_day(self):
        repo = events.EventsRepository()
        repo.load_events_from_google(self._google_events())
        self.assertEqual(len(repo.EVENTS), 2)   # all-day excluded; OOO still stored (next test)
        self.assertEqual(repo.EVENTS[0]["start"], st(2026, 11, 11, 9, 0, 0))
        self.assertEqual(repo.EVENTS[0]["end"], st(2026, 11, 11, 10, 0, 0))

    def test_out_of_office_not_filtered_current_behavior(self):
        # Pinned: the out-of-office clause in _is_storable_g_event is commented out,
        # so an OOO event IS stored. Update this assertion when that filter returns.
        repo = events.EventsRepository()
        repo.load_events_from_google(self._google_events())
        self.assertEqual(repo.EVENTS[1]["start"], st(2026, 11, 11, 14, 0, 0))


class CurrentNextEventTests(unittest.TestCase):
    def _repo(self):
        repo = events.EventsRepository()
        # A and B overlap; C is later.
        repo.load_events([
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 9, 30, 0), "end": st(2026, 11, 11, 11, 0, 0)},
            {"start": st(2026, 11, 11, 12, 0, 0), "end": st(2026, 11, 11, 13, 0, 0)},
        ])
        return repo

    def test_before_any_event(self):
        repo = self._repo()
        before = st(2026, 11, 11, 8, 30, 0)
        self.assertIsNone(repo.get_current_event(now=before))
        self.assertEqual(repo.get_next_event(now=before)["start"], st(2026, 11, 11, 9, 0, 0))

    def test_overlap_returns_first_match(self):
        repo = self._repo()
        during_both = st(2026, 11, 11, 9, 45, 0)
        self.assertEqual(repo.get_current_event(now=during_both)["start"], st(2026, 11, 11, 9, 0, 0))

    def test_during_second_event_only(self):
        repo = self._repo()
        during_b = st(2026, 11, 11, 10, 30, 0)
        self.assertEqual(repo.get_current_event(now=during_b)["start"], st(2026, 11, 11, 9, 30, 0))
        self.assertEqual(repo.get_next_event(now=during_b)["start"], st(2026, 11, 11, 12, 0, 0))

    def test_at_exact_start_is_not_upcoming(self):
        # Pinned: current requires start < now and end > now; upcoming requires start > now.
        # At B's exact start (while A still runs) B is neither current nor upcoming; next is C.
        repo = self._repo()
        at_b_start = st(2026, 11, 11, 9, 30, 0)
        self.assertEqual(repo.get_current_event(now=at_b_start)["start"], st(2026, 11, 11, 9, 0, 0))
        self.assertEqual(repo.get_next_event(now=at_b_start)["start"], st(2026, 11, 11, 12, 0, 0))

    def test_after_all_events(self):
        repo = self._repo()
        after = st(2026, 11, 11, 13, 30, 0)
        self.assertIsNone(repo.get_current_event(now=after))
        self.assertIsNone(repo.get_next_event(now=after))

    def test_no_events(self):
        repo = events.EventsRepository()
        repo.load_events([])
        now = st(2026, 11, 11, 9, 0, 0)
        self.assertIsNone(repo.get_current_event(now=now))
        self.assertIsNone(repo.get_next_event(now=now))

    def test_default_path_unchanged_on_device_behavior(self):
        # D2: with no kwarg the method still reads time.localtime() exactly as today;
        # freeze_clock makes that read hermetic.
        repo = self._repo()
        with freeze_clock(st(2026, 11, 11, 9, 45, 0)):
            self.assertEqual(repo.get_current_event()["start"], st(2026, 11, 11, 9, 0, 0))
            self.assertEqual(repo.get_next_event()["start"], st(2026, 11, 11, 12, 0, 0))


class GetEventsStartingBetweenTests(unittest.TestCase):
    def _repo(self):
        repo = events.EventsRepository()
        repo.load_events([
            {"start": st(2026, 11, 11, 9, 0, 0), "end": st(2026, 11, 11, 10, 0, 0)},
            {"start": st(2026, 11, 11, 9, 30, 0), "end": st(2026, 11, 11, 11, 0, 0)},
            {"start": st(2026, 11, 11, 12, 0, 0), "end": st(2026, 11, 11, 13, 0, 0)},
        ])
        return repo

    def test_struct_window_inclusive_start_exclusive_end(self):
        repo = self._repo()
        # Start boundary inclusive; end exclusive -- C starts exactly at the end and is excluded.
        found = repo.get_events_starting_between(st(2026, 11, 11, 9, 0, 0), st(2026, 11, 11, 12, 0, 0))
        self.assertEqual([e["start"] for e in found], [st(2026, 11, 11, 9, 0, 0), st(2026, 11, 11, 9, 30, 0)])

    def test_struct_window_exact_boundaries(self):
        repo = self._repo()
        found = repo.get_events_starting_between(st(2026, 11, 11, 12, 0, 0), st(2026, 11, 11, 13, 0, 0))
        self.assertEqual([e["start"] for e in found], [st(2026, 11, 11, 12, 0, 0)])

    def test_int_end_converts_end_not_start(self):
        # D4 fixed: int `end` is converted via time.localtime(end); a struct
        # `start` is left untouched (no conversion). With a struct start + int
        # end the method no longer raises (the old bug did time.localtime(<struct>)).
        # Expected is derived the same way (struct start, localtime(end) bound)
        # so the assertion is independent of wall clock / timezone / DST.
        repo = self._repo()
        start_struct = st(2026, 11, 11, 9, 0, 0)
        end_epoch = 1764518400
        expected = [e["start"] for e in repo.EVENTS
                    if e["start"] >= start_struct and e["start"] < time.localtime(end_epoch)]
        found = repo.get_events_starting_between(start_struct, end_epoch)
        self.assertEqual([e["start"] for e in found], expected)


class HourBoundaryTests(unittest.TestCase):
    NOW = st(2026, 11, 11, 15, 47, 3)

    def test_start_of_hour_default(self):
        self.assertEqual(events.start_of_hour(self.NOW), st(2026, 11, 11, 0, 0, 0))

    def test_end_of_hour_default(self):
        self.assertEqual(events.end_of_hour(self.NOW), st(2026, 11, 11, 23, 59, 59))

    def test_custom_hours_preserve_date_and_tail_fields(self):
        # start_of_hour/end_of_hour keep input struct fields [6:9] (wday/yday/isdst) verbatim.
        self.assertEqual(events.start_of_hour(self.NOW, 8), st(2026, 11, 11, 8, 0, 0))
        self.assertEqual(events.end_of_hour(self.NOW, 19), st(2026, 11, 11, 19, 59, 59))


if __name__ == "__main__":
    unittest.main()
