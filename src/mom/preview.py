"""ASCII renderer for Canvas to terminal-friendly preview."""

from datetime import date, timedelta
from mom.layout import Canvas

_DAY_LABELS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def render(canvas: Canvas) -> str:
    """Render a Canvas as an ASCII grid with month header and weekday rows."""
    total_cols = 54

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
        # Use Monday of that week to identify "first week of month"
        col_date = canvas.grid_start + timedelta(weeks=col, days=1)
        if col_date.day <= 7 and col_date.year == canvas.year:
            month_str = _MONTHS[col_date.month - 1]
            for i, c in enumerate(month_str):
                if col + i < total_cols:
                    header_cells[col + i] = c

    lines: list[str] = []
    lines.append("        " + "".join(header_cells))
    for row, label in enumerate(_DAY_LABELS):
        row_chars = ["\u2588" if grid[row][c] else "\u00b7" for c in range(total_cols)]
        lines.append(f"{label}     " + "".join(row_chars))
    return "\n".join(lines)
