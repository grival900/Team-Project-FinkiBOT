from datetime import datetime, timezone

from backend.api.routers.chat import strip_model_sources
from backend.core.chat_ranking import prefer_current_year
from backend.core.chat_sources import (
    build_context,
    build_sources_block,
    citation_url,
    live_results_to_search_results,
    model_sources_start,
    pick_source,
    source_label,
)
from backend.core.config import get_settings
from backend.core.retrieval import SearchResult

_FRONTEND_ORIGIN = get_settings().frontend_origin


def _result(**overrides) -> SearchResult:
    defaults = dict(
        document_id="doc-1",
        title="Title",
        url="https://example.com/original",
        source="official",
        type="announcement",
        published_at=None,
        chunk_text="chunk text",
        score=0.5,
    )
    return SearchResult(**{**defaults, **overrides})


def _dated(year: int, **overrides) -> SearchResult:
    return _result(published_at=datetime(year, 6, 1, tzinfo=timezone.utc), **overrides)


# --- ranking ------------------------------------------------------------------------


def test_prefer_current_year_drops_older_years_when_current_year_matches_exist():
    results = [
        _dated(2026, document_id="new", score=0.7),
        _dated(2014, document_id="old-1", score=0.9),
        _dated(2019, document_id="old-2", score=0.8),
    ]

    kept = prefer_current_year(results, k=6, current_year=2026)

    assert [r.document_id for r in kept] == ["new"]


def test_prefer_current_year_falls_back_to_older_years_when_none_match():
    results = [
        _dated(2014, document_id="old-1", score=0.6),
        _dated(2019, document_id="old-2", score=0.9),
    ]

    kept = prefer_current_year(results, k=6, current_year=2026)

    assert [r.document_id for r in kept] == ["old-2", "old-1"]


def test_prefer_current_year_always_keeps_undated_results():
    results = [
        _dated(2014, document_id="old-announcement", score=0.95),
        _result(document_id="course", type="course", published_at=None, score=0.5),
    ]

    kept = prefer_current_year(results, k=6, current_year=2026)

    assert {r.document_id for r in kept} == {"old-announcement", "course"}


def test_prefer_current_year_drops_old_undated_schedule_using_academic_year_metadata():
    # old PDF sessions have no published_at, only "academic_year" in metadata
    current = _dated(2026, document_id="current-schedule", type="schedule", score=0.6)
    stale = _result(
        document_id="stale-schedule",
        type="schedule",
        published_at=None,
        score=0.95,
        metadata={"academic_year": "2021/2022"},
    )
    course = _result(document_id="course", type="course", published_at=None, score=0.5)

    kept = prefer_current_year([current, stale, course], k=6, current_year=2026)

    assert {r.document_id for r in kept} == {"current-schedule", "course"}


def test_prefer_current_year_prefers_the_schedule_session_closest_to_today():
    # "кога се полага структурно програмирање" used to return January/June, not September
    now = datetime(2026, 9, 14, tzinfo=timezone.utc)
    stale_january = _dated(
        2026, document_id="january", type="schedule", score=0.60, chunk_text="[15.01.2026 08:00 лаб. 2: СП]"
    )
    stale_june = _dated(
        2026, document_id="june", type="schedule", score=0.60, chunk_text="[16.06.2026 08:00 лаб. 2: СП]"
    )
    live_september = _dated(
        2026, document_id="september", type="schedule", score=0.58, chunk_text="[03.09.2026 08:00 лаб. 2: СП]"
    )

    kept = prefer_current_year([stale_january, stale_june, live_september], k=1, current_year=2026, now=now)

    assert [r.document_id for r in kept] == ["september"]


def test_prefer_current_year_respects_k():
    results = [_dated(2026, document_id=f"new-{i}", score=1.0 - i * 0.01) for i in range(10)]

    kept = prefer_current_year(results, k=3, current_year=2026)

    assert [r.document_id for r in kept] == ["new-0", "new-1", "new-2"]


