"""Pure-stdlib POSIX TZ parser for CircuitPython.

Provides:
  parse_posix_tz(s)       -> PosixTz
  offset_at(utc_struct, tz) -> int seconds
  utc_to_local(utc_struct, tz) -> struct_time
  add_seconds(struct, secs)    -> struct_time

Sign convention (pinned against glibc):
  The number in the string is hours WEST of UTC.
  UTC-offset-seconds = -(value * 3600).
  CST6  -> -21600 (EST)
  Sydney dst -11 -> +39600 (AEDT)

M-rule: field1=month, field2=week-of-month (1-based, 5=last),
        field3=weekday (0=Sunday), /H:MM = local wall time at transition.
Rule order is FIXED: rule[0]=start-of-DST (spring), rule[1]=end-of-DST (fall).
"""

import time


# ---------------------------------------------------------------------------
# Day-count helpers (pure integer, no datetime/calendar dependency)
# ---------------------------------------------------------------------------

def _days_before_year(year):
    """Total days from 1970-01-01 to Jan 1 of `year`."""
    days = (year - 1970) * 365
    for y in range(1970, year):
        if _is_leap(y):
            days += 1
    return days


def _is_leap(year):
    return (year % 4 == 0 and year % 100 != 0) or year % 400 == 0


def _days_in_month(year, month):
    dim = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    if month == 2 and _is_leap(year):
        return 29
    return dim[month]


def _days_before_month(year, month):
    """Days from Jan 1 to the start of `month` in `year`."""
    total = 0
    for m in range(1, month):
        total += _days_in_month(year, m)
    return total


def _date_to_day(year, month, day):
    """Total days from 1970-01-01 to the given date (1970-01-01 = 0)."""
    return _days_before_year(year) + _days_before_month(year, month) + (day - 1)


def _date_to_epoch(year, month, day, hour=0, minute=0, second=0):
    """Seconds since 1970-01-01 00:00:00 UTC for the given date."""
    return (_date_to_day(year, month, day) * 86400 +
            hour * 3600 + minute * 60 + second)


def _epoch_to_components(epoch):
    """Convert a UTC epoch (seconds since 1970) to (year, month, day, h, m, s)."""
    # Handle negative epochs (before 1970) — not expected but be safe
    day_adjust = 0
    if epoch < 0:
        epoch += 86400
        day_adjust = -1

    second = epoch % 60
    epoch //= 60
    minute = epoch % 60
    epoch //= 60
    hour = epoch % 24
    epoch //= 24
    day_count = epoch + day_adjust

    year = 1970
    while True:
        yd = 366 if _is_leap(year) else 365
        if day_count < yd:
            break
        day_count -= yd
        year += 1

    month = 1
    for m in range(1, 13):
        dim = _days_in_month(year, m)
        if day_count < dim:
            month = m
            break
        day_count -= dim

    day = day_count + 1
    return year, month, day, hour, minute, second


# ---------------------------------------------------------------------------
# M-rule helpers
# ---------------------------------------------------------------------------

def _find_nth_weekday(year, month, weekday, week):
    """Day-of-month for the Nth occurrence of weekday (0=Sun) in month.

    week: 1-4 = Nth occurrence (1-based), 5 = last occurrence.
    weekday: 0=Sunday, 1=Monday, ..., 6=Saturday.
    """
    dim = _days_in_month(year, month)

    # 1970-01-01 was a Thursday (weekday=4 in Sun=0 convention)
    day1 = _date_to_day(year, month, 1)
    wd_of_day1 = (4 + day1) % 7

    matching = []
    for d in range(1, dim + 1):
        if (wd_of_day1 + d - 1) % 7 == weekday:
            matching.append(d)

    if not matching:
        raise ValueError("No matching weekday for rule")

    if week == 5:
        return matching[-1]
    elif 1 <= week <= 4:
        return matching[week - 1]
    else:
        raise ValueError("week must be 1-5 (got {0})".format(week))


# ---------------------------------------------------------------------------
# POSIX TZ parsing
# ---------------------------------------------------------------------------

def _parse_offset(s, pos):
    """Parse an offset at position `pos` in string `s`.

    Returns (new_pos, utc_seconds).
    Format: [+-]HH[:MM[:SS]]  (POSIX convention: +N = N hours WEST of UTC)
    """
    if pos >= len(s):
        return pos, 0

    sign = 1
    if s[pos] == '-':
        sign = -1
        pos += 1
    elif s[pos] == '+':
        pos += 1

    # Parse the numeric portion (digits and colons)
    num_start = pos
    while pos < len(s):
        c = s[pos]
        if c.isdigit():
            pos += 1
        elif c == ':' and pos + 1 < len(s) and s[pos + 1].isdigit():
            pos += 1
        else:
            break

    num_str = s[num_start:pos]
    if not num_str:
        return pos, 0

    parts = num_str.split(':')
    hours = int(parts[0])
    minutes = int(parts[1]) if len(parts) > 1 else 0
    seconds = int(parts[2]) if len(parts) > 2 else 0

    offset_west = sign * (hours * 3600 + minutes * 60 + seconds)
    utc_secs = -offset_west  # invert: west-positive -> utc-negative

    return pos, utc_secs


