from datetime import datetime
from pathlib import Path

from backend.ingestion.file_extraction import extract_pdf_text, extract_xlsx_schedule_grid

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_pdf_text_returns_readable_text():
    data = (FIXTURES / "sample_exam_schedule.pdf").read_bytes()
    text = extract_pdf_text(data)

    # old PDF format: a flat Предмет/Термин/Простории table
    assert "Дискретна математика" in text
    assert "лаб" in text


def test_extract_xlsx_schedule_grid_collapses_merged_slots_into_one_line_per_course():
    data = (FIXTURES / "sample_exam_schedule.xlsx").read_bytes()
    text, published_at = extract_xlsx_schedule_grid(data)
    lines = text.splitlines()

    # the fixture has sheets 08.06.2026 and 09.06.2026
    assert published_at == datetime(2026, 6, 8)

    # 2 days cut from a real file: one [record] per course per day, not one per half hour
    matching = [line for line in lines if "Дистрибуирани системи" in line]
    assert len(matching) == 1
    # rows 08:00 and 08:30 -> ends at 09:00, not 08:30
    assert matching[0] == "[08.06.2026 08:00-09:00 117: Дистрибуирани системи]"

    # several rooms at once -> one record listing all rooms
    interactive_lines = [line for line in lines if "Интерактивни апликации" in line]
    assert len(interactive_lines) == 1
    assert "лаб. 2" in interactive_lines[0]
    assert "лаб. 3" in interactive_lines[0]

    # Two distinct sheets (days) both contributed records.
    assert any(line.startswith("[08.06.2026") for line in lines)
    assert any(line.startswith("[09.06.2026") for line in lines)


def test_extract_xlsx_schedule_grid_splits_disjoint_same_course_occurrences():
    # a morning and an afternoon group of the same course are two records, not 08:00-17:00
    import io
    from datetime import time as dtime

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "10.09.2026"
    ws["B2"] = "лаб. 1"
    ws["A3"] = dtime(8, 0)
    ws["B3"] = "Оперативни системи"
    # gives the sheet a 30 min step; otherwise the only gap would be the 6 hours below
    ws["A4"] = dtime(8, 30)
    ws["B4"] = "Друг предмет"
    ws["A5"] = dtime(14, 0)
    ws["B5"] = "Оперативни системи"
    buf = io.BytesIO()
    wb.save(buf)

    text, _ = extract_xlsx_schedule_grid(buf.getvalue())
    lines = text.splitlines()

    matching = [line for line in lines if "Оперативни системи" in line]
    assert len(matching) == 2
    assert "[10.09.2026 08:00-08:30 лаб. 1: Оперативни системи]" in matching
    assert "[10.09.2026 14:00-14:30 лаб. 1: Оперативни системи]" in matching


def test_extract_xlsx_schedule_grid_skips_sheets_whose_title_is_not_a_plain_date():
    # "b-25.06.2026" sheets were leftovers copied between files
    import io
    from datetime import time as dtime

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "10.09.2026"
    ws["B2"] = "лаб. 1"
    ws["A3"] = dtime(8, 0)
    ws["B3"] = "Структурно програмирање"

    stray = wb.create_sheet("b-25.06.2026")
    stray["B2"] = "лаб. 13"
    stray["A3"] = dtime(15, 0)
    stray["B3"] = "Маркетинг"

    buf = io.BytesIO()
    wb.save(buf)

    text, published_at = extract_xlsx_schedule_grid(buf.getvalue())

    assert "Структурно програмирање" in text
    assert "Маркетинг" not in text
    assert published_at == datetime(2026, 9, 10)


