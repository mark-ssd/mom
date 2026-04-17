"""Pure layout: text + window -> Canvas with fit validation."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import date, timedelta
from mom.font import get_glyph

_INTENSITY_COMMITS: dict[int, int] = {1: 5, 2: 10, 3: 15, 4: 20}


def _sunday_on_or_before(d: date) -> date:
    # date.weekday(): Mon=0..Sun=6. Convert so Sun=0.
    sunday_offset = (d.weekday() + 1) % 7
    return d - timedelta(days=sunday_offset)


@dataclass(frozen=True)
class Window:
    """A slice of the contribution grid where drawing is allowed.

    - grid_start: Sunday anchor of column 0 within this window
    - usable_indices: column indices where Mon-Fri are in-scope and the
      week's Saturday has passed (drawable cells)
    - display_cols: total columns GitHub renders for this view (includes
      partial weeks at both ends). Used for visual centering.
    - state_key: unique identifier stored in .mom-state.json
    - human_desc: human-readable label used in error messages
    - mode: "calendar" or "trailing"
    - ref: mode-specific reference for regeneration ("2024" or "2026-04-16")
    """
    grid_start: date
    usable_indices: tuple[int, ...]
    display_cols: int
    state_key: str
    human_desc: str
    mode: str
    ref: str


@dataclass(frozen=True)
class Canvas:
    cells: list[tuple[date, int]]
    window: Window
    intensity: int
    text: str


@dataclass(frozen=True)
class Fit:
    ok: bool
    required: int
    available: int
    window: Window


def usable_weeks(year: int, today: date) -> list[int]:
    """Grid-relative week indices whose Mon-Fri all fall in `year`
    AND whose Saturday has already passed as of `today`.
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


def _display_cols_calendar(year: int, today: date, grid_start: date) -> int:
    """Count weeks GitHub renders for the given calendar year as of today.
    Includes partial weeks at year boundaries; for the current year, stops at
    the current week (inclusive).
    """
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    count = 0
    for wk in range(54):
        sun = grid_start + timedelta(weeks=wk)
        sat = sun + timedelta(days=6)
        if sun > year_end or sat < year_start:
            continue
        if year == today.year and sun > today:
            break
        count = wk + 1
    return count


def calendar_window(year: int, today: date) -> Window:
    grid_start = _sunday_on_or_before(date(year, 1, 1))
    indices = tuple(usable_weeks(year, today))
    display_cols = _display_cols_calendar(year, today, grid_start)
    return Window(
        grid_start=grid_start,
        usable_indices=indices,
        display_cols=display_cols,
        state_key=f"calendar-{year}",
        human_desc=f"year {year}",
        mode="calendar",
        ref=str(year),
    )


def trailing_window(ref_date: date) -> Window:
    """The 52 complete weeks ending with the most recent Saturday on-or-before `ref_date`.

    This matches GitHub's default profile view ("N contributions in the last year").
    """
    # Most recent Saturday on-or-before ref_date. Mon=0..Sat=5..Sun=6.
    days_since_sat = (ref_date.weekday() - 5) % 7
    last_sat = ref_date - timedelta(days=days_since_sat)
    end_sun = last_sat - timedelta(days=6)
    grid_start = end_sun - timedelta(weeks=51)
    return Window(
        grid_start=grid_start,
        usable_indices=tuple(range(52)),
        # GitHub's default view shows 53 cols: 52 complete weeks + current week.
        display_cols=53,
        # Single fixed state key -- only one trailing drawing can exist at a
        # time; re-runs on different days replace each other rather than
        # stacking (different ref_dates on consecutive days would otherwise
        # produce overlapping cells).
        state_key="trailing",
        human_desc=f"trailing window ending {ref_date.isoformat()}",
        mode="trailing",
        ref=ref_date.isoformat(),
    )


_GLYPH_WIDTH = 5
_GLYPH_SPACING = 1


def required_cols(text: str) -> int:
    """Pixel-columns needed to render text in the 5x5 font with 1-col spacing."""
    if not text:
        raise ValueError("text must be non-empty")
    return _GLYPH_WIDTH * len(text) + _GLYPH_SPACING * (len(text) - 1)


def check_fit(required: int, available: int, window: Window) -> Fit:
    return Fit(ok=required <= available, required=required, available=available, window=window)


def plan(text: str, window: Window, intensity: int) -> "Canvas | Fit":
    """Build a Canvas for text on the given window, or Fit(ok=False) on failure.

    Raises UnsupportedCharError if any char has no glyph.
    """
    if intensity not in _INTENSITY_COMMITS:
        raise ValueError(f"intensity must be 1..4, got {intensity}")

    req = required_cols(text)
    fit = check_fit(req, len(window.usable_indices), window)
    if not fit.ok:
        return fit

    glyphs = [get_glyph(ch) for ch in text]

    # Center using GitHub's display width, then clamp so the drawing stays in usable cols.
    pad = (window.display_cols - req) // 2
    start_col = max(pad, window.usable_indices[0])
    # If that would overrun the last usable col, right-align within usable range.
    if start_col + req - 1 > window.usable_indices[-1]:
        start_col = window.usable_indices[-1] - req + 1

    cells: list[tuple[date, int]] = []
    commits_per_cell = _INTENSITY_COMMITS[intensity]

    col_cursor = start_col
    for glyph in glyphs:
        for glyph_row, row_str in enumerate(glyph):
            grid_row = glyph_row + 1   # rows 1..5 (Mon..Fri)
            for glyph_col in range(_GLYPH_WIDTH):
                if row_str[glyph_col] == "#":
                    cell_date = window.grid_start + timedelta(
                        weeks=col_cursor + glyph_col, days=grid_row
                    )
                    cells.append((cell_date, commits_per_cell))
        col_cursor += _GLYPH_WIDTH + _GLYPH_SPACING

    return Canvas(cells=cells, window=window, intensity=intensity, text=text)


def window_from_state(mode: str, ref: str, today: date) -> Window:
    """Rebuild a Window from stored (mode, ref) — used by git_ops on rebuild."""
    if mode == "calendar":
        return calendar_window(int(ref), today)
    if mode == "trailing":
        return trailing_window(date.fromisoformat(ref))
    raise ValueError(f"unknown mode: {mode!r}")
