# mom-canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `mom` Python CLI plus a companion Claude Skill that draws user-supplied text on the GitHub contribution graph by materialising backdated empty commits in a dedicated GitHub repository.

**Architecture:** A Python package split into **pure modules** (`font`, `layout`, `preview`) and **impure modules** (`config`, `gh`, `git_ops`), orchestrated by a Typer CLI. A thin `SKILL.md` wraps the CLI for conversational use via `/mom-canvas TEXT`.

**Tech Stack:** Python 3.10+, Typer (CLI), requests (HTTP), pytest + responses (tests), stdlib `subprocess` for git, pipx for distribution.

**Spec:** `docs/superpowers/specs/2026-04-16-mom-canvas-design.md`

---

## File Structure

All paths rooted at repo root `/home/mark-ssd/code/ssd.foundation/mom/`.

**Source (`src/mom/`):**
- `__init__.py` — package version
- `errors.py` — exception classes (`UnsupportedCharError`, `FitError`, `AuthError`, `NotOurRepoError`, `NetworkError`)
- `font.py` — `GLYPHS: dict[str, tuple[str, ...]]` + `get_glyph(char)`
- `layout.py` — `Canvas` dataclass, `Fit` dataclass, `usable_weeks()`, `required_cols()`, `plan()`
- `preview.py` — `render(canvas) -> str`
- `config.py` — `Config` dataclass, `load()`, `save()`, `resolve_token()`
- `gh.py` — `verify_token()`, `verify_email()`, `ensure_repo()`
- `git_ops.py` — `ensure_local_clone()`, `rebuild()`, `refuse_if_not_ours()`
- `cli.py` — Typer app + subcommands

**Tests (`tests/`):** one `test_<module>.py` per module, plus `conftest.py` for shared fixtures.

**Top-level:**
- `pyproject.toml`
- `.gitignore`
- `README.md`
- `LICENSE` (MIT)
- `skill/SKILL.md`

Files that change together live together: each source module owns its tests. No cross-module test files. The CLI is the only module that imports from every other module; all other modules are leaves or only depend on `errors` + stdlib.

---

## Task 1 — Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `src/mom/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "mom-canvas"
version = "0.1.0"
description = "Draw text on your GitHub contribution graph."
readme = "README.md"
license = {text = "MIT"}
authors = [{name = "Mark SSD", email = "aveyurov@gmail.com"}]
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "requests>=2.31",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "responses>=0.25",
]

[project.scripts]
mom = "mom.cli:app"

[project.urls]
Homepage = "https://github.com/mark-ssd/mom"

