"""Tap-to-tap utilization split at local midnight."""
from collections import defaultdict
from datetime import datetime, time, timedelta
from .store import get
from .timezone_util import ZONE, day, instant


def utilization(state, cid, start, end):
    get(state, 'cleaners', cid)
    first, last = day(start), day(end)
    if last < first:
        from .errors import bad
        bad('from must precede to')
    days = defaultdict(int)
    for job in state['jobs']:
        for part in job['parts']:
            for assignment in part['assignments']:
                if assignment['cleaner_id'] != cid or not assignment['arrive'] or not assignment['depart']:
                    continue
                cursor, finish = instant(assignment['arrive']), instant(assignment['depart'])
                while cursor < finish:
                    local_day = cursor.astimezone(ZONE).date()
                    midnight = datetime.combine(local_day + timedelta(days=1), time(), tzinfo=ZONE).astimezone(cursor.tzinfo)
                    segment = min(midnight, finish)
                    if first <= local_day <= last:
                        days[local_day] += int((segment - cursor).total_seconds() // 60)
                    cursor = segment
    weeks = defaultdict(int)
    for on, minutes in days.items():
        weeks[on - timedelta(days=on.weekday())] += minutes
    return {'days': [{'cleaner_id': cid, 'date': on.isoformat(), 'minutes': minutes, 'of': 480}
                     for on, minutes in sorted(days.items())],
            'weeks': [{'cleaner_id': cid, 'week_start': on.isoformat(), 'minutes': minutes, 'of': 2400}
                      for on, minutes in sorted(weeks.items())]}
