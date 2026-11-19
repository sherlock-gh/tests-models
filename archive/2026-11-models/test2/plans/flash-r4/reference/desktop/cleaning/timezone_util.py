"""Local wall clock scheduling and elapsed instant arithmetic."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from .errors import bad

ZONE = ZoneInfo('America/Los_Angeles')
FMT = '%Y-%m-%dT%H:%M'


def day(value):
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
        return date.fromisoformat(value)
    except ValueError:
        bad('invalid date (expected YYYY-MM-DD)')


def clock(value):
    try:
        if not isinstance(value, str) or datetime.strptime(value, FMT).strftime(FMT) != value:
            raise ValueError()
        return datetime.strptime(value, FMT)
    except ValueError:
        bad('invalid time (expected YYYY-MM-DDTHH:MM)')


def instant(value):
    naive = clock(value) if isinstance(value, str) else value
    aware = naive.replace(tzinfo=ZONE, fold=0)
    # Nonexistent wall times advance to the first valid quarter-hour.
    if aware.astimezone(timezone.utc).astimezone(ZONE).replace(tzinfo=None) != naive:
        while True:
            naive += timedelta(minutes=1)
            if naive.minute % 15 == 0:
                aware = naive.replace(tzinfo=ZONE, fold=0)
                if aware.astimezone(timezone.utc).astimezone(ZONE).replace(tzinfo=None) == naive:
                    break
    return aware.astimezone(timezone.utc)


def text(value):
    return value.strftime(FMT)


def elapsed(start, end):
    return int((instant(end) - instant(start)).total_seconds() // 60)


def grid(on):
    base = datetime.combine(on, time(8))
    for index in range(36):
        yield base + timedelta(minutes=index * 15)
