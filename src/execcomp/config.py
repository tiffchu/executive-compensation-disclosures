from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class RunConfig:
    target_year: int
    started_local: str

    @classmethod
    def start(cls, now=None):
        now = now or datetime.now().astimezone()
        return cls(now.year - 1, now.isoformat())

def target_period(fiscal_end, year):
    return date.fromisoformat(fiscal_end).year == year
