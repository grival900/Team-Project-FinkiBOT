from datetime import datetime

from backend.core.theses import mentor_matches
from backend.scrapers.finki_hub.thesis_archive import parse_thesis, student_index

_BACHELOR = {
    "dateOfSubmission": "28.09.2026",
    "description": "Во овој труд се истражуваат методи за детекција.",
    "fileId": None,
    "member1": "Иван Китановски",
    "member2": "Ема Пандилова",
    "mentor": "Иван Чорбев",
    "status": "Пријава",
    "student": "221096 - Анастасија Корабоска",
    "title": "Детекција на епилептични напади",
}

_MASTER = {
    "dateOfPresentation": "02.10.2026",
    "description": "Опис на магистерската.",
    "fileId": "1308",
    "member": "Илинка Иваноска",
    "mentor": "Моника Симјаноска Мишева",
    "president": "Катарина Тројачанец Динева",
    "status": "24. Магистерската е завршена.",
    "student": "249039 - Буковец Џансел",
    "title": "Варијабилност на ДНК метилацијата",
}


def test_student_index_drops_the_name():
    assert student_index("221096 - Анастасија Корабоска") == "221096"


def test_parse_thesis_keeps_the_index_but_never_the_student_name():
    doc = parse_thesis(_BACHELOR, "bachelor")

    assert "Корабоска" not in doc.content and "Анастасија" not in doc.content
    assert "Корабоска" not in str(doc.metadata)
    assert doc.metadata["student_index"] == "221096"
    assert "Индекс на студентот: 221096" in doc.content


def test_parse_thesis_bachelor_fields():
    doc = parse_thesis(_BACHELOR, "bachelor")

    assert (doc.type, doc.source, doc.title) == ("thesis", "finki_hub", "Детекција на епилептични напади")
    assert doc.metadata["committee"] == ["Иван Китановски", "Ема Пандилова"]
    assert doc.published_at == datetime(2026, 9, 28)
    assert "pdf_url" not in doc.metadata
    assert "Ментор: Иван Чорбев" in doc.content


def test_parse_thesis_master_fields_and_pdf_link():
    doc = parse_thesis(_MASTER, "master")

    assert doc.content.startswith("Магистерска работа:")
    assert doc.metadata["committee"] == ["Катарина Тројачанец Динева", "Илинка Иваноска"]
    assert doc.metadata["pdf_url"] == "https://magisterski-api.finki-hub.com/masters/download/1308"
    assert doc.url.startswith("https://diplomski.finki-hub.com/masters?thesis=249039-")


def test_parse_thesis_url_does_not_change_when_a_file_is_added():
    without_file = parse_thesis(_BACHELOR, "bachelor")
    with_file = parse_thesis({**_BACHELOR, "fileId": "55", "status": "Одбрана"}, "bachelor")

    assert without_file.url == with_file.url


def test_mentor_matches_by_surname():
    assert mentor_matches("Иван Чорбев", "Чорбев")
    assert mentor_matches("Иван Чорбев", "иван чорбев")
    assert not mentor_matches("Иван Чорбев", "Китановски")


def _meta(mentor, level="bachelor", status="Одбрана", date="10.06.2025", committee=()):
    return {"mentor": mentor, "level": level, "status": status, "date": date, "committee": list(committee)}


_ROWS = [
    _meta("Иван Чорбев"),
    _meta("Иван Чорбев", date="01.02.2026", status="Пријава"),
    _meta("Иван Чорбев", level="master", status="24. Магистерската е завршена.", date="02.10.2026"),
    _meta("Ема Пандилова", committee=["Иван Чорбев", "Иван Китановски"]),
    _meta("Иван Китановски", level="master", status="22. Менторот ја закажува одбраната"),
]


def test_is_completed_uses_the_last_step_of_each_workflow():
    from backend.core.theses import is_completed

    assert is_completed(_meta("x"))
    assert not is_completed(_meta("x", status="Пријава"))
    assert is_completed(_meta("x", level="master", status="24. Магистерската е завршена."))
    assert not is_completed(_meta("x", level="master", status="22. Менторот ја закажува одбраната"))


def test_summarize_theses_for_a_mentor():
    from backend.core.theses import summarize_theses

    [chorbev] = summarize_theses(_ROWS, mentor="Чорбев")["mentors"]

    assert chorbev["name"] == "Иван Чорбев"
    assert (chorbev["total"], chorbev["bachelor"], chorbev["master"]) == (3, 2, 1)
    assert (chorbev["completed"], chorbev["in_progress"]) == (2, 1)
    assert chorbev["by_year"] == {"2025": 1, "2026": 2}
    assert chorbev["committee_member"] == 1


def test_summarize_theses_lists_every_matching_name():
    from backend.core.theses import summarize_theses

    names = [m["name"] for m in summarize_theses(_ROWS, mentor="Иван")["mentors"]]

    assert names == ["Иван Китановски", "Иван Чорбев"]


def test_summarize_theses_overall_with_filters():
    from backend.core.theses import summarize_theses

    overall = summarize_theses(_ROWS)
    assert overall["total"] == 5
    assert overall["top_mentors"][0] == {"mentor": "Иван Чорбев", "theses": 3}

    assert summarize_theses(_ROWS, level="master")["total"] == 2
    assert summarize_theses(_ROWS, year="2026")["total"] == 2


def test_stats_source_is_picked_over_a_document_that_shares_some_numbers():
    from backend.core.chat_sources import pick_source
    from backend.core.retrieval import SearchResult
    from backend.core.theses import stats_as_source, summarize_theses

    stats = summarize_theses(_ROWS, mentor="Чорбев")
    elaborate = SearchResult(
        document_id="e", title="elaborat", url="https://finki.ukim.mk/e.pdf", source="official",
        type="document", published_at=None, chunk_text="Предмети 2025 и 2026 со 3 кредити", score=0.6,
    )
    answer = "Иван Чорбев има 3 дипломски: 2 завршени, 1 во тек (2025: 1, 2026: 2)."

    picked = pick_source(answer, [elaborate, stats_as_source(stats)])
    assert picked.url == "https://diplomski.finki-hub.com/"
