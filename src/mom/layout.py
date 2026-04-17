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


def required_cols(text: str) -> int:
    """Pixel-columns needed to render text in the 3x5 font with 1-col spacing."""
    if not text:
        raise ValueError("text must be non-empty")
    return 4 * len(text) - 1


def check_fit(required: int, available: int, year: int) -> Fit:
    return Fit(ok=required <= available, required=required, available=available, year=year)


from mom.font import get_glyph

_INTENSITY_COMMITS: dict[int, int] = {1: 5, 2: 10, 3: 15, 4: 20}


def plan(text: str, year: int, today: date, intensity: int) -> "Canvas | Fit":
    """Build a Canvas for text on year's grid, or a Fit(ok=False) on failure.

    Raises UnsupportedCharError if any char has no glyph.
    Returns Fit(ok=False, ...) if text doesn't fit or year has no drawable weeks.
    """
    if intensity not in _INTENSITY_COMMITS:
        raise ValueError(f"intensity must be 1..4, got {intensity}")

    weeks = usable_weeks(year, today)
    req = required_cols(text)
    fit = check_fit(req, len(weeks), year)
    if not fit.ok:
        return fit

    # Resolve glyphs up-front so UnsupportedCharError fires before layout work.
    glyphs = [get_glyph(ch) for ch in text]

    grid_start = _sunday_on_or_before(date(year, 1, 1))
    pad = (len(weeks) - req) // 2
    start_col = weeks[pad]

    cells: list[tuple[date, int]] = []
    commits_per_cell = _INTENSITY_COMMITS[intensity]

    col_cursor = start_col
    for glyph in glyphs:
        # glyph rows correspond to font rows 0..4 -> grid rows 1..5 (Mon..Fri)
        for glyph_row, row_str in enumerate(glyph):
            grid_row = glyph_row + 1
            for glyph_col in range(3):
                if row_str[glyph_col] == "#":
                    cell_date = grid_start + timedelta(
                        weeks=col_cursor + glyph_col, days=grid_row
                    )
                    cells.append((cell_date, commits_per_cell))
        col_cursor += 4   # 3 cols glyph + 1 col spacing

    return Canvas(
        year=year,
        cells=cells,
        width_cols=len(weeks),
        grid_start=grid_start,
        usable_week_indices=weeks,
        intensity=intensity,
        text=text,
    )
