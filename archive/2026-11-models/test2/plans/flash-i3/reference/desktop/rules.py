"""The back office's rules (the plan's rules-core.md), over the store's plain document.
Times are naive local datetimes; parts keep their day and minutes since midnight."""
from datetime import date, datetime, timedelta

DAY_START, DAY_END = 480, 1020   # 8:00, 17:00
PART = 480                       # 8 hours
gap = 60                         # the shadow, minutes
RATE = 4500                      # cents an hour
SEARCH_DAYS = 90
NO_SLOT = "No slot for this job within 90 days of the requested day."
FMT = "%Y-%m-%dT%H:%M"


class RuleError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


def parse_day(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        raise RuleError(f"not a date (YYYY-MM-DD): {s!r}")


def parse_instant(s):
    try:
        return datetime.strptime(s, FMT)
    except (TypeError, ValueError):
        raise RuleError(f"not a time (YYYY-MM-DDTHH:MM): {s!r}")


def fmt(dt):
    return dt.strftime(FMT)


def part_span(p):
    d = date.fromisoformat(p["start_day"])
    base = datetime(d.year, d.month, d.day)
    return base + timedelta(minutes=p["start_min"]), base + timedelta(minutes=p["end_min"])


def clashes(a, b):
    """two spans for one cleaner clash when either starts less than an hour after the other ends"""
    return a[0] < b[1] + timedelta(minutes=gap) and b[0] < a[1] + timedelta(minutes=gap)


def find(doc, kind, rid):
    for r in doc[kind]:
        if r["id"] == rid:
            return r
    raise RuleError(f"no {kind[:-1]} {rid}", 404)


def next_id(doc, kind):
    doc["seq"][kind] = doc["seq"].get(kind, 0) + 1
    return doc["seq"][kind]


def busy(doc, cleaner, skip=None):
    out = []
    for j in doc["jobs"]:
        if j["status"] != "cancelled" and j["id"] != skip and cleaner in j["cleaner_ids"]:
            out += [part_span(p) for p in j["parts"]]
    return out


def lengths(total):
    if total <= PART:
        return [total]
    return [PART] * (total // PART) + ([total % PART] if total % PART else [])


def workdays_from(d):
    while True:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def candidates(first, total, floor):
    """(parts) placements for a job starting on day `first`, earliest first"""
    ls = lengths(total)
    if first.weekday() >= 5:
        return
    if len(ls) == 1:
        for s in range(DAY_START, DAY_END - ls[0] + 1, 15):
            p = {"start_day": first.isoformat(), "start_min": s, "end_min": s + ls[0]}
            if floor is None or part_span(p)[0] >= floor:
                yield [p]
        return
    days, it = [], workdays_from(first)
    for _ in ls:
        days.append(next(it))
    parts = [{"start_day": d.isoformat(), "start_min": DAY_START, "end_min": DAY_START + n} for d, n in zip(days, ls)]
    if floor is None or part_span(parts[0])[0] >= floor:
        yield parts


def place(doc, job, floor=None, crew=None):
    """the earliest placement of `job` from its requested day (and `floor`), with `crew` or any
    free cleaners in id order; sets its parts and cleaners, or raises NO_SLOT"""
    need, total = job["cleaners_needed"], job["expected_length_min"]
    start = date.fromisoformat(job["requested_day"])
    if floor is not None and floor.date() > start:
        start = floor.date()
    pool = crew if crew is not None else sorted(c["id"] for c in doc["cleaners"])
    books = {c: busy(doc, c, skip=job["id"]) for c in pool}
    for k in range(SEARCH_DAYS + 1):
        for parts in candidates(start + timedelta(days=k), total, floor):
            spans = [part_span(p) for p in parts]
            free = [c for c in pool if not any(clashes(s, b) for s in spans for b in books[c])]
            if len(free) >= need:
                job["parts"], job["cleaner_ids"] = parts, free[:need]
                return job
    raise RuleError(NO_SLOT)


def check_booking_fields(body):
    n, length = body.get("cleaners_needed"), body.get("expected_length_min")
    if type(n) is not int or not 1 <= n <= 3:
        raise RuleError("cleaners_needed must be 1, 2 or 3")
    if type(length) is not int or length <= 0:
        raise RuleError("expected_length_min must be a whole number of minutes above 0")
    return n, length, parse_day(body.get("requested_day")).isoformat()


def book(doc, body):
    n, length, day = check_booking_fields(body)
    cid = body.get("client_id")
    if type(cid) is not int:
        raise RuleError("client_id must be a number")
    find(doc, "clients", cid)
    job = {"id": 0, "client_id": cid, "cleaners_needed": n, "expected_length_min": length,
           "requested_day": day, "cleaner_ids": [], "status": "booked", "parts": [], "invoice_id": None, "taps": []}
    place(doc, job)
    job["id"] = next_id(doc, "jobs")
    doc["jobs"].append(job)
    return job


def update_job(doc, jid, body):
    job = find(doc, "jobs", jid)
    if job["status"] != "booked":
        raise RuleError("only a job nobody has arrived on can be changed")
    merged = {"cleaners_needed": job["cleaners_needed"], "expected_length_min": job["expected_length_min"],
              "requested_day": job["requested_day"], **{k: v for k, v in body.items() if k in ("expected_length_min", "requested_day")}}
    _, length, day = check_booking_fields(merged)
    job["expected_length_min"], job["requested_day"] = length, day
    return place(doc, job)


def delete_job(doc, jid):
    job = find(doc, "jobs", jid)
    if job["invoice_id"] is not None:
        raise RuleError("job's invoice has been issued")
    doc["jobs"].remove(job)


def delete_cleaner(doc, cid):
    find(doc, "cleaners", cid)
    doc["cleaners"] = [c for c in doc["cleaners"] if c["id"] != cid]
    for j in doc["jobs"]:
        if cid not in j["cleaner_ids"]:
            continue
        if j["status"] == "booked":
            place(doc, j)
        elif j["status"] == "in_progress":
            j["cleaner_ids"] = [c for c in j["cleaner_ids"] if c != cid]
            j["taps"] = [t for t in j["taps"] if t["cleaner_id"] != cid]
            maybe_complete(doc, j, None)


def delete_client(doc, cid):
    find(doc, "clients", cid)
    doc["clients"] = [c for c in doc["clients"] if c["id"] != cid]
    for j in doc["jobs"]:
        if j["client_id"] == cid and j["status"] == "booked":
            j["status"] = "cancelled"


# --- taps, invoices, settlement ---

def taps_of(job, cleaner):
    return [t for t in job["taps"] if t["cleaner_id"] == cleaner]


def tap_target(doc, jid, body):
    job = find(doc, "jobs", jid)
    cid = body.get("cleaner_id")
    if type(cid) is not int:
        raise RuleError("cleaner_id must be a number")
    if cid not in job["cleaner_ids"]:
        raise RuleError(f"cleaner {cid} is not on job {jid}")
    if job["status"] not in ("booked", "in_progress"):
        raise RuleError(f"job {jid} is {job['status']}")
    at = body.get("at")
    when = parse_instant(at) if at is not None else datetime.now().replace(second=0, microsecond=0)
    return job, cid, when


def arrive(doc, jid, body):
    job, cid, when = tap_target(doc, jid, body)
    mine = taps_of(job, cid)
    if mine and mine[-1]["kind"] == "arrive":
        raise RuleError("already arrived: tap Depart first")
    if sum(t["kind"] == "depart" for t in mine) >= len(job["parts"]):
        raise RuleError("this cleaner has finished the job")
    job["taps"].append({"cleaner_id": cid, "kind": "arrive", "instant": fmt(when)})
    job["status"] = "in_progress"
    return job


def depart(doc, jid, body):
    job, cid, when = tap_target(doc, jid, body)
    mine = taps_of(job, cid)
    if not mine or mine[-1]["kind"] != "arrive":
        raise RuleError("no Arrive to depart from")
    if when < parse_instant(mine[-1]["instant"]):
        raise RuleError("Depart is before the Arrive")
    job["taps"].append({"cleaner_id": cid, "kind": "depart", "instant": fmt(when)})
    return job, maybe_complete(doc, job, when)


def minutes_of(job, cleaner):
    mine, total = taps_of(job, cleaner), 0
    for a, d in zip(mine[::2], mine[1::2]):
        total += int((parse_instant(d["instant"]) - parse_instant(a["instant"])).total_seconds() // 60)
    return total


def line_cents(minutes):
    return (minutes * RATE + 30) // 60


def maybe_complete(doc, job, when):
    n = len(job["parts"])
    if not job["cleaner_ids"]:
        return None
    for c in job["cleaner_ids"]:
        mine = taps_of(job, c)
        if sum(t["kind"] == "depart" for t in mine) < n or mine[-1]["kind"] != "depart":
            return None
    if when is None:
        when = max(parse_instant(t["instant"]) for t in job["taps"])
    lines = [{"cleaner_id": c, "minutes_worked": minutes_of(job, c)} for c in job["cleaner_ids"]]
    for l in lines:
        l["cents"] = line_cents(l["minutes_worked"])
    inv = {"id": next_id(doc, "invoices"), "job_id": job["id"], "issued_at": fmt(when), "lines": lines,
           "total_cents": sum(l["cents"] for l in lines)}
    doc["invoices"].append(inv)
    job["status"], job["invoice_id"] = "complete", inv["id"]
    return inv


def settled(doc, inv):
    return any(p["invoice_id"] == inv["id"] for p in doc["payments"])


def pay(doc, iid, body):
    inv = find(doc, "invoices", iid)
    amount = body.get("amount_cents")
    if settled(doc, inv):
        raise RuleError("this invoice is already settled")
    if type(amount) is not int or amount != inv["total_cents"]:
        raise RuleError(f"an invoice is paid in full in one payment: {inv['total_cents']} cents")
    doc["payments"].append({"id": next_id(doc, "payments"), "invoice_id": iid, "amount_cents": amount,
                            "paid_at": fmt(datetime.now())})
    return inv


# --- more time ---

def more_time(doc, jid, body):
    job = find(doc, "jobs", jid)
    cid = body.get("cleaner_id")
    if type(cid) is not int or cid not in job["cleaner_ids"]:
        raise RuleError(f"cleaner {cid} is not on job {jid}")
    mine = taps_of(job, cid)
    if job["status"] != "in_progress" or not mine or mine[-1]["kind"] != "arrive":
        raise RuleError("more time is for a cleaner who has arrived and not departed")
    k = sum(t["kind"] == "depart" for t in mine)
    part = job["parts"][min(k, len(job["parts"]) - 1)]
    part["end_min"] += 20
    new_end = part_span(part)[1]
    floor = new_end + timedelta(minutes=gap)
    moved = []
    while True:
        spans = [part_span(p) for p in job["parts"]]
        hit = None
        for j in sorted(doc["jobs"], key=lambda j: part_span(j["parts"][0])[0]):
            if j["id"] == job["id"] or j["status"] != "booked" or not set(j["cleaner_ids"]) & set(job["cleaner_ids"]):
                continue
            if any(clashes(s, part_span(p)) for s in spans for p in j["parts"]):
                hit = j
                break
        if hit is None:
            break
        place(doc, hit, floor=floor, crew=list(hit["cleaner_ids"]))
        moved.append(hit["id"])
    return job, moved


# --- utilization ---

def worked_on(job, cleaner, day):
    lo = datetime(day.year, day.month, day.day)
    hi = lo + timedelta(days=1)
    mine, total = taps_of(job, cleaner), 0
    for a, d in zip(mine[::2], mine[1::2]):
        s, e = max(parse_instant(a["instant"]), lo), min(parse_instant(d["instant"]), hi)
        if e > s:
            total += int((e - s).total_seconds() // 60)
    return total


def utilization(doc, days, hours_of):
    out = []
    for c in sorted(doc["cleaners"], key=lambda c: c["id"]):
        m = sum(worked_on(j, c["id"], d) for j in doc["jobs"] for d in days)
        out.append({"cleaner_id": c["id"], "cleaner_name": c["name"], "hours_worked": m / 60, "hours_of": hours_of})
    return out