[tool.hatch.build.targets.wheel]
packages = ["src/mom"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
markers = ["live: tests that hit real GitHub (opt-in, not run in CI)"]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
venv/
dist/
build/
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
.env
```

- [ ] **Step 3: Write `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 Mark SSD

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Write `src/mom/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 5: Write empty test init files**

`tests/__init__.py`: empty file.

`tests/conftest.py`:
```python
"""Shared pytest fixtures."""
```

- [ ] **Step 6: Create venv, install in editable mode, verify**

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest --version
mom --help
```
Expected: `pytest 8.x` prints, and `mom --help` shows an error (the Typer app doesn't exist yet — that's fine). Actually since `mom` maps to `mom.cli:app` which doesn't exist, expected: `ModuleNotFoundError`. That's OK for Task 1.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore LICENSE src/ tests/
git commit -m "chore: project scaffolding"
```

---

## Task 2 — Exception Classes (`errors.py`)

**Files:**
- Create: `src/mom/errors.py`
- Create: `tests/test_errors.py`

- [ ] **Step 1: Write failing test**

`tests/test_errors.py`:
```python
import pytest
from mom.errors import (
    MomError,
    UnsupportedCharError,
    FitError,
    AuthError,
    NotOurRepoError,
    NetworkError,
)


def test_all_errors_inherit_from_mom_error():
    for cls in (UnsupportedCharError, FitError, AuthError, NotOurRepoError, NetworkError):
        assert issubclass(cls, MomError)


def test_unsupported_char_carries_char():
    err = UnsupportedCharError("❤")
    assert err.char == "❤"
    assert "❤" in str(err)


def test_fit_error_carries_numbers():
    err = FitError(required=43, available=14, year=2026)
    assert err.required == 43
    assert err.available == 14
    assert err.year == 2026
    assert "43" in str(err) and "14" in str(err)


def test_auth_error_has_kind():
    err = AuthError(kind="auth_missing", message="No token.")
    assert err.kind == "auth_missing"
    assert str(err) == "No token."
```

- [ ] **Step 2: Run test — expect fail**

```bash
pytest tests/test_errors.py -v
```
Expected: `ModuleNotFoundError: No module named 'mom.errors'`.

- [ ] **Step 3: Implement `src/mom/errors.py`**

```python
"""Exception classes used across the package."""


class MomError(Exception):
    """Base for all mom errors."""


class UnsupportedCharError(MomError):
    def __init__(self, char: str) -> None:
        self.char = char
        super().__init__(
            f"Character {char!r} not supported. Allowed: printable ASCII (0x20-0x7E)."
        )


class FitError(MomError):
    def __init__(self, required: int, available: int, year: int) -> None:
        self.required = required
        self.available = available
        self.year = year
        max_chars = max(0, (available + 1) // 4)
        super().__init__(
            f"Doesn't fit. Required {required} cols, available {available} for year {year}. "
            f"Max text: ~{max_chars} chars. Try a different --year or shorten the text."
        )


class AuthError(MomError):
    def __init__(self, kind: str, message: str) -> None:
        self.kind = kind
        super().__init__(message)


class NotOurRepoError(MomError):
    def __init__(self, repo_name: str) -> None:
        self.repo_name = repo_name
        super().__init__(
            f"Repo '{repo_name}' isn't managed by mom (no .mom-state.json). "
            f"Refusing to touch it. Pick a different --repo."
        )


class NetworkError(MomError):
    pass
```

- [ ] **Step 4: Run test — expect pass**

```bash
pytest tests/test_errors.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/errors.py tests/test_errors.py
git commit -m "feat(errors): define exception hierarchy"
```

---

## Task 3 — Font Table (`font.py`)

**Files:**
- Create: `src/mom/font.py`
- Create: `tests/test_font.py`

Note: the glyph table below is a full 3×5 bitmap font for every printable ASCII char (0x20–0x7E). Hand-designed inline to keep this plan self-contained. Each glyph is a tuple of 5 strings of length 3, where `#` = on pixel and `.` = off pixel.

- [ ] **Step 1: Write failing tests**

`tests/test_font.py`:
```python
import string
import pytest
from mom.font import GLYPHS, get_glyph
from mom.errors import UnsupportedCharError


def test_all_printable_ascii_have_glyphs():
    # U+0020 (space) through U+007E (~). 95 chars total.
    for code in range(0x20, 0x7F):
        ch = chr(code)
        g = get_glyph(ch)
        assert g is not None, f"missing glyph for {ch!r} (U+{code:04X})"


def test_all_glyphs_are_5_rows_of_3_cols():
    for ch, glyph in GLYPHS.items():
        assert len(glyph) == 5, f"{ch!r} has {len(glyph)} rows, expected 5"
        for i, row in enumerate(glyph):
            assert len(row) == 3, f"{ch!r} row {i} has {len(row)} cols, expected 3"
            assert set(row) <= {"#", "."}, f"{ch!r} row {i} has illegal chars: {row}"


def test_uppercase_a_glyph_shape():
    # Pin the exact shape of 'A' as a canary for font stability.
    assert get_glyph("A") == (".#.", "#.#", "###", "#.#", "#.#")


def test_lowercase_falls_back_to_upper():
    # 3x5 is too small for meaningful case distinction; lowercase maps to uppercase.
    assert get_glyph("a") == get_glyph("A")
    assert get_glyph("z") == get_glyph("Z")


def test_space_is_all_empty():
    assert get_glyph(" ") == ("...", "...", "...", "...", "...")


def test_unsupported_char_raises():
    with pytest.raises(UnsupportedCharError) as excinfo:
        get_glyph("❤")
    assert excinfo.value.char == "❤"
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_font.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/font.py`**

```python
"""Tom-Thumb-inspired 3x5 bitmap font covering printable ASCII (0x20-0x7E)."""

from mom.errors import UnsupportedCharError

GLYPHS: dict[str, tuple[str, ...]] = {
    # Space + punctuation (0x20-0x2F)
    " ": ("...", "...", "...", "...", "..."),
    "!": (".#.", ".#.", ".#.", "...", ".#."),
    '"': ("#.#", "#.#", "...", "...", "..."),
    "#": ("#.#", "###", "#.#", "###", "#.#"),
    "$": (".##", "##.", ".##", "##.", "##."),
    "%": ("#.#", "..#", ".#.", "#..", "#.#"),
    "&": ("##.", "##.", "###", "#.#", "###"),
    "'": (".#.", ".#.", "...", "...", "..."),
    "(": ("..#", ".#.", ".#.", ".#.", "..#"),
    ")": ("#..", ".#.", ".#.", ".#.", "#.."),
    "*": ("...", "#.#", ".#.", "#.#", "..."),
    "+": ("...", ".#.", "###", ".#.", "..."),
    ",": ("...", "...", "...", ".#.", "#.."),
    "-": ("...", "...", "###", "...", "..."),
    ".": ("...", "...", "...", "...", ".#."),
    "/": ("..#", "..#", ".#.", "#..", "#.."),

    # Digits (0x30-0x39)
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("##.", "..#", ".#.", "#..", "###"),
    "3": ("##.", "..#", ".#.", "..#", "##."),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "##.", "..#", "##."),
    "6": (".##", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", ".#.", "#..", "#.."),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "##."),

    # 0x3A-0x40
    ":": ("...", ".#.", "...", ".#.", "..."),
    ";": ("...", ".#.", "...", ".#.", "#.."),
    "<": ("..#", ".#.", "#..", ".#.", "..#"),
    "=": ("...", "###", "...", "###", "..."),
    ">": ("#..", ".#.", "..#", ".#.", "#.."),
    "?": ("##.", "..#", ".#.", "...", ".#."),
    "@": ("###", "#.#", "###", "#..", ".##"),

    # Uppercase A-Z (0x41-0x5A)
    "A": (".#.", "#.#", "###", "#.#", "#.#"),
    "B": ("##.", "#.#", "##.", "#.#", "##."),
    "C": (".##", "#..", "#..", "#..", ".##"),
    "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "E": ("###", "#..", "##.", "#..", "###"),
    "F": ("###", "#..", "##.", "#..", "#.."),
    "G": (".##", "#..", "#.#", "#.#", ".##"),
    "H": ("#.#", "#.#", "###", "#.#", "#.#"),
    "I": ("###", ".#.", ".#.", ".#.", "###"),
    "J": ("..#", "..#", "..#", "#.#", ".#."),
    "K": ("#.#", "#.#", "##.", "#.#", "#.#"),
    "L": ("#..", "#..", "#..", "#..", "###"),
    "M": ("#.#", "###", "###", "#.#", "#.#"),
    "N": ("#.#", "###", "###", "###", "#.#"),
    "O": (".#.", "#.#", "#.#", "#.#", ".#."),
    "P": ("##.", "#.#", "##.", "#..", "#.."),
    "Q": (".#.", "#.#", "#.#", "##.", ".##"),
    "R": ("##.", "#.#", "##.", "#.#", "#.#"),
    "S": (".##", "#..", ".#.", "..#", "##."),
    "T": ("###", ".#.", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "V": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": ("#.#", "#.#", "###", "###", "#.#"),
    "X": ("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": ("#.#", "#.#", ".#.", ".#.", ".#."),
    "Z": ("###", "..#", ".#.", "#..", "###"),

    # 0x5B-0x60
    "[": (".##", ".#.", ".#.", ".#.", ".##"),
    "\\": ("#..", "#..", ".#.", "..#", "..#"),
    "]": ("##.", ".#.", ".#.", ".#.", "##."),
    "^": (".#.", "#.#", "...", "...", "..."),
    "_": ("...", "...", "...", "...", "###"),
    "`": ("#..", ".#.", "...", "...", "..."),

    # 0x7B-0x7E
    "{": ("..#", ".#.", "##.", ".#.", "..#"),
    "|": (".#.", ".#.", ".#.", ".#.", ".#."),
    "}": ("#..", ".#.", ".##", ".#.", "#.."),
    "~": ("...", ".##", "##.", "...", "..."),
}


def get_glyph(char: str) -> tuple[str, ...]:
    """Return 5-row × 3-col glyph for char.

    Lowercase ASCII falls back to uppercase (3x5 is too small for distinct cases).
    Raises UnsupportedCharError for anything outside printable ASCII.
    """
    if char in GLYPHS:
        return GLYPHS[char]
    if char.isascii() and char.isalpha() and char.upper() in GLYPHS:
        return GLYPHS[char.upper()]
    raise UnsupportedCharError(char)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_font.py -v
```
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/font.py tests/test_font.py
git commit -m "feat(font): add 3x5 printable-ASCII bitmap font"
```

---

## Task 4 — Layout: `usable_weeks` helper

**Files:**
- Create: `src/mom/layout.py`
- Create: `tests/test_layout.py`

This task only implements `usable_weeks()` and the `Canvas`/`Fit` dataclasses. Subsequent tasks add `required_cols()` and `plan()`.

- [ ] **Step 1: Write failing tests**

`tests/test_layout.py`:
```python
from datetime import date
from mom.layout import Canvas, Fit, usable_weeks


def test_usable_weeks_past_year_2024():
    # 2024: Jan 1 is Monday. Weeks whose Mon-Fri are all in 2024 → 52.
    today = date(2026, 4, 16)
    weeks = usable_weeks(2024, today)
    assert len(weeks) == 52


def test_usable_weeks_past_year_2022():
    # 2022: Jan 1 is Saturday → 53 usable weeks.
    today = date(2026, 4, 16)
    weeks = usable_weeks(2022, today)
    assert len(weeks) == 53


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
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_layout.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/layout.py` (partial — usable_weeks + dataclasses only)**

```python
"""Pure layout: text → Canvas with fit validation."""

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
        if year == today.year and sat > today:
            break
        result.append(week_idx)
    return result
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_layout.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/layout.py tests/test_layout.py
git commit -m "feat(layout): add Canvas/Fit dataclasses and usable_weeks"
```

---

## Task 5 — Layout: `required_cols` + `check_fit`

**Files:**
- Modify: `src/mom/layout.py`
- Modify: `tests/test_layout.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_layout.py`:
```python
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
    # required 14, available 14 → ok
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
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_layout.py::test_required_cols_one_char -v
```
Expected: ImportError on `required_cols`, `check_fit`.

- [ ] **Step 3: Append implementation to `src/mom/layout.py`**

```python
def required_cols(text: str) -> int:
    """Pixel-columns needed to render text in the 3×5 font with 1-col spacing."""
    if not text:
        raise ValueError("text must be non-empty")
    return 4 * len(text) - 1


def check_fit(required: int, available: int, year: int) -> Fit:
    return Fit(ok=required <= available, required=required, available=available, year=year)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_layout.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/layout.py tests/test_layout.py
git commit -m "feat(layout): add required_cols and check_fit"
```

---

## Task 6 — Layout: `plan()` main function

**Files:**
- Modify: `src/mom/layout.py`
- Modify: `tests/test_layout.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_layout.py`:
```python
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
    # "HI" in 3x5: H has 11 on-pixels (2+2+3+2+2), I has 9 (3+1+1+1+3) → 20 cells.
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
        plan("HI❤", year=2024, today=today, intensity=4)


def test_plan_cells_use_rows_1_to_5():
    # Font occupies Mon-Fri (weekday 0-4 → sun-offset 1-5).
    today = _d(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    for cell_date, _ in c.cells:
        offset = (cell_date - c.grid_start).days % 7
        assert 1 <= offset <= 5
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_layout.py -v
```
Expected: ImportError on `plan`.

- [ ] **Step 3: Append implementation to `src/mom/layout.py`**

```python
from mom.font import get_glyph

_INTENSITY_COMMITS: dict[int, int] = {1: 5, 2: 10, 3: 15, 4: 20}


def plan(text: str, year: int, today: date, intensity: int) -> Canvas | Fit:
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
        # glyph rows correspond to font rows 0..4 → grid rows 1..5 (Mon..Fri)
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
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_layout.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/layout.py tests/test_layout.py
git commit -m "feat(layout): add plan() for text→Canvas layout"
```

---

## Task 7 — Preview Renderer (`preview.py`)

**Files:**
- Create: `src/mom/preview.py`
- Create: `tests/test_preview.py`

- [ ] **Step 1: Write failing tests**

`tests/test_preview.py`:
```python
from datetime import date
from mom.layout import plan
from mom.preview import render


def test_render_has_7_weekday_rows():
    today = date(2026, 4, 16)
    c = plan("HI", year=2024, today=today, intensity=4)
    out = render(c)
    lines = out.splitlines()
    # Find rows starting with Sun, Mon, ..., Sat
    day_rows = [l for l in lines if l[:3] in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")]
    assert len(day_rows) == 7


def test_render_uses_block_for_on_pixels():
    today = date(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    out = render(c)
    assert "█" in out


def test_render_uses_dot_for_off_pixels():
    today = date(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    out = render(c)
    assert "·" in out


def test_render_includes_month_header():
    today = date(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    out = render(c)
    # Header line contains month names.
    assert "Jan" in out
    assert "Dec" in out


def test_render_sun_and_sat_rows_are_empty():
    # Font occupies Mon-Fri only; Sun (row 0) and Sat (row 6) must be all dots.
    today = date(2026, 4, 16)
    c = plan("A", year=2024, today=today, intensity=4)
    out = render(c)
    lines = out.splitlines()
    sun_row = next(l for l in lines if l.startswith("Sun"))
    sat_row = next(l for l in lines if l.startswith("Sat"))
    # Strip label + space prefix (4 chars), remaining should be only dots
    assert "█" not in sun_row
    assert "█" not in sat_row
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_preview.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/preview.py`**

```python
"""ASCII renderer for Canvas → terminal-friendly preview."""

from datetime import date, timedelta
from mom.layout import Canvas

_DAY_LABELS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def render(canvas: Canvas) -> str:
    """Render a Canvas as an ASCII grid with month header and weekday rows."""
    total_cols = 54
    on_cells = {(cell_date - canvas.grid_start).days % 7
                + 7 * ((cell_date - canvas.grid_start).days // 7): True
                for cell_date, _ in canvas.cells}

    # Build grid[row][col] = bool
    grid = [[False] * total_cols for _ in range(7)]
    for cell_date, _ in canvas.cells:
        offset_days = (cell_date - canvas.grid_start).days
        col = offset_days // 7
        row = offset_days % 7
        if 0 <= col < total_cols:
            grid[row][col] = True

    # Month header: place month abbreviation at the first column of each month
    header_cells = [" "] * total_cols
    for col in range(total_cols):
        col_date = canvas.grid_start + timedelta(weeks=col, days=1)  # Monday of that week
        if col_date.day <= 7 and col_date.year == canvas.year:
            month_str = _MONTHS[col_date.month - 1]
            for i, c in enumerate(month_str):
                if col + i < total_cols:
                    header_cells[col + i] = c

    lines: list[str] = []
    lines.append("        " + "".join(header_cells))
    for row, label in enumerate(_DAY_LABELS):
        row_chars = ["█" if grid[row][c] else "·" for c in range(total_cols)]
        lines.append(f"{label}     " + "".join(row_chars))
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_preview.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/preview.py tests/test_preview.py
git commit -m "feat(preview): ASCII renderer for Canvas"
```

---

## Task 8 — Config & Auth (`config.py`)

**Files:**
- Create: `src/mom/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
import json
import os
import subprocess
from pathlib import Path
import pytest
from mom.config import Config, load, save, resolve_token
from mom.errors import AuthError


@pytest.fixture
def tmp_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return tmp_path


def test_save_and_load_round_trip(tmp_xdg):
    cfg = Config(repo="mom-canvas", github_user="mark-ssd", token="ghp_xyz")
    save(cfg)
    loaded = load()
    assert loaded == cfg


def test_save_sets_chmod_600(tmp_xdg):
    cfg = Config(repo="x", github_user="y", token="ghp_xyz")
    save(cfg)
    path = tmp_xdg / "mom" / "config.json"
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_load_missing_file_returns_default(tmp_xdg):
    cfg = load()
    assert cfg.repo == "mom-canvas"
    assert cfg.github_user == ""
    assert cfg.token is None


def test_resolve_token_explicit_beats_all(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env_token")
    save(Config(repo="x", github_user="y", token="config_token"))
    assert resolve_token(explicit="flag_token") == "flag_token"


def test_resolve_token_env_beats_config(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env_token")
    save(Config(repo="x", github_user="y", token="config_token"))
    assert resolve_token(explicit=None) == "env_token"


def test_resolve_token_config_when_no_env(tmp_xdg):
    save(Config(repo="x", github_user="y", token="config_token"))
    assert resolve_token(explicit=None) == "config_token"


def test_resolve_token_falls_back_to_gh_cli(tmp_xdg, monkeypatch):
    # Mock subprocess to simulate `gh auth token`.
    def fake_run(cmd, *a, **kw):
        if cmd[:3] == ["gh", "auth", "token"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gh_token\n", stderr="")
        raise FileNotFoundError
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert resolve_token(explicit=None) == "gh_token"


def test_resolve_token_raises_when_nothing_works(tmp_xdg, monkeypatch):
    def fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AuthError) as excinfo:
        resolve_token(explicit=None)
    assert excinfo.value.kind == "auth_missing"
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_config.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/config.py`**

```python
"""Config file + auth resolution."""

from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from mom.errors import AuthError


@dataclass
class Config:
    repo: str = "mom-canvas"
    github_user: str = ""
    token: str | None = None


def _config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg) / "mom" / "config.json"


def load() -> Config:
    p = _config_path()
    if not p.exists():
        return Config()
    data = json.loads(p.read_text())
    return Config(
        repo=data.get("repo", "mom-canvas"),
        github_user=data.get("github_user", ""),
        token=data.get("token"),
    )


def save(cfg: Config) -> None:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(cfg), indent=2))
    os.chmod(p, 0o600)


def resolve_token(explicit: str | None) -> str:
    """Resolve a GitHub token in this precedence:
    explicit flag → GITHUB_TOKEN env → config file → gh CLI.
    Raises AuthError(kind="auth_missing") if none available.
    """
    if explicit:
        return explicit
    env_tok = os.environ.get("GITHUB_TOKEN")
    if env_tok:
        return env_tok
    cfg = load()
    if cfg.token:
        return cfg.token
    try:
        res = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except FileNotFoundError:
        pass
    raise AuthError(
        kind="auth_missing",
        message=(
            "No GitHub token found. Set GITHUB_TOKEN, pass --token, or run "
            "'mom config set-token'."
        ),
    )
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_config.py -v
```
Expected: all 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/config.py tests/test_config.py
git commit -m "feat(config): config file + auth resolution"
```

---

## Task 9 — GitHub API Client (`gh.py`)

**Files:**
- Create: `src/mom/gh.py`
- Create: `tests/test_gh.py`

- [ ] **Step 1: Write failing tests**

`tests/test_gh.py`:
```python
import pytest
import responses
from mom.gh import verify_token, verify_email, ensure_repo
from mom.errors import AuthError, NetworkError


API = "https://api.github.com"


@responses.activate
def test_verify_token_ok():
    responses.add(
        responses.GET, f"{API}/user",
        json={"login": "mark-ssd"}, status=200,
        headers={"X-OAuth-Scopes": "repo, read:user"},
    )
    user = verify_token("ghp_xyz")
    assert user == "mark-ssd"


@responses.activate
def test_verify_token_401_raises_auth_invalid():
    responses.add(responses.GET, f"{API}/user", json={}, status=401)
    with pytest.raises(AuthError) as excinfo:
        verify_token("bad")
    assert excinfo.value.kind == "auth_invalid"


@responses.activate
def test_verify_token_missing_repo_scope_raises():
    responses.add(
        responses.GET, f"{API}/user",
        json={"login": "x"}, status=200,
        headers={"X-OAuth-Scopes": "read:user"},
    )
    with pytest.raises(AuthError) as excinfo:
        verify_token("ghp_xyz")
    assert excinfo.value.kind == "auth_scope"


@responses.activate
def test_verify_email_match():
    responses.add(
        responses.GET, f"{API}/user/emails",
        json=[{"email": "a@b.com", "verified": True, "primary": True}],
        status=200,
    )
    # No exception → pass.
    verify_email("ghp_xyz", "a@b.com")


@responses.activate
def test_verify_email_mismatch_raises():
    responses.add(
        responses.GET, f"{API}/user/emails",
        json=[{"email": "a@b.com", "verified": True, "primary": True}],
        status=200,
    )
    with pytest.raises(AuthError) as excinfo:
        verify_email("ghp_xyz", "other@x.com")
    assert excinfo.value.kind == "email_mismatch"


@responses.activate
def test_ensure_repo_existing_returns_url():
    responses.add(
        responses.GET, f"{API}/repos/mark-ssd/mom-canvas",
        json={"clone_url": "https://github.com/mark-ssd/mom-canvas.git",
              "html_url": "https://github.com/mark-ssd/mom-canvas"},
        status=200,
    )
    clone, html = ensure_repo("ghp_xyz", "mark-ssd", "mom-canvas")
    assert clone == "https://github.com/mark-ssd/mom-canvas.git"
    assert html == "https://github.com/mark-ssd/mom-canvas"


@responses.activate
def test_ensure_repo_404_triggers_create():
    responses.add(
        responses.GET, f"{API}/repos/mark-ssd/mom-canvas",
        json={"message": "Not Found"}, status=404,
    )
    responses.add(
        responses.POST, f"{API}/user/repos",
        json={"clone_url": "https://github.com/mark-ssd/mom-canvas.git",
              "html_url": "https://github.com/mark-ssd/mom-canvas"},
        status=201,
    )
    clone, html = ensure_repo("ghp_xyz", "mark-ssd", "mom-canvas")
    assert "mom-canvas.git" in clone


@responses.activate
def test_ensure_repo_server_error_raises_network():
    responses.add(
        responses.GET, f"{API}/repos/mark-ssd/mom-canvas",
        json={}, status=500,
    )
    with pytest.raises(NetworkError):
        ensure_repo("ghp_xyz", "mark-ssd", "mom-canvas")
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_gh.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/gh.py`**

```python
"""GitHub REST API client."""

from __future__ import annotations
import requests
from mom.errors import AuthError, NetworkError

_API = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def verify_token(token: str) -> str:
    """Verify the token and return the login. Checks `repo` scope.
    Raises AuthError(kind="auth_invalid"|"auth_scope") or NetworkError.
    """
    try:
        r = requests.get(f"{_API}/user", headers=_headers(token), timeout=10)
    except requests.RequestException as e:
        raise NetworkError(str(e)) from e

    if r.status_code == 401:
        raise AuthError(
            "auth_invalid",
            "PAT rejected (401). Regenerate at github.com/settings/tokens with 'repo' scope.",
        )
    if r.status_code >= 500:
        raise NetworkError(f"GitHub API {r.status_code}: {r.text[:200]}")
    r.raise_for_status()

    scopes_hdr = r.headers.get("X-OAuth-Scopes", "")
    scopes = {s.strip() for s in scopes_hdr.split(",") if s.strip()}
    if "repo" not in scopes and "public_repo" not in scopes:
        raise AuthError(
            "auth_scope",
            "Token lacks 'repo' scope. Re-issue with that scope checked.",
        )
    return r.json()["login"]


def verify_email(token: str, git_email: str) -> None:
    """Verify that git_email is one of the user's verified GitHub emails.
    Raises AuthError(kind="email_mismatch") if not.
    """
    try:
        r = requests.get(f"{_API}/user/emails", headers=_headers(token), timeout=10)
    except requests.RequestException as e:
        raise NetworkError(str(e)) from e
    if r.status_code >= 500:
        raise NetworkError(f"GitHub API {r.status_code}: {r.text[:200]}")
    r.raise_for_status()

    verified = {e["email"].lower() for e in r.json() if e.get("verified")}
    if git_email.lower() not in verified:
        raise AuthError(
            "email_mismatch",
            f"git config user.email '{git_email}' isn't on your verified GitHub emails — "
            f"commits won't count. Fix with `git config user.email <verified>` and retry.",
        )


def ensure_repo(token: str, owner: str, name: str) -> tuple[str, str]:
    """Return (clone_url, html_url). Create the repo if it doesn't exist."""
    try:
        r = requests.get(
            f"{_API}/repos/{owner}/{name}", headers=_headers(token), timeout=10
        )
    except requests.RequestException as e:
        raise NetworkError(str(e)) from e

    if r.status_code == 200:
        data = r.json()
        return data["clone_url"], data["html_url"]
    if r.status_code == 404:
        try:
            cr = requests.post(
                f"{_API}/user/repos",
                headers=_headers(token),
                json={
                    "name": name,
                    "private": False,
                    "auto_init": False,
                    "description": "Managed by mom — pixel text on my contribution graph.",
                },
                timeout=10,
            )
        except requests.RequestException as e:
            raise NetworkError(str(e)) from e
        if cr.status_code not in (201, 422):
            raise NetworkError(f"repo create failed ({cr.status_code}): {cr.text[:200]}")
        data = cr.json()
        return data["clone_url"], data["html_url"]

    raise NetworkError(f"GitHub API {r.status_code}: {r.text[:200]}")
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_gh.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/gh.py tests/test_gh.py
git commit -m "feat(gh): GitHub REST client (verify_token, verify_email, ensure_repo)"
```

---

## Task 10 — Git Ops (`git_ops.py`)

**Files:**
- Create: `src/mom/git_ops.py`
- Create: `tests/test_git_ops.py`

- [ ] **Step 1: Write failing tests**

`tests/test_git_ops.py`:
```python
import json
import subprocess
from datetime import date
from pathlib import Path
import pytest
from mom.git_ops import (
    ensure_local_clone,
    read_state,
    write_state,
    refuse_if_not_ours,
    rebuild,
)
from mom.layout import plan
from mom.errors import NotOurRepoError


def _run(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def bare_origin(tmp_path):
    """Create a bare repo to act as 'origin'."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    return origin


@pytest.fixture
def author_env(monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Mark SSD")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "aveyurov@gmail.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Mark SSD")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "aveyurov@gmail.com")


def test_ensure_local_clone_creates_dir(tmp_path, bare_origin, author_env):
    work = tmp_path / "work"
    ensure_local_clone(work, f"file://{bare_origin}")
    assert (work / ".git").is_dir()


def test_read_state_missing_returns_default(tmp_path, bare_origin, author_env):
    work = tmp_path / "work"
    ensure_local_clone(work, f"file://{bare_origin}")
    state = read_state(work)
    assert state == {"managed_by": "mom", "version": 1, "drawings": {}}


def test_refuse_if_not_ours_raises_when_file_missing(tmp_path):
    # Dir exists but no .mom-state.json — should raise.
    d = tmp_path / "not_ours"
    d.mkdir()
    with pytest.raises(NotOurRepoError):
        refuse_if_not_ours(d, "somename")


def test_refuse_if_not_ours_raises_on_bad_marker(tmp_path):
    d = tmp_path / "fake"
    d.mkdir()
    (d / ".mom-state.json").write_text(json.dumps({"managed_by": "someone_else"}))
    with pytest.raises(NotOurRepoError):
        refuse_if_not_ours(d, "fake")


def test_refuse_if_not_ours_passes_on_good_marker(tmp_path):
    d = tmp_path / "good"
    d.mkdir()
    (d / ".mom-state.json").write_text(json.dumps({"managed_by": "mom", "version": 1}))
    refuse_if_not_ours(d, "good")   # no raise


def test_rebuild_creates_expected_commits(tmp_path, bare_origin, author_env):
    work = tmp_path / "work"
    today = date(2026, 4, 16)
    # Seed so refuse_if_not_ours passes on re-run.
    ensure_local_clone(work, f"file://{bare_origin}")
    write_state(work, {"managed_by": "mom", "version": 1, "drawings": {}})
    subprocess.run(["git", "-C", str(work), "add", "."], check=True)
    subprocess.run(["git", "-C", str(work), "commit", "-m", "seed", "--allow-empty"], check=True)
    subprocess.run(["git", "-C", str(work), "push", "origin", "HEAD:main"], check=True)

    canvas = plan("A", year=2024, today=today, intensity=1)  # intensity 1 → 5 commits/cell
    rebuild(
        work_dir=work,
        remote_url=f"file://{bare_origin}",
        year=2024,
        canvas=canvas,
        action="upsert",
        today=today,
    )
    # A has 10 on-pixels (1+2+3+2+2) × 5 commits + 1 initial "rebuild" commit = 51.
    log = subprocess.run(
        ["git", "-C", str(work), "log", "--format=%H", "main"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert len(log) == 10 * 5 + 1


def test_rebuild_refuses_repo_missing_state(tmp_path, bare_origin, author_env):
    """When the remote has commits but no .mom-state.json, rebuild refuses."""
    # Put a random file in the remote.
    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "-C", str(seed), "init", "-b", "main"], check=True)
    (seed / "README.md").write_text("not ours")
    subprocess.run(["git", "-C", str(seed), "add", "."], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-m", "seed"], check=True)
    subprocess.run(["git", "-C", str(seed), "push", f"file://{bare_origin}", "main"], check=True)

    work = tmp_path / "work"
    today = date(2026, 4, 16)
    canvas = plan("A", year=2024, today=today, intensity=1)
    with pytest.raises(NotOurRepoError):
        rebuild(
            work_dir=work,
            remote_url=f"file://{bare_origin}",
            year=2024,
            canvas=canvas,
            action="upsert",
            today=today,
        )
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_git_ops.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/git_ops.py`**

```python
"""Local git operations: clone, orphan-reset rebuild, force-push."""

from __future__ import annotations
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from mom.errors import NotOurRepoError
from mom.layout import Canvas, plan

_STATE_FILE = ".mom-state.json"
_README_BODY = (
    "# mom-canvas\n\n"
    "This repository is managed by [mom](https://github.com/mark-ssd/mom).\n\n"
    "Its commits form pixel text on the owner's GitHub contribution graph.\n"
    "Do not push to this repository manually — it will be rewritten on the next run.\n"
)


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True, env=env,
    )


def ensure_local_clone(work_dir: Path, remote_url: str) -> None:
    """Clone `remote_url` to `work_dir` if absent; otherwise fetch."""
    if (work_dir / ".git").is_dir():
        _git(work_dir, "fetch", "origin")
        return
    work_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", remote_url, str(work_dir)],
        capture_output=True, text=True, check=True,
    )


def read_state(work_dir: Path) -> dict:
    p = work_dir / _STATE_FILE
    if not p.exists():
        return {"managed_by": "mom", "version": 1, "drawings": {}}
    return json.loads(p.read_text())


def write_state(work_dir: Path, state: dict) -> None:
    (work_dir / _STATE_FILE).write_text(json.dumps(state, indent=2, sort_keys=True))


def refuse_if_not_ours(work_dir: Path, repo_name: str) -> None:
    """Raise NotOurRepoError unless the dir has a well-formed .mom-state.json.

    Empty directories (fresh clone with no commits) are allowed — the tool owns them
    from the first run. The refuse check only triggers if the dir is non-empty AND
    lacks our marker (i.e., someone else's repo).
    """
    state_file = work_dir / _STATE_FILE
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            if state.get("managed_by") == "mom":
                return
        except json.JSONDecodeError:
            pass
        raise NotOurRepoError(repo_name)
    # No state file: is the dir otherwise empty (aside from .git)?
    tracked = list(p for p in work_dir.iterdir() if p.name != ".git")
    if tracked:
        raise NotOurRepoError(repo_name)


def rebuild(
    *,
    work_dir: Path,
    remote_url: str,
    year: int,
    canvas: Canvas | None,
    action: Literal["upsert", "delete"],
    today: date,
) -> None:
    """Rebuild the repo's main branch deterministically from state, then force-push.

    action="upsert": write canvas.text for `year` into state (overwriting any prior).
    action="delete": remove `year` from state.
    canvas is used only for action="upsert"; for "delete", pass None.
    """
    ensure_local_clone(work_dir, remote_url)
    # Bring current main into the tree if it exists (so refuse_if_not_ours can check).
    try:
        _git(work_dir, "checkout", "main")
    except subprocess.CalledProcessError:
        pass   # branch doesn't exist yet (first run)

    repo_name = remote_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    refuse_if_not_ours(work_dir, repo_name)

    state = read_state(work_dir)
    drawings = state.setdefault("drawings", {})
    if action == "upsert":
        assert canvas is not None
        drawings[str(year)] = {
            "text": canvas.text,
            "intensity": canvas.intensity,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        drawings.pop(str(year), None)

    # Regenerate every stored drawing into cells (pure).
    all_cells: list[tuple[date, int]] = []
    for y_str, d in drawings.items():
        c = plan(d["text"], int(y_str), today, d["intensity"])
        if isinstance(c, Canvas):
            all_cells.extend(c.cells)
    # else: skip years that no longer fit (could happen if current-year capacity shrunk)
    all_cells.sort(key=lambda t: t[0])

    # Orphan-reset
    _git(work_dir, "checkout", "--orphan", "_build")
    try:
        _git(work_dir, "rm", "-rf", ".")
    except subprocess.CalledProcessError:
        pass   # empty index is fine
    (work_dir / "README.md").write_text(_README_BODY)
    write_state(work_dir, state)
    _git(work_dir, "add", ".")

    # Initial commit, dated 1 day before earliest drawing (or today if no drawings).
    seed_date = (all_cells[0][0] if all_cells else today)
    seed_env = _date_env(seed_date)
    _git(work_dir, "commit", "-m", "rebuild", env=_merged_env(seed_env))

    # Per-cell empty commits, chronological.
    for i, (d, count) in enumerate(all_cells):
        env = _merged_env(_date_env(d))
        for n in range(count):
            _git(work_dir, "commit", "--allow-empty",
                 "-m", f"canvas {d.isoformat()} #{n + 1}", env=env)

    # Promote _build to main and force-push.
    try:
        _git(work_dir, "branch", "-D", "main")
    except subprocess.CalledProcessError:
        pass
    _git(work_dir, "branch", "-M", "_build", "main")
    _git(work_dir, "push", "--force", "origin", "main")


def _date_env(d: date) -> dict[str, str]:
    iso = f"{d.isoformat()}T12:00:00+0000"
    return {"GIT_AUTHOR_DATE": iso, "GIT_COMMITTER_DATE": iso}


def _merged_env(extra: dict[str, str]) -> dict[str, str]:
    import os
    env = os.environ.copy()
    env.update(extra)
    return env
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_git_ops.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/git_ops.py tests/test_git_ops.py
git commit -m "feat(git_ops): rebuild via orphan-reset + force-push"
```

---

## Task 11 — CLI: `draw` command

**Files:**
- Create: `src/mom/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

`tests/test_cli.py`:
```python
import json
import pytest
from typer.testing import CliRunner
from mom.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_draw_dry_run_json_fit(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake_for_dry_run")
    result = runner.invoke(app, [
        "draw", "HI", "--year", "2024", "--dry-run", "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "preview"
    assert data["fit"]["ok"] is True
    assert data["fit"]["required_cols"] == 7
    assert data["commits"]["total"] == 11 * 20 + 9 * 20   # H(11)+I(9) pixels × 20 = 400
    assert "preview_ascii" in data


def test_draw_dry_run_fit_fail_exits_3(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake_for_dry_run")
    result = runner.invoke(app, [
        "draw", "HELLO WORLD", "--year", "2026",
        "--dry-run", "--format", "json",
    ])
    assert result.exit_code == 3
    data = json.loads(result.output)
    assert data["status"] == "error"
    assert data["error"]["kind"] == "fit_fail"


def test_draw_dry_run_unsupported_char_exits_2(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake_for_dry_run")
    result = runner.invoke(app, [
        "draw", "HI❤", "--year", "2024",
        "--dry-run", "--format", "json",
    ])
    assert result.exit_code == 2
    data = json.loads(result.output)
    assert data["error"]["kind"] == "unsupported_char"


@pytest.fixture
def tmp_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_cli.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `src/mom/cli.py`**

```python
"""Typer CLI."""

from __future__ import annotations
import json as _json
import subprocess
import sys
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional
import typer
from mom import __version__
from mom.errors import (
    AuthError, FitError, MomError, NetworkError,
    NotOurRepoError, UnsupportedCharError,
)
from mom.layout import Canvas, Fit, plan
from mom.preview import render
from mom.config import Config, load, save, resolve_token
from mom.gh import verify_token, verify_email, ensure_repo
from mom.git_ops import rebuild

app = typer.Typer(
    help="Draw text on your GitHub contribution graph.",
    no_args_is_help=True,
    add_completion=False,
)
config_app = typer.Typer(help="Config subcommands.")
app.add_typer(config_app, name="config")


class Format(str, Enum):
    text = "text"
    json = "json"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit(0)


@app.callback()
def _main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True),
    ] = False,
) -> None:
    pass


def _emit_error(fmt: Format, code: int, kind: str, message: str, extra: dict | None = None) -> None:
    if fmt is Format.json:
        payload = {
            "status": "error",
            "error": {"code": code, "kind": kind, "message": message, **(extra or {})},
        }
        typer.echo(_json.dumps(payload))
    else:
        typer.echo(f"✗ {message}", err=True)
    raise typer.Exit(code)


def _git_user_email() -> str:
    r = subprocess.run(
        ["git", "config", "--global", "--get", "user.email"],
        capture_output=True, text=True, check=False,
    )
    return r.stdout.strip()


@app.command()
def draw(
    text: Annotated[str, typer.Argument(help="Text to draw.")],
    year: Annotated[int, typer.Option(help="Target calendar year.")] = date.today().year,
    repo: Annotated[Optional[str], typer.Option(help="Dedicated repo name.")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview + fit check only.")] = False,
    fmt: Annotated[Format, typer.Option("--format", help="Output format.")] = Format.text,
    intensity: Annotated[int, typer.Option(help="Intensity 1-4.")] = 4,
    token: Annotated[Optional[str], typer.Option(help="PAT override.")] = None,
) -> None:
    cfg = load()
    if repo:
        cfg.repo = repo

    # Layout first (pure, cheap, catches fit + char errors without any I/O).
    today = date.today()
    try:
        result = plan(text, year, today, intensity)
    except UnsupportedCharError as e:
        _emit_error(fmt, 2, "unsupported_char", str(e))
    if isinstance(result, Fit):
        # Build a fake preview showing the year's usable window only.
        _emit_error(
            fmt, 3, "fit_fail", str(FitError(result.required, result.available, result.year)),
            extra={"fit": {"ok": False, "required_cols": result.required,
                           "available_cols": result.available, "year": result.year}},
        )
    assert isinstance(result, Canvas)
    canvas: Canvas = result
    preview_ascii = render(canvas)
    total_commits = sum(n for _, n in canvas.cells)
    dates = sorted({d for d, _ in canvas.cells})
    date_range = [dates[0].isoformat(), dates[-1].isoformat()] if dates else []

    payload = {
        "status": "preview" if dry_run else "success",
        "fit": {"ok": True, "required_cols": 4 * len(text) - 1,
                "available_cols": len(canvas.usable_week_indices), "year": year},
        "commits": {"total": total_commits, "date_range": date_range},
        "preview_ascii": preview_ascii,
        "repo_url": None,
        "error": None,
    }

    if dry_run:
        if fmt is Format.json:
            typer.echo(_json.dumps(payload))
        else:
            typer.echo(preview_ascii)
            typer.echo(f"\n{total_commits} commits across {len(dates)} dates (dry-run).")
        raise typer.Exit(0)

    # Auth + GitHub calls.
    try:
        tok = resolve_token(token)
        user = verify_token(tok)
        if not cfg.github_user:
            cfg.github_user = user
            save(cfg)
        git_email = _git_user_email()
        if git_email:
            verify_email(tok, git_email)
        clone_url, html_url = ensure_repo(tok, user, cfg.repo)
        # Inject token into push URL in-memory.
        auth_clone = clone_url.replace("https://", f"https://x-access-token:{tok}@")
    except AuthError as e:
        _emit_error(fmt, 4, e.kind, str(e))
    except NetworkError as e:
        _emit_error(fmt, 5, "network", str(e))

    # Confirm (skipped by --yes).
    if not yes and fmt is Format.text:
        typer.echo(preview_ascii)
        typer.echo(f"\n{total_commits} commits across {len(dates)} dates.")
        ok = typer.confirm("Proceed?")
        if not ok:
            raise typer.Exit(0)

    # Execute.
    try:
        work_dir = Path.home() / ".cache" / "mom" / cfg.repo
        rebuild(
            work_dir=work_dir,
            remote_url=auth_clone,
            year=year,
            canvas=canvas,
            action="upsert",
            today=today,
        )
    except NotOurRepoError as e:
        _emit_error(fmt, 1, "not_our_repo", str(e))
    except subprocess.CalledProcessError as e:
        _emit_error(fmt, 5, "push_rejected", f"git failed: {e.stderr[:500]}")

    payload["repo_url"] = html_url
    payload["status"] = "success"
    if fmt is Format.json:
        typer.echo(_json.dumps(payload))
    else:
        typer.echo(f"Done. View at {html_url}/graphs/contribution-activity")
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_cli.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/cli.py tests/test_cli.py
git commit -m "feat(cli): draw command with JSON/text output"
```

---

## Task 12 — CLI: `clean`, `preview`, `config` subcommands

**Files:**
- Modify: `src/mom/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_cli.py`:
```python
def test_preview_is_alias_for_dry_run(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake")
    r1 = runner.invoke(app, ["preview", "HI", "--year", "2024", "--format", "json"])
    r2 = runner.invoke(app, ["draw", "HI", "--year", "2024", "--dry-run", "--format", "json"])
    assert r1.exit_code == 0
    d1, d2 = json.loads(r1.output), json.loads(r2.output)
    assert d1["fit"] == d2["fit"]
    assert d1["preview_ascii"] == d2["preview_ascii"]


def test_config_set_token_persists(tmp_xdg):
    result = runner.invoke(app, ["config", "set-token", "ghp_new"])
    assert result.exit_code == 0
    result2 = runner.invoke(app, ["config", "show"])
    assert "ghp_new" not in result2.output   # redacted
    assert "(set)" in result2.output or "***" in result2.output


def test_config_check_auth_missing(tmp_xdg, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Mock gh CLI to fail.
    def fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.invoke(app, ["config", "check", "--format", "json"])
    assert result.exit_code == 4
    data = json.loads(result.output)
    assert data["error"]["kind"] == "auth_missing"
```

- [ ] **Step 2: Run tests — expect fail**

```bash
pytest tests/test_cli.py -v -k "preview or config"
```
Expected: fail (commands don't exist).

- [ ] **Step 3: Append to `src/mom/cli.py`**

```python
@app.command()
def preview(
    text: Annotated[str, typer.Argument()],
    year: Annotated[int, typer.Option()] = date.today().year,
    fmt: Annotated[Format, typer.Option("--format")] = Format.text,
    intensity: Annotated[int, typer.Option()] = 4,
) -> None:
    """Alias for `draw --dry-run`."""
    today = date.today()
    try:
        result = plan(text, year, today, intensity)
    except UnsupportedCharError as e:
        _emit_error(fmt, 2, "unsupported_char", str(e))
    if isinstance(result, Fit):
        _emit_error(fmt, 3, "fit_fail",
                    str(FitError(result.required, result.available, result.year)),
                    extra={"fit": {"ok": False, "required_cols": result.required,
                                   "available_cols": result.available, "year": result.year}})
    assert isinstance(result, Canvas)
    preview_ascii = render(result)
    total = sum(n for _, n in result.cells)
    dates = sorted({d for d, _ in result.cells})
    payload = {
        "status": "preview",
        "fit": {"ok": True, "required_cols": 4 * len(text) - 1,
                "available_cols": len(result.usable_week_indices), "year": year},
        "commits": {"total": total,
                    "date_range": [dates[0].isoformat(), dates[-1].isoformat()] if dates else []},
        "preview_ascii": preview_ascii, "repo_url": None, "error": None,
    }
    if fmt is Format.json:
        typer.echo(_json.dumps(payload))
    else:
        typer.echo(preview_ascii)


@app.command()
def clean(
    year: Annotated[int, typer.Option(help="Year to remove.")],
    repo: Annotated[Optional[str], typer.Option()] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
    fmt: Annotated[Format, typer.Option("--format")] = Format.text,
    token: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Remove a year's drawing from the dedicated repo."""
    cfg = load()
    if repo:
        cfg.repo = repo
    try:
        tok = resolve_token(token)
        user = verify_token(tok)
        clone_url, html_url = ensure_repo(tok, user, cfg.repo)
        auth_clone = clone_url.replace("https://", f"https://x-access-token:{tok}@")
    except AuthError as e:
        _emit_error(fmt, 4, e.kind, str(e))
    except NetworkError as e:
        _emit_error(fmt, 5, "network", str(e))

    if not yes and fmt is Format.text:
        if not typer.confirm(f"Remove year {year} from {cfg.repo}?"):
            raise typer.Exit(0)

    today = date.today()
    try:
        work_dir = Path.home() / ".cache" / "mom" / cfg.repo
        rebuild(
            work_dir=work_dir, remote_url=auth_clone,
            year=year, canvas=None, action="delete", today=today,
        )
    except NotOurRepoError as e:
        _emit_error(fmt, 1, "not_our_repo", str(e))
    except subprocess.CalledProcessError as e:
        _emit_error(fmt, 5, "push_rejected", f"git failed: {e.stderr[:500]}")

    if fmt is Format.json:
        typer.echo(_json.dumps({"status": "success", "repo_url": html_url, "year_removed": year}))
    else:
        typer.echo(f"Removed year {year}. View at {html_url}")


@config_app.command("check")
def config_check(
    fmt: Annotated[Format, typer.Option("--format")] = Format.text,
    token: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Exit 0 if auth is resolvable and the configured repo is reachable."""
    try:
        tok = resolve_token(token)
        user = verify_token(tok)
    except AuthError as e:
        _emit_error(fmt, 4, e.kind, str(e))
    except NetworkError as e:
        _emit_error(fmt, 5, "network", str(e))
    if fmt is Format.json:
        typer.echo(_json.dumps({"status": "ok", "github_user": user, "error": None}))
    else:
        typer.echo(f"OK — authenticated as {user}")


@config_app.command("set-token")
def config_set_token(token: str) -> None:
    """Persist a PAT to the config file."""
    cfg = load()
    cfg.token = token
    save(cfg)
    typer.echo("Token saved to config.")


@config_app.command("show")
def config_show() -> None:
    """Print config (token redacted)."""
    cfg = load()
    display = {
        "repo": cfg.repo,
        "github_user": cfg.github_user,
        "token": "***" if cfg.token else "(not set)",
    }
    typer.echo(_json.dumps(display, indent=2))
```

- [ ] **Step 4: Run tests — expect pass**

```bash
pytest tests/test_cli.py -v
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/mom/cli.py tests/test_cli.py
git commit -m "feat(cli): clean, preview, config subcommands"
```

---

## Task 13 — Claude Skill File (`skill/SKILL.md`)

**Files:**
- Create: `skill/SKILL.md`

No tests (the skill is a markdown prompt, not executable code — its correctness is checked in Task 15 by inspection and during install).

- [ ] **Step 1: Write `skill/SKILL.md`**

```markdown
---
name: mom-canvas
description: Draw text on the user's GitHub contribution graph. Use when user
  invokes /mom-canvas <text>, or asks to "write/draw text on my GitHub graph".
  Creates/updates a dedicated GitHub repo with backdated empty commits forming
  pixel-art letters in the 7-row contribution grid. Full ASCII supported,
  auto-centered, validates fit against year capacity.
---

# mom-canvas

User invokes as `/mom-canvas TEXT [--year YYYY]`. Execute steps IN ORDER.
Any non-zero exit halts the flow — surface the error, do NOT proceed.

## Step 1 — Parse input
Extract TEXT (required, everything up to `--year`). Extract `--year YYYY`
(optional; default = current year).

## Step 2 — Ensure CLI is installed
Run: `command -v mom >/dev/null 2>&1 && mom --version`

If the command fails:
1. Tell user: "Installing the mom CLI (one-time setup)…"
2. Run: `pipx install git+https://github.com/mark-ssd/mom`
3. Retry `mom --version`. If still failing, surface the install error and STOP.

## Step 3 — Ensure auth is configured
Run: `mom config check --format json`

Parse the JSON:
- `status == "ok"` → proceed to Step 4.
- `error.kind == "auth_missing"`:
    1. Ask user: "I need a GitHub Personal Access Token with `repo` scope.
       Create one at
       https://github.com/settings/tokens/new?scopes=repo&description=mom-canvas
       and paste it here. It'll be saved to ~/.config/mom/config.json
       (chmod 600; never sent anywhere else)."
    2. Once user pastes, run: `mom config set-token <TOKEN>` (pass token as argv, not interpolated into a shell string).
    3. Re-run `mom config check --format json`. Proceed if ok; otherwise surface error.
- `error.kind == "auth_invalid"` or `"auth_scope"`: surface the error
    message verbatim, tell the user to regenerate the PAT with `repo`
    scope, and STOP.
- `error.kind == "email_mismatch"`: surface the error verbatim and STOP.
    The user must fix `git config user.email` themselves — do NOT auto-edit git config.

## Step 4 — Preview + fit check
Run: `mom draw "$TEXT" --year $YEAR --dry-run --format json`

Parse JSON:
- `fit.ok == false`:
    1. Show the user the `preview_ascii` block in a ```` ``` ```` code fence.
    2. Show the `error.message` (which includes required/available cols and max-char suggestion).
    3. STOP.
- `fit.ok == true`:
    1. Show `preview_ascii` verbatim in a ```` ``` ```` code fence.
    2. Summarize: "N commits across M dates on year Y. Proceed?"
    3. Wait for explicit yes. Do NOT proceed without it.

## Step 5 — Execute
On confirmation, run: `mom draw "$TEXT" --year $YEAR --yes --format json`

Parse JSON:
- `status == "success"`: tell user: "Done. View your canvas at `<repo_url>`.
    The contribution graph updates within a few minutes."
- `status == "error"`: surface `error.message` + `error.code`. STOP.

## Removal
If the user asks to remove a drawing, suggest: `mom clean --year YYYY`.
Run it only after explicit confirmation. Mirror the same auth/error handling.

## Safety
- Always pass TEXT as a single argv element. Never interpolate user input into
  a shell command string.
- Always use `--format json` from this skill. Text mode is for human CLI use.
- Never modify `git config` on the user's behalf.
- Never write the user's PAT to disk outside of `mom config set-token`.
```

- [ ] **Step 2: Verify frontmatter is valid YAML**

```bash
python3 -c "import yaml; print(yaml.safe_load(open('skill/SKILL.md').read().split('---')[1]))"
```
Expected: dict with `name` and `description` keys printed.

(If `yaml` isn't installed, `pip install pyyaml` once.)

- [ ] **Step 3: Commit**

```bash
git add skill/SKILL.md
git commit -m "feat(skill): add Claude skill instructions"
```

---

## Task 14 — README.md (install + usage)

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# mom-canvas

Draw text on your GitHub contribution graph. A CLI plus a Claude Skill.

## What it does

Give it a string like `HELLO WORLD`. It renders the text as pixel art in a
7-row × N-column grid (GitHub's contribution calendar), then materialises
the drawing as backdated empty commits in a dedicated GitHub repo. Once pushed,
the text appears on your profile graph.

## Install (with Claude)

Ask Claude:

> install the mom-canvas skill from https://github.com/mark-ssd/mom

Claude will:
1. `git clone https://github.com/mark-ssd/mom /tmp/mom-install`
2. Copy `/tmp/mom-install/skill/SKILL.md` to `~/.claude/skills/mom-canvas/SKILL.md`
3. Install the CLI with `pipx install /tmp/mom-install`
4. Verify with `mom --version`

Then invoke anytime:

    /mom-canvas HELLO WORLD

Claude will handle the first-run PAT prompt, show you the preview, and
ask for confirmation before committing anything.

## Install (CLI-only, no Claude)

```bash
pipx install git+https://github.com/mark-ssd/mom
mom config set-token ghp_your_personal_access_token
mom draw "HELLO WORLD" --year 2024
```

## Requirements

- Python 3.10+
- git
- A GitHub Personal Access Token with `repo` scope
- `git config --global user.email` must be one of your verified GitHub emails
  (otherwise commits don't count toward your contribution graph)

## Commands

| Command | Purpose |
|---|---|
| `mom draw TEXT --year YYYY` | Plan + preview + confirm + commit + push |
| `mom preview TEXT --year YYYY` | Alias for `draw --dry-run` |
| `mom clean --year YYYY` | Remove a year's drawing |
| `mom config check` | Verify auth is working |
| `mom config set-token TOKEN` | Save a PAT to config |
| `mom config show` | Print config (token redacted) |

## Character set

Printable ASCII U+0020 through U+007E (95 chars): `A-Z a-z 0-9` plus
punctuation and symbols. Lowercase renders identically to uppercase — 3×5
bitmaps are too small for meaningful case distinction.

## How capacity works

Each letter is 3 cols wide with 1-col spacing, so `required_cols = 4N - 1`
for N characters. The GitHub year view has ~52 usable columns for past
years and fewer for the current year (only weeks whose Saturday has already
passed count). The CLI prints the exact available capacity on a fit failure.

## Safety

- Refuses to touch any repo that doesn't have `.mom-state.json` with
  `managed_by: "mom"` — so pointing `--repo` at a real repo is a no-op.
- Force-push is used on the dedicated repo only.
- Tokens are never written to `.git/config`; they live in memory during
  pushes and in `~/.config/mom/config.json` (chmod 600) at rest.

## License

MIT.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with install and usage"
```

---

## Task 15 — Opt-in End-to-End Integration Test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write the live test**

`tests/test_e2e.py`:
```python
"""End-to-end test against a real GitHub sandbox account.

Gated behind `@pytest.mark.live`. Not run in CI. To run locally:

    export MOM_E2E_TOKEN=ghp_...
    export MOM_E2E_USER=<sandbox-login>
    export MOM_E2E_REPO=mom-canvas-sandbox
    pytest tests/test_e2e.py -m live -v

The test draws "HI" on year 2022 and verifies the repo ends up with the
expected commit dates.
"""

import os
import subprocess
import pytest
from typer.testing import CliRunner
from mom.cli import app

runner = CliRunner()
pytestmark = pytest.mark.live


@pytest.fixture
def env():
    tok = os.environ.get("MOM_E2E_TOKEN")
    user = os.environ.get("MOM_E2E_USER")
    repo = os.environ.get("MOM_E2E_REPO", "mom-canvas-sandbox")
    if not tok or not user:
        pytest.skip("MOM_E2E_TOKEN and MOM_E2E_USER required")
    return tok, user, repo


def test_draw_and_clean_lifecycle(env):
    tok, user, repo = env
    # Draw.
    result = runner.invoke(app, [
        "draw", "HI", "--year", "2022", "--repo", repo,
        "--yes", "--format", "json", "--token", tok,
    ])
    assert result.exit_code == 0, result.output
    # Clean.
    result = runner.invoke(app, [
        "clean", "--year", "2022", "--repo", repo,
        "--yes", "--format", "json", "--token", tok,
    ])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Verify the marker skips by default**

```bash
pytest tests/test_e2e.py -v
```
Expected: all `live`-marked tests deselected (pytest shows `1 deselected`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: opt-in e2e test against real GitHub"
```

---

## Task 16 — Final integration check

This task runs the full suite, manually exercises a dry-run, and tidies loose ends.

- [ ] **Step 1: Full test suite passes**

```bash
pytest -v
```
Expected: all non-live tests pass, live tests deselected.

- [ ] **Step 2: Coverage check on pure modules**

```bash
pytest --cov=mom --cov-report=term-missing tests/test_font.py tests/test_layout.py tests/test_preview.py tests/test_config.py
```
Expected: >90% coverage on `font`, `layout`, `preview`, `config`.

- [ ] **Step 3: Manual dry-run smoke test**

```bash
mom draw "HI" --year 2024 --dry-run --format text
```
Expected: preview prints showing "HI" centered in the 2024 grid, 7 weekday rows with `█` and `·`.

- [ ] **Step 4: Manual fit-fail smoke test**

```bash
mom draw "SUPERCALIFRAGILISTIC" --year 2026 --dry-run --format json | python3 -m json.tool
```
Expected: exit 3, JSON with `error.kind == "fit_fail"` and numbers matching the current date.

- [ ] **Step 5: Final commit**

No code changes expected here. If linting/formatting adjustments are needed:

```bash
git add -u
git commit -m "chore: final integration polish"
```

Otherwise skip.

---

## Summary

| # | Task | Outcome |
|---|---|---|
| 1 | Scaffolding | pyproject, package dirs, LICENSE |
| 2 | errors.py | Exception hierarchy |
| 3 | font.py | 3×5 glyph table (full ASCII) |
| 4 | layout.py pt 1 | Canvas/Fit + usable_weeks |
| 5 | layout.py pt 2 | required_cols + check_fit |
| 6 | layout.py pt 3 | plan() |
| 7 | preview.py | ASCII renderer |
| 8 | config.py | Config + auth resolution |
| 9 | gh.py | GitHub REST client |
| 10 | git_ops.py | rebuild() |
| 11 | cli.py pt 1 | draw command |
| 12 | cli.py pt 2 | clean, preview, config subcommands |
| 13 | skill/SKILL.md | Claude Skill file |
| 14 | README.md | Install + usage docs |
| 15 | test_e2e.py | Opt-in e2e test |
| 16 | Integration check | Full suite + manual smoke |

**TDD throughout.** Every source task opens with a failing test. Every impure module (gh, git_ops, config) is tested with either mocks (`responses`) or tmp-dir integration (bare-repo fixture). Pure modules are exercised exhaustively with pinned `today` dates so results are deterministic.
