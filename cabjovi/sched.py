# Copyright © 2026 Philippe Proulx <eepp.ca>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import dataclasses
import datetime
import re

_DAY_TO_NUM = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}
_DIR_NAME_PATTERN = re.compile(r'^(mon|tue|wed|thu|fri|sat|sun)-(\d{1,2}):(mon|tue|wed|thu|fri|sat|sun)-(\d{1,2})$')


@dataclasses.dataclass(frozen=True)
class _TimeRange:
    start_day: int
    start_hour: int
    end_day: int
    end_hour: int


# Parses directory name into a `_TimeRange` instance.
#
# Returns `None` if the name doesn't match the expected pattern.
def _parse_dir_name(name):
    match = _DIR_NAME_PATTERN.match(name.lower())

    if not match:
        return

    start_day_str, start_hour_str, end_day_str, end_hour_str = match.groups()
    start_hour = int(start_hour_str)
    end_hour = int(end_hour_str)

    if not (0 <= start_hour < 24) or not (0 <= end_hour < 24):
        return

    return _TimeRange(_DAY_TO_NUM[start_day_str], start_hour,
                      _DAY_TO_NUM[end_day_str], end_hour)


# Checks if current time `now_day`/`now_hour` falls within the given
# range `time_range`. Handles ranges that wrap around the week (for
# example, Friday to Monday).
def _time_in_range(now_day, now_hour, time_range):
    # Convert to hours since start of week
    now_week_hour = now_day * 24 + now_hour
    start_week_hour = time_range.start_day * 24 + time_range.start_hour
    end_week_hour = time_range.end_day * 24 + time_range.end_hour

    if start_week_hour <= end_week_hour:
        # Normal range (for example, Monday 8:00 to Monday 17:00)
        return start_week_hour <= now_week_hour < end_week_hour
    else:
        # Wrapping range (for example, Friday 18:00 to Monday 6:00)
        return now_week_hour >= start_week_hour or now_week_hour < end_week_hour


# Finds the first directory in `base_dir` matching the current time.
#
# Returns `None` if no directory matches.
def get_cur_dir(base_dir):
    now = datetime.datetime.now()

    if not base_dir.is_dir():
        return

    for entry in base_dir.iterdir():
        if not entry.is_dir():
            continue

        time_range = _parse_dir_name(entry.name)

        if time_range is None:
            continue

        if _time_in_range(now.weekday(), now.hour, time_range):
            return entry
