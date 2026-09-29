from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from backend.core import retrieval
from backend.core.retrieval import (
    _RECENCY_BOOST_HORIZON_DAYS,
    _RERANK_POOL,
    RECENCY_MATCH_BOOST,
    TITLE_MATCH_BOOST,
    SearchResult,
    _apply_recency_boost,
    _apply_title_boost,
    _merge,
    _query_vectors,
    search,
)


def _result(**overrides) -> SearchResult:
    defaults = dict(
        document_id="doc-1",
        title="Title",
        url="https://example.com",
        source="official",
        type="course",
        published_at=None,
        chunk_text="chunk text",
        score=0.5,
    )
    return SearchResult(**{**defaults, **overrides})


def test_merge_keeps_highest_score_per_chunk():
    low = _result(document_id="a", chunk_text="same chunk", score=0.3)
    high = _result(document_id="a", chunk_text="same chunk", score=0.9)

    merged: dict[str, SearchResult] = {}
    _merge(merged, [low])
    _merge(merged, [high])

    assert list(merged.values()) == [high]


def test_search_with_source_filter_only_queries_that_source():
    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1, 0.2]]),
        patch.object(retrieval, "_search_by_vector") as mock_search,
    ):
        mock_search.return_value = [_result(document_id="a", source="official", score=0.7)]
        results = search(db=None, query="бази", k=5, source="official")

    # the vector query asks for the bigger rerank pool, then it's trimmed to k
    assert [c.args[3] for c in mock_search.call_args_list] == ["official", "official"]
    assert mock_search.call_args_list[0].args == (None, [0.1, 0.2], _RERANK_POOL, "official", None, None, None)
    assert mock_search.call_args_list[0].kwargs == {"exclude_type": "document"}
    assert mock_search.call_args_list[1].args[4] == "document"
    assert [r.document_id for r in results] == ["a"]  # same chunk from both calls, merged


def test_search_without_source_filter_unions_instead_of_competing():
    # "bazi" used to return 8 official results and only 2 finki-hub ones
    official_results = [_result(document_id=f"official-{i}", source="official", score=0.9 - i * 0.01) for i in range(5)]
    finki_hub_results = [_result(document_id=f"finki_hub-{i}", source="finki_hub", score=0.4 - i * 0.01) for i in range(5)]

    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        return official_results if source == "official" else finki_hub_results

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1, 0.2]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        results = search(db=None, query="bazi", k=5)

    document_ids = {r.document_id for r in results}
    assert document_ids == {f"official-{i}" for i in range(5)} | {f"finki_hub-{i}" for i in range(5)}
    assert results[0].source == "official"
    assert "finki_hub-0" in document_ids


def test_query_vectors_adds_a_transliterated_variant_for_a_latin_query():
    with patch.object(retrieval, "embed_query", side_effect=lambda q: [q]) as embed:
        vectors = _query_vectors("bazi na podatoci")

    assert [call.args[0] for call in embed.call_args_list] == [
        "bazi na podatoci",
        "бази на податоци",
    ]
    assert vectors == [["bazi na podatoci"], ["бази на податоци"]]


def test_query_vectors_leaves_a_cyrillic_query_untouched():
    with patch.object(retrieval, "embed_query", side_effect=lambda q: [q]) as embed:
        _query_vectors("бази на податоци")

    assert [call.args[0] for call in embed.call_args_list] == ["бази на податоци"]


def test_query_vectors_does_not_duplicate_when_transliteration_is_a_noop():
    """A query with only unmapped Latin letters (q/w/x/y) transliterates to itself once
    lowercased — no point embedding the same string twice."""
    with patch.object(retrieval, "embed_query", side_effect=lambda q: [q]) as embed:
        _query_vectors("qwxy")

    assert embed.call_count == 1


def test_query_vectors_mixed_script_query_is_not_transliterated():
    """`SQL бази` already has Cyrillic — transliterating the Latin part would corrupt
    the technical term without helping recall."""
    with patch.object(retrieval, "embed_query", side_effect=lambda q: [q]) as embed:
        _query_vectors("SQL бази")

    assert [call.args[0] for call in embed.call_args_list] == ["SQL бази"]


def test_search_passes_the_date_range_through_to_each_per_source_query():
    df, dt = date(2026, 1, 1), date(2026, 6, 30)
    seen = []

    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        seen.append((source, date_from, date_to))
        return []

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        search(db=None, query="сесија", k=5, date_from=df, date_to=dt)

    assert seen == [("official", df, dt), ("finki_hub", df, dt), ("official", df, dt), ("finki_hub", df, dt)]


def test_search_ranks_theses_as_their_own_group():
    # thesis abstracts must not take all the finki-hub slots away from courses
    theses = [_result(document_id=f"t{i}", source="finki_hub", type="thesis", score=0.9 - i * 0.01) for i in range(10)]
    course = _result(document_id="course", source="finki_hub", type="course", score=0.6)

    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        if source != "finki_hub":
            return []
        pool = theses + [course]
        return [r for r in pool if (type is None or r.type == type) and r.type != exclude_type]

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        results = search(db=None, query="бази на податоци", k=3)

    assert [r.document_id for r in results] == ["t0", "t1", "t2", "course"]


