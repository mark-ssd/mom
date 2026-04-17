from datetime import date
import pytest
from mom.layout import (
    Canvas, Fit, Window,
    usable_weeks, required_cols, check_fit, plan,
    calendar_window, trailing_window, window_from_state,
)
from mom.errors import UnsupportedCharError


# ---- usable_weeks ----

def test_usable_weeks_past_year_2024():
    today = date(2026, 4, 16)
    assert len(usable_weeks(2024, today)) == 52


def test_usable_weeks_past_year_2022():
    today = date(2026, 4, 16)
    assert len(usable_weeks(2022, today)) == 52


def test_usable_weeks_current_year_partial():
    today = date(2026, 4, 16)   # Thursday
    assert len(usable_weeks(2026, today)) == 14


def test_usable_weeks_current_year_cutoff_on_saturday():
    today = date(2026, 4, 18)   # Saturday
    assert len(usable_weeks(2026, today)) == 15


def test_usable_weeks_future_year_empty():
    today = date(2026, 4, 16)
    assert usable_weeks(2027, today) == []


# ---- calendar_window ----

def test_calendar_window_for_2024():
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    assert w.mode == "calendar"
    assert w.ref == "2024"
    assert w.state_key == "calendar-2024"
    assert w.human_desc == "year 2024"
    assert len(w.usable_indices) == 52


def test_calendar_window_current_year_partial():
    today = date(2026, 4, 16)
    w = calendar_window(2026, today)
    assert len(w.usable_indices) == 14


# ---- trailing_window ----

def test_trailing_window_has_52_cols():
    ref = date(2026, 4, 16)   # Thursday
    w = trailing_window(ref)
    assert len(w.usable_indices) == 52


def test_trailing_window_state_key_is_fixed():
    # Fixed "trailing" key so re-runs on different days replace, not stack.
    w = trailing_window(date(2026, 4, 16))
    assert w.state_key == "trailing"
    assert w.ref == "2026-04-16"
    assert w.mode == "trailing"

    w2 = trailing_window(date(2026, 4, 17))
    assert w2.state_key == "trailing"
    assert w2.ref == "2026-04-17"


def test_trailing_window_ends_at_most_recent_completed_saturday():
    # Today = Thu Apr 16 2026. Last completed Sat = Apr 11. End-week Sun = Apr 5.
    ref = date(2026, 4, 16)
    w = trailing_window(ref)
    # Last usable week start (Sun) is grid_start + 51*7 days
    from datetime import timedelta
    last_week_sun = w.grid_start + timedelta(weeks=51)
    assert last_week_sun == date(2026, 4, 5)
    # And the grid_start should be 51 weeks earlier = Apr 13 2025 (Sun)
    assert w.grid_start == date(2025, 4, 13)


def test_trailing_window_on_saturday_includes_that_week():
    # Today = Sat Apr 18 2026. Last Sat = itself. End-week Sun = Apr 12.
    ref = date(2026, 4, 18)
    w = trailing_window(ref)
    from datetime import timedelta
    last_week_sun = w.grid_start + timedelta(weeks=51)
    assert last_week_sun == date(2026, 4, 12)


# ---- required_cols, check_fit ----

def test_required_cols_one_char():
    assert required_cols("A") == 3


def test_required_cols_two_chars():
    assert required_cols("HI") == 7


def test_required_cols_empty_raises():
    with pytest.raises(ValueError):
        required_cols("")


def test_required_cols_hello_world():
    assert required_cols("HELLO WORLD") == 43


def test_check_fit_exact_fit():
    w = calendar_window(2024, date(2026, 4, 16))
    f = check_fit(14, 14, w)
    assert f.ok is True


def test_check_fit_overflow_by_one():
    w = calendar_window(2026, date(2026, 4, 16))
    f = check_fit(15, 14, w)
    assert f.ok is False
    assert f.required == 15
    assert f.available == 14


# ---- plan ----

def test_plan_calendar_returns_canvas_for_valid_input():
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    result = plan("HI", w, intensity=4)
    assert isinstance(result, Canvas)
    assert result.text == "HI"
    assert result.window.state_key == "calendar-2024"
    assert result.intensity == 4


