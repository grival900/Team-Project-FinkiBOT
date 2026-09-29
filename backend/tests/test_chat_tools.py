from unittest.mock import MagicMock, patch

from backend.core import chat_tools
from backend.core.chat_tools import _strip_academic_title, build_chat_tools, find_courses_taught_by
from backend.core.retrieval import SearchResult


def _result(**overrides) -> SearchResult:
    defaults = dict(
        document_id="doc-1",
        title="Title",
        url="https://example.com",
        source="official",
        type="announcement",
        published_at=None,
        chunk_text="chunk",
        score=0.5,
    )
    return SearchResult(**{**defaults, **overrides})


def test_strip_academic_title_removes_dr_prefix():
    assert _strip_academic_title("д-р Слободан Калајџиски") == "Слободан Калајџиски"


def test_strip_academic_title_removes_mr_prefix_with_stray_period():
    assert _strip_academic_title("м-р. Александар Тенев") == "Александар Тенев"


def test_strip_academic_title_leaves_a_bare_name_untouched():
    assert _strip_academic_title("Костадин Мишев") == "Костадин Мишев"


def _course_row(title: str, url: str = "https://x/") -> MagicMock:
    row = MagicMock()
    row.title = title
    row.url = url
    return row


def test_find_courses_taught_by_strips_honorific_before_matching():
    # finki-hub course pages never include the "д-р"
    db = MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = [
        _course_row("Дискретна математика")
    ]

    result = find_courses_taught_by(db, "д-р Слободан Калајџиски")

    assert result == [{"title": "Дискретна математика", "url": "https://x/"}]


def test_find_courses_taught_by_matches_a_longer_finki_hub_name_form():
    # finki-hub has the longer "Магдалена Костоска Ѓорчевска"
    db = MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = [_course_row("Курс")]

    result = find_courses_taught_by(db, "д-р Магдалена Костоска")

    assert result == [{"title": "Курс", "url": "https://x/"}]


def test_find_courses_taught_by_returns_empty_for_a_name_with_no_tokens():
    db = MagicMock()

    assert find_courses_taught_by(db, "   ") == []
    db.query.assert_not_called()


def test_build_chat_tools_returns_the_expected_tool_names():
    tools = build_chat_tools(MagicMock(), min_score=0.3, collected=[])
    names = {t.__name__ for t in tools}

    assert names == {
        "search_announcements",
        "get_course_info",
        "get_professor_info",
        "search_faculty_info",
        "get_exam_schedule_reference",
        "search_courses",
        "search_staff",
        "search_consultations",
        "search_materials",
        "search_exam_sessions",
        "find_courses_taught_by",
        "find_exam_dates_for_professor",
        "find_exam_dates_for_course",
        "search_official_documents",
        "search_theses",
        "thesis_stats",
        "live_site_search",
    }


def test_search_tool_delegates_to_search_with_the_right_source_and_type():
    hit = _result(document_id="d1", type="course", score=0.7)
    collected: list[SearchResult] = []

    with patch.object(chat_tools, "search", return_value=[hit]) as mock_search:
        tools = build_chat_tools(MagicMock(), min_score=0.4, collected=collected)
        search_courses = next(t for t in tools if t.__name__ == "search_courses")
        out = search_courses("бази на податоци", limit=3)

    mock_search.assert_called_once()
    _, kwargs = mock_search.call_args
    assert kwargs["source"] == "finki_hub"
    assert kwargs["type"] == "course"
    assert kwargs["k"] == 3
    assert kwargs["min_score"] == 0.4
    assert kwargs["recency_boost"] is True
    assert out == [
        {
            "title": "Title",
            "url": "https://example.com",
            "type": "course",
            "published_at": None,
            "excerpt": "chunk",
            "score": 0.7,
        }
    ]
    # results must reach the caller so they can be cited
    assert collected == [hit]


def test_find_courses_taught_by_tool_uses_the_shared_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.limit.return_value.all.return_value = [_course_row("Курс")]
    tools = build_chat_tools(db, min_score=0.3, collected=[])
    tool = next(t for t in tools if t.__name__ == "find_courses_taught_by")

    assert tool("Костадин Мишев") == [{"title": "Курс", "url": "https://x/"}]


def test_live_site_search_tool_delegates_to_the_live_mcp_search():
    with patch.object(chat_tools, "search_official_site_live", return_value=[{"title": "X"}]) as mock_live:
        tools = build_chat_tools(MagicMock(), min_score=0.3, collected=[])
        live_site_search = next(t for t in tools if t.__name__ == "live_site_search")
        out = live_site_search("испитна сесија", limit=2)

    mock_live.assert_called_once_with("испитна сесија", limit=2)
    assert out == [{"title": "X"}]
