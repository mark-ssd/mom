"""ASCII renderer for Canvas to terminal-friendly preview."""

from datetime import timedelta
from mom.layout import Canvas

_DAY_LABELS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def render(canvas: Canvas) -> str:
    """Render a Canvas as an ASCII grid with month header and weekday rows."""
    total_cols = 54

    grid = [[False] * total_cols for _ in range(7)]
    for cell_date, _ in canvas.cells:
        offset_days = (cell_date - canvas.window.grid_start).days
        col = offset_days // 7
        row = offset_days % 7
        if 0 <= col < total_cols:
            grid[row][col] = True

    # Month header: place abbreviation at the first column whose Monday is in the
    # first week of a month. Works for both calendar and trailing windows.
    header_cells = [" "] * total_cols
    for col in range(total_cols):
        col_date = canvas.window.grid_start + timedelta(weeks=col, days=1)
        if col_date.day <= 7:
            month_str = _MONTHS[col_date.month - 1]
            for i, c in enumerate(month_str):
                if col + i < total_cols:
                    header_cells[col + i] = c

    lines: list[str] = []
    lines.append("        " + "".join(header_cells))
    for row, label in enumerate(_DAY_LABELS):
        # Use ASCII `#` / `.` -- guaranteed same width in any monospace font.
        # The Unicode block + middle-dot pair can drift in some terminal fonts.
        row_chars = ["#" if grid[row][c] else "." for c in range(total_cols)]
        lines.append(f"{label}     " + "".join(row_chars))
    return "\n".join(lines)
