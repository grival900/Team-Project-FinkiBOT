"""Turns downloaded files (PDF, XLSX) into text. Used by the exam-session scraper
and by the quiz upload."""

import datetime
import io
import re
from collections import Counter

from openpyxl import load_workbook
from pypdf import PdfReader


def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _normalize_ws(value: str) -> str:
    """Collapses line breaks inside cells ("АМФ \nФИНКИ Г") to single spaces."""
    return re.sub(r"\s+", " ", value).strip()


_SHEET_DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def _parse_sheet_date(title: str) -> datetime.datetime | None:
    """Sheet titles are the exam day: "08.06.2026", sometimes "5.6.2023 (Понеделник)"."""
    match = _SHEET_DATE_RE.match(title.strip())
    if match is None:
        return None
    day, month, year = (int(g) for g in match.groups())
    try:
        return datetime.datetime(year, month, day)
    except ValueError:
        return None


def _slot_duration(times: list[datetime.time]) -> datetime.timedelta:
    """Time between rows in the grid (usually 30 min), needed to work out end times."""
    distinct = sorted(set(times))
    if len(distinct) < 2:
        return datetime.timedelta(minutes=30)
    base = datetime.date(2000, 1, 1)
    gaps = (
        datetime.datetime.combine(base, b) - datetime.datetime.combine(base, a)
        for a, b in zip(distinct, distinct[1:])
    )
    return min(gaps)


def _group_contiguous_runs(
    entries: list[tuple[datetime.time, str]], slot_duration: datetime.timedelta
) -> list[tuple[datetime.time, datetime.time, set[str]]]:
    """Groups a course's (time, room) cells on one day into (start, end, rooms) blocks.
    A gap in time starts a new block (e.g. a morning and an afternoon group); several
    rooms at the same time stay in one block."""
    ordered = sorted(entries, key=lambda e: e[0])
    base = datetime.date(2000, 1, 1)
    runs: list[list[tuple[datetime.time, str]]] = []
    for time_value, room in ordered:
        if runs and (
            datetime.datetime.combine(base, time_value) - datetime.datetime.combine(base, runs[-1][-1][0])
        ) <= slot_duration:
            runs[-1].append((time_value, room))
        else:
            runs.append([(time_value, room)])

    result: list[tuple[datetime.time, datetime.time, set[str]]] = []
    for run in runs:
        start = run[0][0]
        end = (datetime.datetime.combine(base, run[-1][0]) + slot_duration).time()
        rooms = {room for _, room in run}
        result.append((start, end, rooms))
    return result


def _resolve_merged_cells(ws) -> dict[tuple[int, int], object]:
    """Merged cells only hold a value in the top-left cell, so copy it to the rest."""
    overrides: dict[tuple[int, int], object] = {}
    for merged_range in ws.merged_cells.ranges:
        top_left = ws.cell(row=merged_range.min_row, column=merged_range.min_col).value
        if top_left is None:
            continue
        for row in range(merged_range.min_row, merged_range.max_row + 1):
            for col in range(merged_range.min_col, merged_range.max_col + 1):
                overrides[(row, col)] = top_left
    return overrides


def _fill_key(cell) -> tuple | None:
    """Something to compare two cells' background color by (RGB or theme color)."""
    fill = cell.fill
    if fill is None or fill.patternType != "solid":
        return None
    fg = fill.fgColor
    if fg.type == "rgb":
        return ("rgb", fg.rgb)
    if fg.type == "theme":
        return ("theme", fg.theme, fg.tint)
    return None


def _resolve_color_blocks(ws, cell_value, header_row_index: int) -> dict[tuple[int, int], object]:
    """Some sheets mark a course's block only by coloring the cells, without merging
    them - only the top-left cell has the course name. E.g. "Структурно програмирање"
    as a red block over 08:00-14:00 and 9 rooms.

    We flood-fill from each named cell into empty neighbours of the same color. A
    rectangle wouldn't work - blocks can have other bookings cut out of them."""
    rows = range(header_row_index + 1, ws.max_row + 1)
    cols = range(2, ws.max_column + 1)

    def fill_key(row: int, col: int) -> tuple | None:
        return _fill_key(ws.cell(row=row, column=col))

    visited: set[tuple[int, int]] = set()
    overrides: dict[tuple[int, int], object] = {}

    for row in rows:
        for col in cols:
            if (row, col) in visited:
                continue
            value = cell_value(row, col)
            if value in (None, ""):
                continue
            anchor_key = fill_key(row, col)
            if anchor_key is None:
                continue
            visited.add((row, col))
            stack = [(row, col)]
            while stack:
                r, c = stack.pop()
                for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if nr not in rows or nc not in cols or (nr, nc) in visited:
                        continue
                    if cell_value(nr, nc) not in (None, ""):
                        continue
                    if fill_key(nr, nc) != anchor_key:
                        continue
                    visited.add((nr, nc))
                    overrides[(nr, nc)] = value
                    stack.append((nr, nc))
    return overrides