def test_search_caps_each_source_at_k_before_merging():
    many_official = [_result(document_id=f"official-{i}", source="official", score=1.0 - i * 0.01) for i in range(10)]

    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        return many_official[:k] if source == "official" else []

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1, 0.2]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        results = search(db=None, query="bazi", k=3)

    assert len(results) == 3


def test_search_min_score_drops_results_below_the_floor():
    mixed = [
        _result(document_id="strong", source="official", score=0.71),
        _result(document_id="weak", source="official", score=0.32),
    ]

    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        return mixed if source == "official" else []

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1, 0.2]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        results = search(db=None, query="кога е испитната сесија", k=5, min_score=0.45)

    assert [r.document_id for r in results] == ["strong"]


def test_search_min_score_none_keeps_everything():
    mixed = [
        _result(document_id="strong", source="official", score=0.71),
        _result(document_id="weak", source="official", score=0.12),
    ]

    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        return mixed if source == "official" else []

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1, 0.2]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        results = search(db=None, query="anything", k=5)

    assert {r.document_id for r in results} == {"strong", "weak"}


def test_title_boost_lifts_a_result_whose_title_contains_every_query_token():
    on_topic = _result(document_id="prof-page", title="д-р Слободан Калајџиски", score=0.60)
    mention = _result(document_id="co-author", title="д-р Андреа Кулаков", score=0.62)

    _apply_title_boost("Слободан Калајџиски", [on_topic, mention])

    assert on_topic.score == 0.60 + TITLE_MATCH_BOOST
    assert mention.score == 0.62  # untouched — title shares no query token


def test_title_boost_matches_across_a_latin_query_despite_transliteration_slack():
    """"kalajdziski" transliterates to "калајѕиски" (dz digraph), not the real
    "калајџиски" — the fuzzy per-token match is what still connects them."""
    result = _result(document_id="prof-page", title="д-р Слободан Калајџиски", score=0.5)

    _apply_title_boost("Slobodan Kalajdziski", [result])

    assert result.score == 0.5 + TITLE_MATCH_BOOST


def test_title_boost_is_a_noop_for_a_long_topical_query():
    result = _result(document_id="course", title="Бази на податоци", score=0.5)

    _apply_title_boost("што се учи на предметот бази на податоци и sql", [result])

    assert result.score == 0.5


def test_recency_boost_gives_a_fresh_result_close_to_the_full_bump():
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    fresh = _result(document_id="days-old", published_at=now - timedelta(days=3), score=0.55)

    _apply_recency_boost([fresh], now)

    assert fresh.score == 0.55 + RECENCY_MATCH_BOOST * (1 - 3 / _RECENCY_BOOST_HORIZON_DAYS)


def test_recency_boost_does_not_touch_a_result_past_the_horizon():
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    stale = _result(document_id="2022", published_at=now - timedelta(days=_RECENCY_BOOST_HORIZON_DAYS + 1), score=0.62)

    _apply_recency_boost([stale], now)

    assert stale.score == 0.62


def test_recency_boost_is_a_noop_for_an_undated_result():
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    course = _result(document_id="course", published_at=None, score=0.7)

    _apply_recency_boost([course], now)

    assert course.score == 0.7


def test_recency_boost_handles_a_naive_published_at():
    now = datetime(2026, 9, 8, tzinfo=timezone.utc)
    naive = _result(document_id="naive", published_at=datetime(2026, 9, 1), score=0.5)

    _apply_recency_boost([naive], now)

    assert naive.score > 0.5


def _run_official_search(rows: list[SearchResult], **kwargs) -> list[SearchResult]:
    def fake_search_by_vector(db, vector, k, source, type, date_from=None, date_to=None, exclude_type=None):
        return list(rows) if source == "official" else []

    with (
        patch.object(retrieval, "_query_vectors", return_value=[[0.1, 0.2]]),
        patch.object(retrieval, "_search_by_vector", side_effect=fake_search_by_vector),
    ):
        return search(db=None, query="подготвителна настава", source="official", **kwargs)


def test_recency_boost_lets_a_fresh_repost_overtake_an_older_near_duplicate():
    # 'подготвителна настава' is reposted every year; the 2022 copy scored slightly higher
    now = datetime.now(timezone.utc)
    rows = [
        _result(document_id="2022", source="official", published_at=now - timedelta(days=1400), score=0.66),
        _result(document_id="2026", source="official", published_at=now - timedelta(days=4), score=0.61),
    ]

    plain = _run_official_search(rows, k=2)
    assert [r.document_id for r in plain] == ["2022", "2026"]

    boosted = _run_official_search(rows, k=2, recency_boost=True)
    assert [r.document_id for r in boosted] == ["2026", "2022"]
