"""Flash-Next's plan, the rules (research D-3..D-9, data-model.md): every operation works on a copy of
the store and is saved only if it succeeds. Times are local minutes; money is Decimal."""
import copy
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DAY_START, DAY_END, GAP, MAX_MIN, HORIZON = 480, 1020, 60, 540, 52
FMT = "%Y-%m-%dT%H:%M"


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def at(day, minute):
    return (datetime.combine(day, datetime.min.time()) + timedelta(minutes=minute)).strftime(FMT)


def parse_dt(s):
    try:
        return datetime.strptime(s, FMT)
    except (TypeError, ValueError):
        raise Refused("invalid_input", f"{s!r} is not a time YYYY-MM-DDTHH:MM")


def parse_day(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        raise Refused("invalid_input", f"{s!r} is not a day YYYY-MM-DD")


def to_int(v, what):
    try:
        return int(str(v))
    except (TypeError, ValueError):
        raise Refused("invalid_input", f"{what} must be a whole number")


def money(d):
    return f"{d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"


class Store:
    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            with open(path) as f:
                self.s = json.load(f)
        else:
            self.s = {"next": {}, "cleaners": [], "clients": [], "jobs": [], "invoices": []}

    def run(self, fn, *args):
        s = copy.deepcopy(self.s)
        out = fn(s, *args)
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d)
        with os.fdopen(fd, "w") as f:
            json.dump(s, f)
        os.replace(tmp, self.path)
        self.s = s
        return copy.deepcopy(out)

    def read(self, fn, *args):
        return copy.deepcopy(fn(self.s, *args))


def new_id(s, kind):
    s["next"][kind] = s["next"].get(kind, 0) + 1
    return s["next"][kind]


def find(s, kind, i):
    i = to_int(i, "id")
    for r in s[kind]:
        if r["id"] == i:
            return r
    raise Refused("not_found", f"no {kind[:-1]} {i}")


def name_of(v):
    if not isinstance(v, str) or not v.strip():
        raise Refused("invalid_input", "a name is required")
    return v.strip()


# ---- records
def add_person(s, kind, name):
    r = {"id": new_id(s, kind), "name": name_of(name)}
    s[kind].append(r)
    return r


def update_person(s, kind, i, name):
    r = find(s, kind, i)
    r["name"] = name_of(name)
    return r


def day_min(dt):
    d = datetime.strptime(dt, FMT)
    return d.date(), d.hour * 60 + d.minute


# ---- booking (D-3)
def free(s, cleaner, day, start, end, skip):
    for j in s["jobs"]:
        if j["id"] == skip or j["state"] != "scheduled" or cleaner not in [a["cleaner_id"] for a in j["assignments"]]:
            continue
        jd, js = day_min(j["booked_start"])
        _, je = day_min(j["booked_end"])
        if jd != day:
            continue
        if start < je + GAP and js < end + GAP:
            return False
    return True


def place(s, job, from_day, floor=None):
    """Earliest slot on or after from_day (floor: (day, minute), a lower bound on its own day)."""
    ids = sorted(c["id"] for c in s["cleaners"])
    n, L = job["cleaners_required"], job["expected_length_min"]
    if n > len(ids):
        raise Refused("no_feasible_slot", f"needs {n} cleaners; there are {len(ids)}")
    d, seen = from_day, 0
    while seen < HORIZON:
        if d.weekday() < 5:
            seen += 1
            lo = max(DAY_START, floor[1]) if floor and floor[0] == d else DAY_START
            for start in range(lo, DAY_END - L + 1):
                ok = [c for c in ids if free(s, c, d, start, start + L, job["id"])]
                if len(ok) >= n:
                    job["booked_start"], job["booked_end"] = at(d, start), at(d, start + L)
                    job["assignments"] = [{"cleaner_id": c, "arrival": None, "departure": None, "worked_min": None} for c in ok[:n]]
                    return
        d += timedelta(days=1)
    raise Refused("no_feasible_slot", f"no slot for job {job['id']} within {HORIZON} workdays")


