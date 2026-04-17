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


from mom.layout import required_cols, check_fit


def test_required_cols_one_char():
    assert required_cols("A") == 3     # 1*3 + 0 = 3


def test_required_cols_two_chars():
    assert required_cols("HI") == 7    # 2*3 + 1 = 7


def test_required_cols_empty_raises():
    import pytest
    with pytest.raises(ValueError):
        required_cols("")


def test_required_cols_hello_world():
    assert required_cols("HELLO WORLD") == 43   # 11*3 + 10 = 43


def test_check_fit_exact_fit():
    # required 14, available 14 -> ok
    f = check_fit(14, 14, year=2024)
    assert f.ok is True


def test_check_fit_overflow_by_one():
    f = check_fit(15, 14, year=2026)
    assert f.ok is False
    assert f.required == 15
    assert f.available == 14


def test_check_fit_under():
    f = check_fit(3, 52, year=2024)
    assert f.ok is True


from datetime import date as _d
from mom.layout import plan
from mom.errors import UnsupportedCharError


def test_plan_returns_canvas_for_valid_input():
    today = _d(2026, 4, 16)
    result = plan("HI", year=2024, today=today, intensity=4)
    assert isinstance(result, Canvas)
    assert result.text == "HI"
    assert result.year == 2024
    assert result.intensity == 4


def test_plan_cell_count_matches_glyph_pixels():
    # "HI" in 3x5: H has 11 on-pixels (2+2+3+2+2), I has 9 (3+1+1+1+3) -> 20 cells.
    today = _d(2026, 4, 16)
    c = plan("HI", year=2024, today=today, intensity=4)
    assert len(c.cells) == 20


def test_plan_commit_count_scales_with_intensity():
    today = _d(2026, 4, 16)
    c4 = plan("A", year=2024, today=today, intensity=4)
    c1 = plan("A", year=2024, today=today, intensity=1)
    total4 = sum(n for _, n in c4.cells)
    total1 = sum(n for _, n in c1.cells)
    assert total4 == 4 * total1   # 20 vs 5


def test_plan_centers_horizontally():
    # "A" in 2024 (52 cols). required=3. pad=(52-3)//2 = 24. start_col=usable[24]=24.
    today = _d(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    min_col = min((cell_date - c.grid_start).days // 7 for cell_date, _ in c.cells)
    max_col = max((cell_date - c.grid_start).days // 7 for cell_date, _ in c.cells)
    assert min_col == 24
    assert max_col == 26   # 3 cols wide


def test_plan_rejects_when_too_wide_returns_fit():
    today = _d(2026, 4, 16)
    result = plan("HELLO WORLD", year=2026, today=today, intensity=4)
    assert isinstance(result, Fit)
    assert result.ok is False


def test_plan_future_year_returns_fit_fail():
    today = _d(2026, 4, 16)
    result = plan("HI", year=2027, today=today, intensity=4)
    assert isinstance(result, Fit)
    assert result.ok is False


def test_plan_unsupported_char_raises():
    import pytest
    today = _d(2026, 4, 16)
    with pytest.raises(UnsupportedCharError):
        plan("HI\u2764", year=2024, today=today, intensity=4)


def test_plan_cells_use_rows_1_to_5():
    # Font occupies Mon-Fri (weekday 0-4 -> sun-offset 1-5).
    today = _d(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    for cell_date, _ in c.cells:
        offset = (cell_date - c.grid_start).days % 7
        assert 1 <= offset <= 5