def _representative_date(dates: list[datetime.datetime]) -> datetime.datetime:
    """A date to represent the whole session file: the median of the dates from the
    most common year. The sheets have typos (a "16.06.2025" between two 2026 dates),
    and taking the earliest date put the whole session in the wrong year."""
    year_counts = Counter(d.year for d in dates)
    majority_year, majority_count = year_counts.most_common(1)[0]
    runner_up_count = year_counts.most_common(2)[1][1] if len(year_counts) > 1 else 0
    candidates = [d for d in dates if d.year == majority_year] if majority_count > runner_up_count else dates

    ordered = sorted(candidates)
    return ordered[(len(ordered) - 1) // 2]


def extract_xlsx_schedule_grid(data: bytes) -> tuple[str, datetime.datetime | None]:
    """Reads an exam-session spreadsheet into one line per exam:
        [08.06.2026 11:30-17:30 лаб. 2, лаб. 3: Оперативни системи]

    Layout: one sheet per day (the title is the date), rooms across the header row,
    times down column A, course names in the cells (often merged or colored blocks).

    Returns (text, a representative date for the file)."""
    wb = load_workbook(io.BytesIO(data), data_only=True)
    lines: list[str] = []
    sheet_dates: list[datetime.datetime] = []

    for ws in wb.worksheets:
        date = ws.title.strip()
        parsed_date = _parse_sheet_date(date)
        if parsed_date is None:
            # e.g. "b-25.06.2026" - leftover sheets copied between files, not real data
            continue
        sheet_dates.append(parsed_date)
        overrides = _resolve_merged_cells(ws)

        def cell_value(row: int, col: int):
            if (row, col) in overrides:
                return overrides[(row, col)]
            return ws.cell(row=row, column=col).value

        # row 1 is a banner, the room names are in the row just above the first time
        first_data_row = None
        for row in range(1, ws.max_row + 1):
            if isinstance(cell_value(row, 1), (datetime.time, datetime.datetime)):
                first_data_row = row
                break

        if first_data_row is None or first_data_row == 1:
            continue
        header_row_index = first_data_row - 1
        header = {
            col: _normalize_ws(str(v))
            for col in range(2, ws.max_column + 1)
            if (v := cell_value(header_row_index, col)) not in (None, "")
        }
        if not header:
            continue

        color_overrides = _resolve_color_blocks(ws, cell_value, header_row_index)

        def cell_value_with_color(row: int, col: int):
            value = cell_value(row, col)
            if value not in (None, ""):
                return value
            return color_overrides.get((row, col))

        # course -> (time, room) occurrences, in row order
        occurrences: dict[str, list[tuple[datetime.time, str]]] = {}
        all_row_times: list[datetime.time] = []
        for row in range(header_row_index + 1, ws.max_row + 1):
            time_value = cell_value(row, 1)
            if not isinstance(time_value, (datetime.time, datetime.datetime)):
                continue
            if isinstance(time_value, datetime.datetime):
                time_value = time_value.time()
            all_row_times.append(time_value)

            for col, room in header.items():
                course = cell_value_with_color(row, col)
                if course in (None, "", ".") or not str(course).strip():
                    continue
                course = _normalize_ws(str(course))
                occurrences.setdefault(course, []).append((time_value, room))

        slot_duration = _slot_duration(all_row_times)
        for course, entries in occurrences.items():
            for start, end, rooms in _group_contiguous_runs(entries, slot_duration):
                time_range = f"{start:%H:%M}-{end:%H:%M}"
                rooms_str = ", ".join(sorted(rooms))
                # brackets keep records apart once chunking joins the lines with spaces
                lines.append(f"[{date} {time_range} {rooms_str}: {course}]")

    return "\n".join(lines), (_representative_date(sheet_dates) if sheet_dates else None)