def _parse_rule(s):
    """Parse one M-rule: M<month>.<week>.<weekday>/<hour>:<minute>."""
    # Expected: M3.2.0/2:00
    if s[0] != 'M':
        raise ValueError("Rule must start with M, got '{0}'".format(s[0]))

    body = s[1:]
    slash = body.find('/')
    if slash < 0:
        raise ValueError("Rule missing '/'")

    fields = body[:slash].split('.')
    if len(fields) != 3:
        raise ValueError("Rule must have 3 dot-separated fields")

    month = int(fields[0])
    week = int(fields[1])
    weekday = int(fields[2])

    time_str = body[slash + 1:]
    colon = time_str.find(':')
    if colon < 0:
        raise ValueError("Rule time missing ':'")

    hour = int(time_str[:colon])
    minute = int(time_str[colon + 1:])

    return {
        'month': month,
        'week': week,
        'weekday': weekday,
        'hour': hour,
        'minute': minute,
    }


class PosixTz(object):
    """Parsed POSIX TZ zone."""

    def __init__(self, std_name, dst_name, std_offset, dst_offset,
                 rule_start, rule_end):
        self.std_name = std_name
        self.dst_name = dst_name
        self.std_offset = std_offset    # seconds
        self.dst_offset = dst_offset    # seconds
        self.rule_start = rule_start    # dict (start of DST)
        self.rule_end = rule_end        # dict (end of DST)


def parse_posix_tz(s):
    """Parse a POSIX TZ string into a PosixTz object.

    Examples:
      CST6CDT,M3.2.0/2:00,M11.1.0/2:00
      GMT0BST-1,M3.5.0/1:00,M10.5.0/2:00
    """
    parts = s.split(',')
    name_off = parts[0]
    rules = parts[1:]

    # Find end of standard name (first digit, +, or -)
    i = 0
    while i < len(name_off):
        c = name_off[i]
        if c.isdigit() or c in ('+', '-'):
            break
        i += 1

    if i == 0 or i >= len(name_off):
        raise ValueError("No standard time name / offset in TZ string")

    std_name = name_off[:i]
    pos, std_secs = _parse_offset(name_off, i)

    # Parse optional DST name and offset
    dst_name = std_name
    dst_secs = std_secs + 3600  # default: one hour ahead of standard
    has_dst = False

    if pos < len(name_off):
        j = pos
        while j < len(name_off):
            c = name_off[j]
            if c.isdigit() or c in ('+', '-'):
                break
            j += 1
        if j > pos:
            dst_name = name_off[pos:j]
            has_dst = True
            if j < len(name_off):
                _, dst_secs = _parse_offset(name_off, j)
        # If no DST name found, dst_secs stays at std+3600

    if not has_dst:
        # No DST — return a zone with no transitions
        return PosixTz(std_name, std_name, std_secs, std_secs, None, None)

    if len(rules) < 2:
        raise ValueError("DST zone requires two rules, got {0}".format(len(rules)))

    rule_start = _parse_rule(rules[0])
    rule_end = _parse_rule(rules[1])

    return PosixTz(std_name, dst_name, std_secs, dst_secs, rule_start, rule_end)


# ---------------------------------------------------------------------------
# Offset and conversion
# ---------------------------------------------------------------------------

def _transition_epoch(rule, year, offset_before):
    """UTC epoch of the transition defined by the rule in `year`.

    The rule specifies a LOCAL WALL CLOCK time. The transition instant in UTC
    is: wall_epoch - offset_before.
    """
    day = _find_nth_weekday(year, rule['month'], rule['weekday'], rule['week'])
    wall_epoch = _date_to_epoch(year, rule['month'], day,
                                 rule['hour'], rule['minute'], 0)
    return wall_epoch - offset_before


def _struct_to_epoch(st):
    """UTC epoch for a struct_time (treated as UTC)."""
    return _date_to_epoch(st.tm_year, st.tm_mon, st.tm_mday,
                           st.tm_hour, st.tm_min, st.tm_sec)


def offset_at(utc_struct, tz):
    """UTC offset in seconds for the given UTC instant.

    Returns tz.std_offset or tz.dst_offset depending on whether DST is active.
    """
    if tz is None:
        return 0

    if tz.rule_start is None:
        return tz.std_offset

    year = utc_struct.tm_year
    start_ep = _transition_epoch(tz.rule_start, year, tz.std_offset)
    end_ep = _transition_epoch(tz.rule_end, year, tz.dst_offset)

    utc_ep = _struct_to_epoch(utc_struct)

    if tz.rule_start['month'] < tz.rule_end['month']:
        # Northern hemisphere: DST in [start, end) of the same calendar year
        if start_ep <= utc_ep < end_ep:
            return tz.dst_offset
        return tz.std_offset
    else:
        # Southern hemisphere: DST wraps the year boundary
        # DST active if: utc >= start(year) OR utc < end(year)
        if utc_ep >= start_ep or utc_ep < end_ep:
            return tz.dst_offset
        return tz.std_offset


def add_seconds(struct, secs):
    """Add seconds to a struct_time, carrying through days/hours.

    Pure field arithmetic — no system timezone involved.
    """
    total = _struct_to_epoch(struct) + secs
    year, month, day, hour, minute, second = _epoch_to_components(total)
    return time.struct_time((year, month, day, hour, minute, second, 0, -1, -1))


def utc_to_local(utc_struct, tz):
    """Convert a UTC struct_time to a local struct_time.

    Identity when tz is None (keeps existing tests green).
    """
    if tz is None:
        return utc_struct
    return add_seconds(utc_struct, offset_at(utc_struct, tz))
