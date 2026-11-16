"""Operations (contracts/operations.md, interfaces.md): each works on a copy and commits only on success."""
import copy
import re
from datetime import datetime

from . import rules
from .store import Store


class CleaningError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def err(code, message):
    raise CleaningError(code, message)


TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def _int(v, name):
    if not isinstance(v, int) or isinstance(v, bool):
        err("invalid_input", f"{name} must be an integer")
    return v


def _date(v, name):
    try:
        return rules.parse_date(v)
    except (TypeError, ValueError):
        err("invalid_input", f"{name} must be a date YYYY-MM-DD")


def _ts(v):
    if not isinstance(v, str) or not TS.match(v):
        err("invalid_input", "timestamp must be YYYY-MM-DDTHH:MM:SS")
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        err("invalid_input", "timestamp is not a real time")


def _name(v):
    if not isinstance(v, str) or not v.strip():
        err("invalid_input", "name is required")
    return v.strip()


class Service:
    def __init__(self, path):
        self.store = Store(path)
        self.state = self.store.load()

    # ---- plumbing
    def _run(self, fn, *args):
        s = copy.deepcopy(self.state)
        out = fn(s, *args)
        self.store.save(s)
        self.state = s
        return copy.deepcopy(out)

    def _read(self, fn, *args):
        return copy.deepcopy(fn(self.state, *args))

    @staticmethod
    def _new_id(s, kind):
        s["nextIds"][kind] += 1
        return s["nextIds"][kind]

    @staticmethod
    def _find(s, kind, id_):
        _int(id_, "id")
        for r in s[kind]:
            if r["id"] == id_:
                return r
        err("not_found", f"no {kind[:-1]} {id_}")

    # ---- cleaners
    def create_cleaner(self, name):
        def op(s):
            c = {"id": self._new_id(s, "cleaner"), "name": _name(name)}
            s["cleaners"].append(c)
            return c
        return self._run(op)

    def update_cleaner(self, id_, name):
        def op(s):
            c = self._find(s, "cleaners", id_)
            c["name"] = _name(name)
            return c
        return self._run(op)

    def get_cleaner(self, id_):
        return self._read(lambda s: self._find(s, "cleaners", id_))

    def list_cleaners(self):
        return self._read(lambda s: s["cleaners"])

    def delete_cleaner(self, id_):
        def op(s):
            c = self._find(s, "cleaners", id_)
            s["cleaners"].remove(c)
            mine = sorted((j for j in s["jobs"] if j["status"] == "booked" and id_ in j["cleanerIds"]),
                          key=lambda j: (j["date"], j["startMinute"]))
            for j in mine:
                self._rebook(s, j, rules.parse_date(j["requestedDate"]))
        return self._run(op)

    # ---- clients
    def create_client(self, name, address=None):
        def op(s):
            if address is not None and not isinstance(address, str):
                err("invalid_input", "address must be text")
            c = {"id": self._new_id(s, "client"), "name": _name(name), "address": address}
            s["clients"].append(c)
            return c
        return self._run(op)

    def update_client(self, id_, name, address=None):
        def op(s):
            c = self._find(s, "clients", id_)
            if address is not None and not isinstance(address, str):
                err("invalid_input", "address must be text")
            c["name"], c["address"] = _name(name), address
            return c
        return self._run(op)

    def get_client(self, id_):
        return self._read(lambda s: self._find(s, "clients", id_))

    def list_clients(self):
        return self._read(lambda s: s["clients"])

    def delete_client(self, id_):
        def op(s):
            c = self._find(s, "clients", id_)
            s["clients"].remove(c)
            for j in s["jobs"]:
                if j["clientId"] == id_ and j["status"] == "booked":
                    j["status"] = "cancelled"
        return self._run(op)

    # ---- jobs
    @staticmethod
    def _check_job(needed, length):
        _int(needed, "cleanersNeeded")
        _int(length, "lengthMinutes")
        if needed not in (1, 2, 3):
            err("invalid_input", "cleanersNeeded must be 1, 2 or 3")
        if not 0 < length <= rules.MAX_LENGTH:
            err("invalid_input", "lengthMinutes must be more than 0 and at most 540")

    def _place(self, s, job, requested, floor=None):
        ids = [c["id"] for c in s["cleaners"]]
        if job["cleanersNeeded"] > len(ids):
            err("unschedulable", f"job {job['id']} needs {job['cleanersNeeded']} cleaners; there are {len(ids)}")
        slot = rules.find_slot(s["jobs"], ids, job["cleanersNeeded"], job["lengthMinutes"], requested, floor, skip=job["id"])
        if not slot:
            err("unschedulable", f"no slot for job {job['id']}")
        job["date"], job["startMinute"], job["cleanerIds"] = slot[0], slot[1], slot[2]
        job["endMinute"] = slot[1] + job["lengthMinutes"]
        job["timeEntries"] = [{"cleanerId": c, "arrivedAt": None, "departedAt": None, "secondsWorked": None} for c in slot[2]]

    def _rebook(self, s, job, requested, floor=None):
        job["cleanerIds"] = []
        self._place(s, job, requested, floor)

    def book_job(self, client_id, needed, length, requested_date):
        def op(s):
            self._find(s, "clients", _int(client_id, "clientId"))
            self._check_job(needed, length)
            req = _date(requested_date, "requestedDate")
            job = {"id": self._new_id(s, "job"), "clientId": client_id, "cleanersNeeded": needed,
                   "lengthMinutes": length, "requestedDate": requested_date, "status": "booked", "cleanerIds": []}
            self._place(s, job, req)
            s["jobs"].append(job)
            return job
        return self._run(op)

    def update_job(self, id_, client_id=None, needed=None, length=None, requested_date=None):
        def op(s):
            j = self._find(s, "jobs", id_)
            if j["status"] != "booked":
                err("invalid_state", f"job {id_} has started or ended")
            if client_id is not None:
                self._find(s, "clients", _int(client_id, "clientId"))
                j["clientId"] = client_id
            n = j["cleanersNeeded"] if needed is None else needed
            L = j["lengthMinutes"] if length is None else length
            self._check_job(n, L)
            if requested_date is not None:
                _date(requested_date, "requestedDate")
                j["requestedDate"] = requested_date
            j["cleanersNeeded"], j["lengthMinutes"] = n, L
            self._rebook(s, j, rules.parse_date(j["requestedDate"]))
            return j
        return self._run(op)

    def delete_job(self, id_):
        def op(s):
            j = self._find(s, "jobs", id_)
            if j["status"] != "booked":
                err("invalid_state", f"job {id_} has started or ended")
            s["jobs"].remove(j)
        return self._run(op)

    def get_job(self, id_):
        return self._read(lambda s: self._find(s, "jobs", id_))

    def list_jobs(self):
        return self._read(lambda s: s["jobs"])

    def cleaner_day(self, cleaner_id, day):
        def op(s):
            self._find(s, "cleaners", cleaner_id)
            _date(day, "date")
            return sorted((j for j in s["jobs"] if j["date"] == day and cleaner_id in j["cleanerIds"] and j["status"] != "cancelled"),
                          key=lambda j: j["startMinute"])
        return self._read(op)

    # ---- field
    def _entry(self, s, job_id, cleaner_id):
        j = self._find(s, "jobs", job_id)
        _int(cleaner_id, "cleanerId")
        if j["status"] in ("complete", "cancelled"):
            err("invalid_state", f"job {job_id} is {j['status']}")
        for e in j["timeEntries"]:
            if e["cleanerId"] == cleaner_id:
                return j, e
        err("invalid_input", f"cleaner {cleaner_id} is not assigned to job {job_id}")

    def arrive(self, job_id, cleaner_id, ts):
        def op(s):
            j, e = self._entry(s, job_id, cleaner_id)
            _ts(ts)
            if e["arrivedAt"]:
                err("invalid_state", "already arrived")
            e["arrivedAt"] = ts
            j["status"] = "in_progress"
            return j
        return self._run(op)

    def depart(self, job_id, cleaner_id, ts):
        def op(s):
            j, e = self._entry(s, job_id, cleaner_id)
            t = _ts(ts)
            if not e["arrivedAt"]:
                err("invalid_state", "has not arrived")
            if e["departedAt"]:
                err("invalid_state", "already departed")
            secs = int((t - datetime.fromisoformat(e["arrivedAt"])).total_seconds())
            if secs < 0:
                err("invalid_input", "departure is before arrival")
            e["departedAt"], e["secondsWorked"] = ts, secs
            if all(x["departedAt"] for x in j["timeEntries"]):
                j["status"] = "complete"
                names = {c["id"]: c["name"] for c in s["cleaners"]}
                client = next((c["name"] for c in s["clients"] if c["id"] == j["clientId"]), "")
                lines = [{"cleanerId": x["cleanerId"], "cleanerName": names.get(x["cleanerId"], ""),
                          "secondsWorked": x["secondsWorked"], "chargeCents": rules.charge_cents(x["secondsWorked"])}
                         for x in sorted(j["timeEntries"], key=lambda x: x["cleanerId"])]
                s["invoices"].append({"id": self._new_id(s, "invoice"), "jobId": j["id"], "clientName": client,
                                      "lines": lines, "totalCents": sum(x["chargeCents"] for x in lines), "settled": False})
            return j
        return self._run(op)

    def request_extension(self, job_id, cleaner_id, minutes):
        def op(s):
            j, _ = self._entry(s, job_id, cleaner_id)
            _int(minutes, "minutes")
            if minutes <= 0 or minutes % 20:
                err("invalid_input", "minutes must be a positive multiple of 20")
            j["endMinute"] += minutes
            floor = j["endMinute"] + rules.GAP
            bumped = sorted((k for k in s["jobs"] if k["id"] != j["id"] and k["status"] == "booked" and k["date"] == j["date"]
                             and set(k["cleanerIds"]) & set(j["cleanerIds"]) and k["startMinute"] >= j["startMinute"]
                             and k["startMinute"] < floor), key=lambda k: k["startMinute"])
            for k in bumped:
                k["cleanerIds"] = []          # all bumped jobs leave the schedule before any is placed again
            for k in bumped:
                self._place(s, k, rules.parse_date(k["date"]), (j["date"], floor))
            return j
        return self._run(op)

    # ---- invoices
    def list_invoices(self, settled=None):
        return self._read(lambda s: [i for i in s["invoices"] if settled is None or i["settled"] == settled])

    def get_invoice(self, id_):
        return self._read(lambda s: self._find(s, "invoices", id_))

    def pay_invoice(self, id_, amount):
        def op(s):
            i = self._find(s, "invoices", id_)
            _int(amount, "amountCents")
            if i["settled"]:
                err("invalid_state", f"invoice {id_} is settled already")
            if amount != i["totalCents"]:
                err("payment_mismatch", f"payment must be exactly {i['totalCents']} cents")
            i["settled"] = True
            s["payments"].append({"invoiceId": id_, "amountCents": amount, "paidAt": datetime.now().isoformat(timespec="seconds")})
            return i
        return self._run(op)

    # ---- utilization
    def utilization(self, day):
        d = _date(day, "date")
        mon, sun = rules.week_bounds(d)

        def op(s):
            out = []
            for c in s["cleaners"]:
                ds = ws = 0
                for j in s["jobs"]:
                    for e in j.get("timeEntries", []):
                        if e["cleanerId"] == c["id"] and e["secondsWorked"] is not None:
                            a = datetime.fromisoformat(e["arrivedAt"]).date()
                            ds += e["secondsWorked"] if a == d else 0
                            ws += e["secondsWorked"] if mon <= a <= sun else 0
                out.append({"cleanerId": c["id"], "date": day, "daySeconds": ds, "weekSeconds": ws,
                            "dayPercent": ds / 28800 * 100, "weekPercent": ws / 144000 * 100})
            return out
        return self._read(op)