def test_plan_trailing_returns_canvas_and_fits_ssd_tech():
    today = date(2026, 4, 16)
    w = trailing_window(today)
    result = plan("SSD TECH", w, intensity=4)
    assert isinstance(result, Canvas)
    # 8 chars: 4*8-1 = 31 cols. 52 available in trailing window.
    assert result.window.state_key == "trailing"


def test_plan_cell_count_matches_glyph_pixels():
    # "HI": H=11 (2+2+3+2+2), I=9 (3+1+1+1+3) = 20 cells.
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    c = plan("HI", w, intensity=4)
    assert len(c.cells) == 20


def test_plan_commit_count_scales_with_intensity():
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    c4 = plan("A", w, intensity=4)
    c1 = plan("A", w, intensity=1)
    total4 = sum(n for _, n in c4.cells)
    total1 = sum(n for _, n in c1.cells)
    assert total4 == 4 * total1


def test_plan_centers_horizontally():
    # "A" in 2024. display_cols=53 (53 weeks span 2024). pad=(53-3)//2=25.
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    c = plan("A", w, intensity=4)
    min_col = min((d - c.window.grid_start).days // 7 for d, _ in c.cells)
    max_col = max((d - c.window.grid_start).days // 7 for d, _ in c.cells)
    assert min_col == 25
    assert max_col == 27


def test_plan_trailing_centers_on_53_col_display():
    # Trailing display_cols=53. "SSD TECH" = 31 cols. pad=(53-31)//2=11.
    today = date(2026, 4, 16)
    w = trailing_window(today)
    c = plan("SSD TECH", w, intensity=4)
    min_col = min((d - c.window.grid_start).days // 7 for d, _ in c.cells)
    max_col = max((d - c.window.grid_start).days // 7 for d, _ in c.cells)
    assert min_col == 11
    assert max_col == 41


def test_calendar_window_display_cols_past_year():
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    assert w.display_cols == 53   # 2024 spans 53 weeks in GitHub's view


def test_trailing_window_display_cols_is_53():
    w = trailing_window(date(2026, 4, 16))
    assert w.display_cols == 53


def test_plan_rejects_too_wide_returns_fit_fail():
    today = date(2026, 4, 16)
    w = calendar_window(2026, today)
    result = plan("HELLO WORLD", w, intensity=4)
    assert isinstance(result, Fit)
    assert result.ok is False


def test_plan_future_year_returns_fit_fail():
    today = date(2026, 4, 16)
    w = calendar_window(2027, today)
    result = plan("HI", w, intensity=4)
    assert isinstance(result, Fit)
    assert result.ok is False


def test_plan_unsupported_char_raises():
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    with pytest.raises(UnsupportedCharError):
        plan("HI\u2764", w, intensity=4)


def test_plan_cells_use_rows_1_to_5():
    today = date(2026, 4, 16)
    w = calendar_window(2024, today)
    c = plan("A", w, intensity=4)
    for cell_date, _ in c.cells:
        offset = (cell_date - c.window.grid_start).days % 7
        assert 1 <= offset <= 5


def test_plan_trailing_cell_dates_span_two_years():
    # trailing window spans across year boundary (Apr 2025 -> Apr 2026)
    today = date(2026, 4, 16)
    w = trailing_window(today)
    c = plan("SSD TECH", w, intensity=4)
    years = {d.year for d, _ in c.cells}
    # Drawing is centered; with 52 cols and text needing 31, centered at col 10..41.
    # Those dates should all be in 2025 or 2026.
    assert years <= {2025, 2026}


# ---- window_from_state ----

def test_window_from_state_calendar():
    today = date(2026, 4, 16)
    w = window_from_state("calendar", "2024", today)
    assert w.state_key == "calendar-2024"
    assert len(w.usable_indices) == 52


def test_window_from_state_trailing():
    w = window_from_state("trailing", "2026-04-16", date(2026, 5, 1))
    assert w.state_key == "trailing"
    assert len(w.usable_indices) == 52


def test_window_from_state_unknown_mode_raises():
    with pytest.raises(ValueError):
        window_from_state("unknown", "x", date(2026, 4, 16))
