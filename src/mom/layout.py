"""Pure layout: text -> Canvas with fit validation."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Canvas:
    year: int
    cells: list[tuple[date, int]]
    width_cols: int
    grid_start: date
    usable_week_indices: list[int]
    intensity: int
    text: str


@dataclass(frozen=True)
class Fit:
    ok: bool
    required: int
    available: int
    year: int


def _sunday_on_or_before(d: date) -> date:
    # date.weekday(): Mon=0 .. Sun=6. We want: Sun=0. So (weekday + 1) % 7.
    sunday_offset = (d.weekday() + 1) % 7
    return d - timedelta(days=sunday_offset)


def usable_weeks(year: int, today: date) -> list[int]:
    """Return grid-relative week indices whose Mon-Fri all fall in `year`
    AND, for the current year, whose Saturday has already passed as of `today`.
    """
    grid_start = _sunday_on_or_before(date(year, 1, 1))
    result: list[int] = []
    for week_idx in range(54):
        sun = grid_start + timedelta(weeks=week_idx)
        mon = sun + timedelta(days=1)
        fri = sun + timedelta(days=5)
        sat = sun + timedelta(days=6)
        if mon.year != year or fri.year != year:
            continue
        if sat > today:
            break
        result.append(week_idx)
    return result
