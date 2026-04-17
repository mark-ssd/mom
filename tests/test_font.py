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
