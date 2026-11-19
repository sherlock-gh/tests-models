"""JSON record shapes; services use dictionaries of these exact fields."""
from dataclasses import dataclass, asdict
from typing import Optional


class Record:
    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        return cls(**value)


@dataclass
class Cleaner(Record):
    id: int
    name: str
    phone: str
    email: str
    active: bool = True


@dataclass
class Client(Record):
    id: int
    name: str
    address: str
    phone: str


@dataclass
class Assignment(Record):
    cleaner_id: int
    arrive: Optional[str] = None
    depart: Optional[str] = None
    extended_minutes: int = 0


@dataclass
class JobPart(Record):
    part_index: int
    day: str
    start: str
    end: str
    assignments: list


@dataclass
class Job(Record):
    id: int
    client_id: int
    cleaners_needed: int
    expected_length_hours: float
    requested_day: str
    status: str
    parts: list
    invoice_id: Optional[int] = None


@dataclass
class InvoiceLine(Record):
    cleaner_id: int
    cleaner_name: str
    minutes_worked: int
    amount_cents: int


@dataclass
class Payment(Record):
    amount_cents: int
    paid_at: str


@dataclass
class Invoice(Record):
    id: int
    job_id: int
    issued_at: str
    lines: list
    total_cents: int
    settled: bool = False
    payment: Optional[dict] = None


def worked_minutes(job, cleaner_id):
    from .timezone_util import elapsed
    return sum(elapsed(a['arrive'], a['depart']) for p in job['parts']
               for a in p['assignments'] if a['cleaner_id'] == cleaner_id
               and a['arrive'] is not None and a['depart'] is not None)