def test_prefer_current_year_boosts_a_current_match_above_higher_scoring_undated_ones():
    # a short current schedule chunk used to lose to long syllabus pages
    schedule_hit = _dated(2026, document_id="schedule", type="schedule", score=0.557)
    syllabus_pages = [
        _result(document_id=f"syllabus-{i}", type="course", published_at=None, score=score)
        for i, score in enumerate([0.635, 0.590, 0.586, 0.579, 0.570])
    ]

    kept = prefer_current_year([schedule_hit, *syllabus_pages], k=6, current_year=2026)

    assert kept[0].document_id == "schedule"
    assert kept[0].score == 0.557  # the bonus only affects ordering


# --- context and labels ---------------------------------------------------------------


def test_citation_url_uses_internal_link_for_finki_hub_courses():
    r = _result(source="finki_hub", type="course", document_id="abc-123")
    assert citation_url(r) == f"{_FRONTEND_ORIGIN}/documents/abc-123"


def test_citation_url_leaves_other_sources_and_types_untouched():
    r = _result(source="official", type="announcement", url="https://finki.ukim.mk/announcements/x/")
    assert citation_url(r) == "https://finki.ukim.mk/announcements/x/"

    r = _result(source="finki_hub", type="material", url="https://snimki.finki-hub.com/courses/x")
    assert citation_url(r) == "https://snimki.finki-hub.com/courses/x"


def test_build_context_embeds_internal_link_for_finki_hub_course():
    results = [_result(source="finki_hub", type="course", document_id="abc-123", title="Бази на податоци")]
    context = build_context(results)
    assert f"{_FRONTEND_ORIGIN}/documents/abc-123" in context
    assert "predmeti.finki-hub.com" not in context


def test_live_results_to_search_results_wraps_title_url_only_hits():
    items = [{"title": "Испитна сесија", "url": "https://finki.ukim.mk/x", "type": "post", "subtype": "schedule"}]

    [r] = live_results_to_search_results(items)

    assert r.title == "Испитна сесија"
    assert r.url == "https://finki.ukim.mk/x"
    assert r.type == "schedule"
    assert r.document_id == "live:https://finki.ukim.mk/x"
    assert r.published_at is None


def test_live_results_to_search_results_skips_items_with_no_url():
    assert live_results_to_search_results([{"title": "No URL"}]) == []


def test_source_label_distinguishes_same_title_across_sites():
    official = _result(
        title="Неструктурирани бази на податоци",
        source="official",
        type="course",
        url="https://www.finki.ukim.mk/mk/subject/F23L3S141",
    )
    finki_hub = _result(title="Неструктурирани бази на податоци", source="finki_hub", type="course", metadata={})

    assert source_label(official) == "Неструктурирани бази на податоци (предмет, finki.ukim.mk)"
    assert source_label(finki_hub) == "Неструктурирани бази на податоци (предмет, finki-hub.com)"


def test_source_label_uses_the_link_host_not_the_source_field():
    staff = _result(
        title="Слободан Калајџиски",
        source="finki_hub",
        type="staff",
        url="https://www.finki.ukim.mk/mk/staff/slobodan-kalajdziski",
    )
    assert source_label(staff) == "Слободан Калајџиски (наставник, finki.ukim.mk)"


def test_build_sources_block_has_one_labelled_link():
    block = build_sources_block(
        _result(title="Т", source="official", type="professor", url="https://finki.ukim.mk/kadar/t/")
    )
    assert "**Извори:**" in block
    assert "- [Т (професор, finki.ukim.mk)](https://finki.ukim.mk/kadar/t/)" in block


def test_build_sources_block_is_empty_without_a_source():
    assert build_sources_block(None) == ""


# --- picking the source ---------------------------------------------------------------


def _schedule(doc_id: str, title: str, text: str, score: float) -> SearchResult:
    return _result(
        document_id=doc_id, title=title, url=f"https://e.com/{doc_id}", type="schedule", chunk_text=text, score=score
    )


