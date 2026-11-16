"""Pure rules (research D3–D6, D10): booking, overlap, charges, utilization. Times are minutes from midnight."""
from datetime import date, timedelta

DAY_START, DAY_END, GAP, MAX_LENGTH = 480, 1020, 60, 540
SEARCH_DAYS = 366


def parse_date(s):
    return date.fromisoformat(s)


def first_weekday(d):
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def live(job):
    return job["status"] != "cancelled"


def free(jobs, cleaner_id, day, start, end, skip=None):
    """The cleaner has no live job that day within GAP of [start, end)."""
    for j in jobs:
        if j["id"] == skip or not live(j) or j["date"] != day or cleaner_id not in j["cleanerIds"]:
            continue
        if not (j["endMinute"] + GAP <= start or j["startMinute"] >= end + GAP):
            return False
    return True


def find_slot(jobs, cleaner_ids, needed, length, requested, floor=None, skip=None):
    """Earliest (date, start, cleaners) on or after `requested` (a date); `floor` (date, minute) bounds it
    from below on its own day. Lowest-id free cleaners. None when nothing within SEARCH_DAYS."""
    if needed > len(cleaner_ids):
        return None
    d = first_weekday(requested)
    for _ in range(SEARCH_DAYS):
        day = d.isoformat()
        lo = floor[1] if floor and floor[0] == day else DAY_START
        cands = {DAY_START, lo} | {j["endMinute"] + GAP for j in jobs
                                   if j["id"] != skip and live(j) and j["date"] == day}
        for s in sorted(c for c in cands if c >= lo and c >= DAY_START):
            if s + length > DAY_END:
                break
            ok = [c for c in sorted(cleaner_ids) if free(jobs, c, day, s, s + length, skip)]
            if len(ok) >= needed:
                return day, s, ok[:needed]
        d = first_weekday(d + timedelta(days=1))
    return None


def charge_cents(seconds):
    return (seconds * 5 + 2) // 4


def week_bounds(d):
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)
