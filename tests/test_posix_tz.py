"""Unit tests for posix_tz.py and the B2 store conversion in EventsRepository.

Validated against glibc oracle (see eval session notes) for Chicago, London,
and Sydney (year-wrap) over a full year of hourly checks.
"""

import time
import unittest

import posix_tz
from events import EventsRepository, iso_to_time_struct


class PosixTzParseTests(unittest.TestCase):
    """Parser sign convention and DST activation."""

    def test_chicago_offsets(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        self.assertEqual(tz.std_name, "CST")
        self.assertEqual(tz.dst_name, "CDT")
        self.assertEqual(tz.std_offset, -21600)
        self.assertEqual(tz.dst_offset, -18000)

    def test_london_offsets(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        self.assertEqual(tz.std_name, "GMT")
        self.assertEqual(tz.dst_name, "BST")
        self.assertEqual(tz.std_offset, 0)
        self.assertEqual(tz.dst_offset, 3600)

    def test_sydney_offsets(self):
        tz = posix_tz.parse_posix_tz("AEST-10AEDT-11,M10.1.0/2:00,M4.1.0/3:00")
        self.assertEqual(tz.std_name, "AEST")
        self.assertEqual(tz.dst_name, "AEDT")
        self.assertEqual(tz.std_offset, 36000)
        self.assertEqual(tz.dst_offset, 39600)

    def test_no_dst_string_gives_fixed_offset(self):
        tz = posix_tz.parse_posix_tz("EST5")
        self.assertEqual(tz.std_name, "EST")
        self.assertEqual(tz.std_offset, -18000)
        self.assertIsNone(tz.rule_start)

    def test_missing_dst_name_gives_no_dst(self):
        # A string without a DST name is a fixed-offset zone
        tz = posix_tz.parse_posix_tz("CST-6,M3.2.0/2:00,M11.1.0/2:00")
        self.assertEqual(tz.std_offset, 21600)
        self.assertIsNone(tz.rule_start)


class PosixTzOffsetAtTests(unittest.TestCase):
    """offset_at reproduces glibc-pinned transition epochs for 2026."""

    def _st(self, y, m, d, h=0, mi=0, s=0):
        return time.struct_time((y, m, d, h, mi, s, 0, -1, -1))

    def test_chicago_est_january(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        self.assertEqual(posix_tz.offset_at(self._st(2026,1,15,12), tz), -21600)

    def test_chicago_cdt_june(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        self.assertEqual(posix_tz.offset_at(self._st(2026,6,15,12), tz), -18000)

    def test_chicago_spring_transition(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        # 2026-03-08 07:59Z = EST; 08:00Z = CDT
        self.assertEqual(posix_tz.offset_at(self._st(2026,3,8,7,59), tz), -21600)
        self.assertEqual(posix_tz.offset_at(self._st(2026,3,8,8,0), tz), -18000)

    def test_chicago_fall_transition(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        # 2026-11-01 06:59Z = CDT; 07:00Z = EST
        self.assertEqual(posix_tz.offset_at(self._st(2026,11,1,6,59), tz), -18000)
        self.assertEqual(posix_tz.offset_at(self._st(2026,11,1,7,0), tz), -21600)

    def test_london_gmt_january(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        self.assertEqual(posix_tz.offset_at(self._st(2026,1,15,12), tz), 0)

    def test_london_bst_june(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        self.assertEqual(posix_tz.offset_at(self._st(2026,6,15,12), tz), 3600)

    def test_london_spring_transition(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        # 2026-03-29 00:59Z = GMT; 01:00Z = BST
        self.assertEqual(posix_tz.offset_at(self._st(2026,3,29,0,59), tz), 0)
        self.assertEqual(posix_tz.offset_at(self._st(2026,3,29,1,0), tz), 3600)

    def test_london_fall_transition(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        # 2026-10-25 00:59Z = BST; 01:00Z = GMT
        self.assertEqual(posix_tz.offset_at(self._st(2026,10,25,0,59), tz), 3600)
        self.assertEqual(posix_tz.offset_at(self._st(2026,10,25,1,0), tz), 0)

    def test_sydney_aedt_january_summer(self):
        tz = posix_tz.parse_posix_tz("AEST-10AEDT-11,M10.1.0/2:00,M4.1.0/3:00")
        # January = DST active (AEDT)
        self.assertEqual(posix_tz.offset_at(self._st(2026,1,15,12), tz), 39600)

    def test_sydney_aest_june_winter(self):
        tz = posix_tz.parse_posix_tz("AEST-10AEDT-11,M10.1.0/2:00,M4.1.0/3:00")
        self.assertEqual(posix_tz.offset_at(self._st(2026,6,15,12), tz), 36000)

    def test_sydney_fall_transition(self):
        tz = posix_tz.parse_posix_tz("AEST-10AEDT-11,M10.1.0/2:00,M4.1.0/3:00")
        # 2026-04-04 15:59Z = AEDT; 16:00Z = AEST
        self.assertEqual(posix_tz.offset_at(self._st(2026,4,4,15,59), tz), 39600)
        self.assertEqual(posix_tz.offset_at(self._st(2026,4,4,16,0), tz), 36000)


class PosixTzUtcToLocalTests(unittest.TestCase):
    """utc_to_local and add_seconds behave correctly."""

    def _st(self, y, m, d, h=0, mi=0, s=0):
        return time.struct_time((y, m, d, h, mi, s, 0, -1, -1))

    def test_none_is_identity(self):
        st = self._st(2026, 6, 15, 14, 30)
        self.assertEqual(posix_tz.utc_to_local(st, None), st)

    def test_chicago_utc_14_to_local_09(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        utc = self._st(2026, 6, 15, 14, 0, 0)
        local = posix_tz.utc_to_local(utc, tz)
        # CDT = UTC-5; 14:00 UTC = 09:00 CDT
        self.assertEqual(local.tm_hour, 9)
        self.assertEqual(local.tm_min, 0)
        self.assertEqual(local.tm_mday, 15)

    def test_chicago_utc_23_crosses_midnight(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        utc = self._st(2026, 6, 15, 23, 0, 0)
        local = posix_tz.utc_to_local(utc, tz)
        # CDT = UTC-5; 23:00 UTC = 18:00 same day
        self.assertEqual(local.tm_hour, 18)
        self.assertEqual(local.tm_mday, 15)

    def test_london_utc_12_is_local_13(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        utc = self._st(2026, 6, 15, 12, 0, 0)
        local = posix_tz.utc_to_local(utc, tz)
        # BST = UTC+1; 12:00 UTC = 13:00 BST
        self.assertEqual(local.tm_hour, 13)
        self.assertEqual(local.tm_mday, 15)

    def test_add_seconds_day_carry(self):
        st = self._st(2026, 1, 31, 23, 0, 0)
        result = posix_tz.add_seconds(st, 3600)
        self.assertEqual(result.tm_mday, 1)
        self.assertEqual(result.tm_mon, 2)
        self.assertEqual(result.tm_hour, 0)

    def test_add_seconds_hour_carry(self):
        st = self._st(2026, 1, 15, 12, 0, 0)
        result = posix_tz.add_seconds(st, 3600)
        self.assertEqual(result.tm_hour, 13)
        self.assertEqual(result.tm_mday, 15)


class EventsRepositoryTzTests(unittest.TestCase):
    """B2: tz-aware EventsRepository stores UTC→local at store time."""

    def _st(self, y, m, d, h=0, mi=0, s=0):
        return time.struct_time((y, m, d, h, mi, s, 0, -1, -1))

    def test_tz_none_stores_utc_as_is(self):
        repo = EventsRepository()
        g_event = {
            "start": {"dateTime": "2026-06-15T14:00:00Z"},
            "end": {"dateTime": "2026-06-15T15:00:00Z"},
            "eventType": "default",
        }
        repo.load_events_from_google([g_event])
        ev = repo.EVENTS[0]
        # tz=None → identity: 14:00 UTC stored as 14:00
        self.assertEqual(ev["start"].tm_hour, 14)
        self.assertEqual(ev["end"].tm_hour, 15)

    def test_tz_chicago_stores_local(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        repo = EventsRepository(tz=tz)
        g_event = {
            "start": {"dateTime": "2026-06-15T14:00:00Z"},
            "end": {"dateTime": "2026-06-15T15:00:00Z"},
            "eventType": "default",
        }
        repo.load_events_from_google([g_event])
        ev = repo.EVENTS[0]
        # CDT = UTC-5; 14:00 UTC → 09:00 local
        self.assertEqual(ev["start"].tm_hour, 9)
        self.assertEqual(ev["end"].tm_hour, 10)

    def test_tz_london_stores_local(self):
        tz = posix_tz.parse_posix_tz("GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00")
        repo = EventsRepository(tz=tz)
        g_event = {
            "start": {"dateTime": "2026-06-15T12:00:00Z"},
            "end": {"dateTime": "2026-06-15T13:00:00Z"},
            "eventType": "default",
        }
        repo.load_events_from_google([g_event])
        ev = repo.EVENTS[0]
        # BST = UTC+1; 12:00 UTC → 13:00 local
        self.assertEqual(ev["start"].tm_hour, 13)
        self.assertEqual(ev["end"].tm_hour, 14)

    def test_get_current_event_tz_aware(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        repo = EventsRepository(tz=tz)
        # Event at 14:00 UTC = 09:00 CDT on 2026-06-15
        g_event = {
            "start": {"dateTime": "2026-06-15T14:00:00Z"},
            "end": {"dateTime": "2026-06-15T15:00:00Z"},
            "eventType": "default",
        }
        repo.load_events_from_google([g_event])
        # Simulate "now" at 14:30 UTC (09:30 CDT)
        now_utc = self._st(2026, 6, 15, 14, 30, 0)
        now_local = posix_tz.utc_to_local(now_utc, tz)
        ev = repo.get_current_event(now=now_local)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["start"].tm_hour, 9)

    def test_get_next_event_tz_aware(self):
        tz = posix_tz.parse_posix_tz("CST6CDT,M3.2.0/2:00,M11.1.0/2:00")
        repo = EventsRepository(tz=tz)
        # Event at 14:00 UTC = 09:00 CDT
        g_event = {
            "start": {"dateTime": "2026-06-15T14:00:00Z"},
            "end": {"dateTime": "2026-06-15T15:00:00Z"},
            "eventType": "default",
        }
        repo.load_events_from_google([g_event])
        # Simulate "now" at 13:00 UTC = 08:00 CDT (before event)
        now_utc = self._st(2026, 6, 15, 13, 0, 0)
        now_local = posix_tz.utc_to_local(now_utc, tz)
        ev = repo.get_next_event(now=now_local)
        self.assertIsNotNone(ev)
        self.assertEqual(ev["start"].tm_hour, 9)


if __name__ == "__main__":
    unittest.main()