def test_pick_source_prefers_the_document_the_answer_quotes_over_the_top_scorer():
    june = _schedule("june", "2025/2026 Јуни", "[22.06.2026 11:30-17:30 лаб. 117: Оперативни системи]", 0.70)
    september = _schedule("sep", "2025/2026 Септември", "[10.09.2026 11:30-17:30 лаб. 117: Оперативни системи]", 0.62)
    syllabus = _result(document_id="os", url="https://e.com/os", type="course", title="Оперативни системи", score=0.75)
    answer = "Испитот по **Оперативни системи** е на 10.09.2026, 11:30-17:30, лаб. 117."

    assert pick_source(answer, [syllabus, june, september]).document_id == "sep"


def test_pick_source_ignores_words_every_candidate_shares():
    a = _result(document_id="a", url="https://e.com/a", chunk_text="испит предмет студенти", score=0.8)
    b = _result(document_id="b", url="https://e.com/b", chunk_text="испит предмет кабинет 222", score=0.5)

    # "испит" is in both, so only "кабинет" and "222" count - and only b has them
    assert pick_source("Кабинет 222, за испит прашајте го професорот.", [a, b]).document_id == "b"


def test_pick_source_returns_none_when_the_answer_matches_nothing():
    a = _result(document_id="a", url="https://e.com/a", chunk_text="распоред за испити", score=0.8)
    b = _result(document_id="b", url="https://e.com/b", chunk_text="упис на студенти", score=0.7)

    assert pick_source("Рекурзија е кога функција се повикува сама себе.", [a, b]) is None
    assert pick_source("anything", []) is None


def test_pick_source_breaks_ties_by_retrieval_score():
    a = _result(document_id="a", url="https://e.com/a", chunk_text="Веб програмирање 02.09.2026", score=0.6)
    b = _result(document_id="b", url="https://e.com/b", chunk_text="Веб програмирање 02.09.2026", score=0.7)
    c = _result(document_id="c", url="https://e.com/c", chunk_text="нешто друго", score=0.9)

    assert pick_source("Веб програмирање е на 02.09.2026.", [a, b, c]).document_id == "b"


def test_pick_source_treats_two_copies_with_one_link_as_one_document():
    shared = "https://www.finki.ukim.mk/mk/subject/F23L3S141"
    official = _result(document_id="official", source="official", type="course", url=shared, score=0.8,
                       chunk_text="ECTS 6 кредити")
    hub = _result(document_id="hub", source="finki_hub", type="course", metadata={"official_subject_url": shared},
                  score=0.7, chunk_text="семестар 5 задолжителен")
    other = _result(document_id="x", url="https://e.com/x", chunk_text="друг предмет", score=0.9)

    # the answer quotes both copies; together they are one source, cited at the shared link
    picked = pick_source("Предметот носи 6 ECTS кредити и е задолжителен во семестар 5.", [official, hub, other])
    assert citation_url(picked) == shared


# --- stripping a model-written source list --------------------------------------------


def test_model_sources_start_finds_a_list_after_a_rule():
    body = "Answer text here.\n\n---\n\n**Извори:**\n- [X](https://e.com)"
    assert body[: model_sources_start(body)].rstrip() == "Answer text here."


def test_model_sources_start_finds_a_bare_heading():
    body = "Одговор.\nSources:\n- x"
    assert body[: model_sources_start(body)].rstrip() == "Одговор."


def test_model_sources_start_ignores_the_word_mid_sentence():
    assert model_sources_start("Постојат два извори за оваа информација и двата се важни.") is None
    assert model_sources_start("Plain answer with no list at all.") is None


def test_strip_model_sources_cuts_a_heading_split_across_chunks():
    chunks = iter(["Одговор е тука.", "\n\n**Изв", "ори:**\n- [X](https://e.com)"])
    assert "".join(strip_model_sources(chunks)).rstrip() == "Одговор е тука."


def test_strip_model_sources_passes_a_normal_answer_through():
    chunks = iter(["Прв дел, ", "втор дел."])
    assert "".join(strip_model_sources(chunks)) == "Прв дел, втор дел."