def test_extract_xlsx_schedule_grid_reads_a_color_filled_block_with_no_merge():
    # like "Структурно програмирање" in the real September file: a red block, only the
    # top-left cell has text
    import io

    import openpyxl
    from openpyxl.styles import PatternFill
    from datetime import time as dtime

    red = PatternFill(fill_type="solid", fgColor="FFFF0000")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "10.09.2026"
    ws["B2"] = "лаб. 1"
    ws["C2"] = "лаб. 2"
    for row, t in ((3, dtime(8, 0)), (4, dtime(8, 30)), (5, dtime(9, 0))):
        ws.cell(row=row, column=1, value=t)
        ws.cell(row=row, column=2).fill = red
        ws.cell(row=row, column=3).fill = red
    ws["B3"] = "Структурно програмирање"  # the only cell that actually has the text
    buf = io.BytesIO()
    wb.save(buf)

    text, _ = extract_xlsx_schedule_grid(buf.getvalue())
    lines = [line for line in text.splitlines() if "Структурно програмирање" in line]

    assert len(lines) == 1
    assert lines[0] == "[10.09.2026 08:00-09:30 лаб. 1, лаб. 2: Структурно програмирање]"


def test_extract_xlsx_schedule_grid_color_block_does_not_cross_a_different_course():
    # another booking ("Гости Израел") cut out of the middle of the colored block
    import io

    import openpyxl
    from openpyxl.styles import PatternFill
    from datetime import time as dtime

    red = PatternFill(fill_type="solid", fgColor="FFFF0000")
    blue = PatternFill(fill_type="solid", fgColor="FF0000FF")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "11.09.2026"
    ws["B2"] = "лаб. 1"
    ws["C2"] = "лаб. 2"
    for row, t in ((3, dtime(8, 0)), (4, dtime(8, 30)), (5, dtime(9, 0))):
        ws.cell(row=row, column=1, value=t)
    for row in (3, 4, 5):
        ws.cell(row=row, column=2).fill = red
    ws.cell(row=3, column=3).fill = red
    ws.cell(row=5, column=3).fill = red
    ws["B3"] = "Курс А"
    ws["C4"] = "Друг курс"  # a real, unrelated booking carved out of the block
    ws.cell(row=4, column=3).fill = blue
    buf = io.BytesIO()
    wb.save(buf)

    text, _ = extract_xlsx_schedule_grid(buf.getvalue())
    lines = text.splitlines()

    course_a = next(line for line in lines if "Курс А" in line)
    assert course_a == "[11.09.2026 08:00-09:30 лаб. 1, лаб. 2: Курс А]"
    other = next(line for line in lines if "Друг курс" in line)
    assert other == "[11.09.2026 08:30-09:00 лаб. 2: Друг курс]"


def test_extract_xlsx_schedule_grid_empty_workbook_returns_empty_string_and_no_date():
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    buf = io.BytesIO()
    wb.save(buf)

    assert extract_xlsx_schedule_grid(buf.getvalue()) == ("", None)


def test_extract_xlsx_schedule_grid_published_at_is_robust_to_one_mistyped_sheet():
    # a typo'd "16.06.2025" sheet between 2026 ones must not move the session to 2025
    import io
    from datetime import time as dtime

    import openpyxl

    wb = openpyxl.Workbook()
    del wb["Sheet"]
    day_titles = ["08.06.2026", "09.06.2026", "10.06.2026", "16.06.2025", "17.06.2026", "18.06.2026"]
    for title in day_titles:
        ws = wb.create_sheet(title=title)
        ws["B2"] = "лаб. 3"
        ws["A3"] = dtime(8, 0)
        ws["B3"] = "Тест предмет"
    buf = io.BytesIO()
    wb.save(buf)

    _, published_at = extract_xlsx_schedule_grid(buf.getvalue())

    assert published_at is not None
    assert published_at.year == 2026


def test_extract_xlsx_schedule_grid_parses_single_digit_day_month_sheet_title():
    # some sheets are titled "5.6.2023" instead of "05.06.2023"
    import io
    from datetime import time as dtime

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "5.6.2023"
    ws["B2"] = "лаб. 3"
    ws["A3"] = dtime(8, 0)
    ws["B3"] = "Тест предмет"
    buf = io.BytesIO()
    wb.save(buf)

    text, published_at = extract_xlsx_schedule_grid(buf.getvalue())

    assert published_at == datetime(2023, 6, 5)
    assert "5.6.2023" in text