def job_fields(s, client_id, required, hours):
    find(s, "clients", client_id)
    n = to_int(required, "cleaners_required")
    if n not in (1, 2, 3):
        raise Refused("invalid_input", "cleaners_required must be 1, 2 or 3")
    try:
        mins = int((Decimal(str(hours)) * 60).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        raise Refused("invalid_input", "hours must be a number")
    if mins <= 0:
        raise Refused("invalid_input", "hours must be more than 0")
    if mins > MAX_MIN:
        raise Refused("job_too_long", "a job may not be longer than 9 hours")
    return to_int(client_id, "client_id"), n, mins


def book(s, client_id, required, hours, requested_day):
    c, n, mins = job_fields(s, client_id, required, hours)
    day = parse_day(requested_day)
    job = {"id": new_id(s, "jobs"), "client_id": c, "requested_day": requested_day, "expected_length_min": mins,
           "cleaners_required": n, "state": "scheduled", "assignments": [], "invoice_id": None}
    place(s, job, day)
    s["jobs"].append(job)
    return job


def edit_job(s, i, client_id, required, hours):
    j = find(s, "jobs", i)
    if j["state"] != "scheduled":
        raise Refused("invalid_input", f"job {i} has started or ended")
    c, n, mins = job_fields(s, client_id if client_id is not None else j["client_id"],
                            required if required is not None else j["cleaners_required"],
                            hours if hours is not None else Decimal(j["expected_length_min"]) / 60)
    j["client_id"], j["cleaners_required"], j["expected_length_min"] = c, n, mins
    j["assignments"] = []
    place(s, j, parse_day(j["requested_day"]))
    return j


def delete_job(s, i):
    s["jobs"].remove(find(s, "jobs", i))
    return {}


# ---- removals (D-5)
def delete_cleaner(s, i):
    c = find(s, "cleaners", i)
    s["cleaners"].remove(c)
    mine = sorted((j for j in s["jobs"] if j["state"] == "scheduled" and c["id"] in [a["cleaner_id"] for a in j["assignments"]]),
                  key=lambda j: j["booked_start"])
    for j in mine:
        d, m = day_min(j["booked_start"])
        j["assignments"] = []
        try:
            place(s, j, d, (d, m))
        except Refused:
            raise Refused("not_enough_cleaners", f"job {j['id']} could not be rebooked without cleaner {i}")
    return {}


def delete_client(s, i):
    c = find(s, "clients", i)
    s["clients"].remove(c)
    for j in s["jobs"]:
        if j["client_id"] == c["id"] and j["state"] == "scheduled":
            j["state"] = "cancelled"
    return {}


# ---- field (D-6)
def assignment(s, job_id, cleaner_id):
    j = find(s, "jobs", job_id)
    cid = to_int(cleaner_id, "cleaner_id")
    find(s, "cleaners", cid)
    for a in j["assignments"]:
        if a["cleaner_id"] == cid:
            return j, a
    raise Refused("wrong_cleaner", f"cleaner {cid} is not on job {j['id']}")


def arrive(s, cleaner_id, job_id, when):
    j, a = assignment(s, job_id, cleaner_id)
    parse_dt(when)
    if j["state"] not in ("scheduled", "in_progress") or a["arrival"]:
        raise Refused("tap_out_of_order", "this cleaner can't arrive at this job now")
    a["arrival"], j["state"] = when, "in_progress"
    return j


def depart(s, cleaner_id, job_id, when):
    j, a = assignment(s, job_id, cleaner_id)
    t = parse_dt(when)
    if not a["arrival"] or a["departure"]:
        raise Refused("tap_out_of_order", "this cleaner can't depart from this job now")
    mins = int((t - parse_dt(a["arrival"])).total_seconds() // 60)
    if mins < 0:
        raise Refused("tap_out_of_order", "departure before arrival")
    a["departure"], a["worked_min"] = when, mins
    if all(x["departure"] for x in j["assignments"]):
        lines = [{"cleaner_id": x["cleaner_id"], "worked_min": x["worked_min"],
                  "amount": money(Decimal(x["worked_min"]) / 60 * 45)} for x in sorted(j["assignments"], key=lambda x: x["cleaner_id"])]
        inv = {"id": new_id(s, "invoices"), "job_id": j["id"], "issued_at": when, "lines": lines,
               "total": money(sum(Decimal(x["amount"]) for x in lines)), "settled": False, "payment_amount": None, "payment_date": None}
        s["invoices"].append(inv)
        j["state"], j["invoice_id"] = "complete", inv["id"]
    return j


def extend(s, cleaner_id, job_id):
    j, _ = assignment(s, job_id, cleaner_id)
    if j["state"] in ("complete", "cancelled"):
        raise Refused("tap_out_of_order", f"job {j['id']} is {j['state']}")
    d, end = day_min(j["booked_end"])
    end += 20
    j["booked_end"] = at(d, end)
    floor = end + GAP
    cid = to_int(cleaner_id, "cleaner_id")
    bumped = sorted((k for k in s["jobs"] if k["id"] != j["id"] and k["state"] == "scheduled"
                     and cid in [a["cleaner_id"] for a in k["assignments"]]
                     and day_min(k["booked_start"])[0] == d and day_min(k["booked_start"])[1] < floor
                     and k["booked_start"] >= j["booked_start"]), key=lambda k: k["booked_start"])
    for k in bumped:
        k["assignments"] = []
    for k in bumped:
        place(s, k, d, (d, floor))
    return j


# ---- invoices (D-7)
def pay(s, i, amount, when):
    inv = find(s, "invoices", i)
    if inv["settled"]:
        raise Refused("already_settled", f"invoice {i} is settled")
    try:
        a = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        raise Refused("invalid_input", "amount must be a number")
    if a != Decimal(inv["total"]):
        raise Refused("payment_amount_mismatch", f"the payment must be exactly {inv['total']}")
    inv["settled"], inv["payment_amount"], inv["payment_date"] = True, money(a), when
    return inv


# ---- utilization (D-8)
def utilization(s, day):
    d = parse_day(day)
    mon = d - timedelta(days=d.weekday())
    out = []
    for c in s["cleaners"]:
        dm = wm = 0
        for j in s["jobs"]:
            for a in j["assignments"]:
                if a["cleaner_id"] == c["id"] and a["departure"]:
                    dd = parse_dt(a["departure"]).date()
                    dm += a["worked_min"] if dd == d else 0
                    wm += a["worked_min"] if mon <= dd <= mon + timedelta(days=6) else 0
        out.append({"cleaner_id": c["id"], "day_worked_min": dm, "week_worked_min": wm})
    return out


def cleaner_day(s, cleaner_id, day):
    c = find(s, "cleaners", cleaner_id)
    d = parse_day(day)
    js = [j for j in s["jobs"] if j["state"] != "cancelled" and day_min(j["booked_start"])[0] == d
          and c["id"] in [a["cleaner_id"] for a in j["assignments"]]]
    return sorted(js, key=lambda j: j["booked_start"])
