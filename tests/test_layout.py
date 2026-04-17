from datetime import date
from mom.layout import Canvas, Fit, usable_weeks


def test_usable_weeks_past_year_2024():
    # 2024: Jan 1 is Monday. Weeks whose Mon-Fri are all in 2024 -> 52.
    today = date(2026, 4, 16)
    weeks = usable_weeks(2024, today)
    assert len(weeks) == 52


def test_usable_weeks_past_year_2022():
    # 2022: Jan 1 = Sat, first eligible Mon = Jan 3, last eligible Fri = Dec 30 -> 52.
    today = date(2026, 4, 16)
    weeks = usable_weeks(2022, today)
    assert len(weeks) == 52


def test_usable_weeks_current_year_partial():
    # As of Thursday Apr 16 2026, weeks Jan 5-9 through Apr 6-10 = 14 usable.
    today = date(2026, 4, 16)
    weeks = usable_weeks(2026, today)
    assert len(weeks) == 14


def test_usable_weeks_current_year_cutoff_on_saturday():
    # If today is Saturday, the full current week is usable.
    today = date(2026, 4, 18)   # Sat in week Apr 12-18
    weeks = usable_weeks(2026, today)
    assert len(weeks) == 15


def test_usable_weeks_future_year_empty():
    today = date(2026, 4, 16)
    assert usable_weeks(2027, today) == []


def test_usable_weeks_indices_are_grid_relative():
    # The returned indices are relative to grid_start = Sunday on-or-before Jan 1.
    # For 2024 (Jan 1 = Mon), grid_start = Dec 31 2023. First usable week is index 0
    # (its Mon-Fri Jan 1-5 are all 2024).
    today = date(2026, 4, 16)
    weeks = usable_weeks(2024, today)
    assert weeks[0] == 0


def test_canvas_dataclass_fields():
    from datetime import date as d
    c = Canvas(
        year=2024,
        cells=[(d(2024, 6, 1), 20)],
        width_cols=52,
        grid_start=d(2023, 12, 31),
        usable_week_indices=list(range(52)),
        intensity=4,
        text="HI",
    )
    assert c.year == 2024
    assert c.cells == [(d(2024, 6, 1), 20)]


def test_fit_dataclass_fields():
    f = Fit(ok=False, required=43, available=14, year=2026)
    assert f.ok is False
    assert f.required == 43
