from datetime import date
from mom.layout import plan, calendar_window
from mom.preview import render


def test_render_has_7_weekday_rows():
    today = date(2026, 4, 16)
    c = plan("HI", calendar_window(2024, today), intensity=4)
    out = render(c)
    lines = out.splitlines()
    # Find rows starting with Sun, Mon, ..., Sat
    day_rows = [l for l in lines if l[:3] in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")]
    assert len(day_rows) == 7


def test_render_uses_hash_for_on_pixels():
    today = date(2026, 4, 16)
    c = plan("A", calendar_window(2024, today), intensity=4)
    out = render(c)
    assert "#" in out


def test_render_uses_dot_for_off_pixels():
    today = date(2026, 4, 16)
    c = plan("A", calendar_window(2024, today), intensity=4)
    out = render(c)
    assert "." in out


def test_render_includes_month_header():
    today = date(2026, 4, 16)
    c = plan("A", calendar_window(2024, today), intensity=4)
    out = render(c)
    # Header line contains month names.
    assert "Jan" in out
    assert "Dec" in out


def test_render_sun_and_sat_rows_are_empty():
    # Font occupies Mon-Fri only; Sun (row 0) and Sat (row 6) must be all dots.
    today = date(2026, 4, 16)
    c = plan("A", calendar_window(2024, today), intensity=4)
    out = render(c)
    lines = out.splitlines()
    sun_row = next(l for l in lines if l.startswith("Sun"))
    sat_row = next(l for l in lines if l.startswith("Sat"))
    assert "#" not in sun_row
    assert "#" not in sat_row
