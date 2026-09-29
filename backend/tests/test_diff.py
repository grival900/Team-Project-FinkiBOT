from dataclasses import dataclass, field

import pytest

from backend.models import Document
from backend.notifier.diff import find_unsent_matches, matches_filters


@dataclass
class FakeDoc:
    title: str
    content: str


# --------------------------------------------------------------------------------------
# matches_filters
# --------------------------------------------------------------------------------------


def test_empty_filters_match_everything():
    doc = FakeDoc(title="Наслов", content="содржина")
    assert matches_filters(doc, {}) is True


def test_none_filters_match_everything():
    """A Subscription row could carry filters=None; don't blow up on `.get`."""
    doc = FakeDoc(title="Наслов", content="содржина")
    assert matches_filters(doc, None) is True


def test_filters_present_but_all_lists_empty_match_everything():
    doc = FakeDoc(title="Наслов", content="содржина")
    assert matches_filters(doc, {"keywords": [], "course_codes": []}) is True


def test_keyword_match_is_case_insensitive_substring():
    doc = FakeDoc(title="Распоред за јунска ИСПИТНА сесија", content="...")
    assert matches_filters(doc, {"keywords": ["испитна сесија"]}) is True


def test_keyword_match_when_filter_is_upper_and_doc_is_lower():
    doc = FakeDoc(title="распоред за јунска испитна сесија", content="...")
    assert matches_filters(doc, {"keywords": ["ИСПИТНА СЕСИЈА"]}) is True


def test_keyword_miss():
    doc = FakeDoc(title="Нешто сосема друго", content="...")
    assert matches_filters(doc, {"keywords": ["запишување"]}) is False


def test_any_keyword_matching_is_enough():
    doc = FakeDoc(title="Одбрана на дипломска", content="...")
    assert matches_filters(doc, {"keywords": ["колоквиум", "дипломска", "испит"]}) is True


def test_keyword_can_match_in_content_only():
    doc = FakeDoc(title="Општо соопштение", content="Се однесува на предметот F23L3S139")
    assert matches_filters(doc, {"keywords": ["f23l3s139"]}) is True


def test_keyword_can_match_in_title_only():
    doc = FakeDoc(title="Резултати за Бази на податоци", content="види прилог")
    assert matches_filters(doc, {"keywords": ["бази на податоци"]}) is True


def test_course_code_matched_like_a_keyword():
    doc = FakeDoc(title="Промена на термин", content="важи за F23L3S139")
    assert matches_filters(doc, {"course_codes": ["F23L3S139"]}) is True


def test_course_code_match_is_case_insensitive():
    doc = FakeDoc(title="Промена на термин", content="важи за F23L3S139")
    assert matches_filters(doc, {"course_codes": ["f23l3s139"]}) is True


def test_keywords_and_course_codes_are_ored_together():
    doc = FakeDoc(title="Термин за colloquium", content="за сите години")
    assert matches_filters(doc, {"keywords": ["нема"], "course_codes": ["исто така нема"]}) is False
    assert matches_filters(doc, {"keywords": ["нема"], "course_codes": ["colloquium"]}) is True


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
def test_blank_term_alongside_a_real_one_does_not_swallow_the_filter(blank):
    # "" is a substring of everything, so a blank keyword used to match every announcement
    doc = FakeDoc(title="Нешто сосема друго", content="...")
    assert matches_filters(doc, {"keywords": [blank, "запишување"]}) is False


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
def test_filter_made_up_entirely_of_blanks_behaves_like_no_filter(blank):
    doc = FakeDoc(title="Нешто сосема друго", content="...")
    assert matches_filters(doc, {"keywords": [blank]}) is True


def test_blank_terms_are_dropped_but_real_ones_still_apply():
    doc = FakeDoc(title="Рок за запишување семестар", content="...")
    assert matches_filters(doc, {"keywords": ["  ", "запишување"]}) is True


def test_surrounding_whitespace_on_a_term_is_ignored():
    doc = FakeDoc(title="Јунска испитна сесија", content="...")
    assert matches_filters(doc, {"keywords": ["  испитна сесија  "]}) is True


def test_term_is_not_matched_across_the_title_content_boundary():
    """haystack joins title and content with a newline; a term straddling that seam
    should not match."""
    doc = FakeDoc(title="испитна", content="сесија")
    assert matches_filters(doc, {"keywords": ["испитна сесија"]}) is False


# --------------------------------------------------------------------------------------
# find_unsent_matches  (exercises the dedup + filter + source/type gating together)
# --------------------------------------------------------------------------------------


@dataclass
class _Row:
    """Stand-in for a Document / SentNotification row."""

    id: object = None
    document_id: object = None
    subscription_id: object = None
    source: str = "official"
    type: str = "announcement"
    title: str = ""
    content: str = ""


@dataclass
class _Sub:
    id: object
    filters: dict = field(default_factory=dict)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter_by(self, **kw):
        return _FakeQuery(
            r for r in self._rows if all(getattr(r, k) == v for k, v in kw.items())
        )

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    """Enough of a Session for find_unsent_matches: it issues exactly two queries,
    `db.query(Document)` and `db.query(SentNotification.document_id)`."""

    def __init__(self, documents, sent):
        self._documents = documents
        self._sent = sent

    def query(self, entity):
        if entity is Document:
            return _FakeQuery(self._documents)
        return _FakeQuery(self._sent)


def test_find_unsent_matches_returns_matching_unsent_announcements():
    docs = [
        _Row(id="d1", title="Резултати по Бази на податоци", content="..."),
        _Row(id="d2", title="Нешто друго", content="..."),
    ]
    sub = _Sub(id="s1", filters={"keywords": ["бази на податоци"]})

    out = find_unsent_matches(_FakeSession(docs, sent=[]), sub)

    assert [d.id for d in out] == ["d1"]


def test_find_unsent_matches_excludes_already_sent_for_this_subscription():
    docs = [_Row(id="d1", title="Соопштение", content="...")]
    sent = [_Row(document_id="d1", subscription_id="s1")]
    sub = _Sub(id="s1", filters={})

    assert find_unsent_matches(_FakeSession(docs, sent), sub) == []


def test_find_unsent_matches_ignores_sends_to_other_subscriptions():
    """A doc already delivered to a *different* subscriber is still new for this one."""
    docs = [_Row(id="d1", title="Соопштение", content="...")]
    sent = [_Row(document_id="d1", subscription_id="someone-else")]
    sub = _Sub(id="s1", filters={})

    assert [d.id for d in find_unsent_matches(_FakeSession(docs, sent), sub)] == ["d1"]


def test_find_unsent_matches_empty_filters_returns_all_unsent_announcements():
    docs = [_Row(id="d1", title="A", content="..."), _Row(id="d2", title="B", content="...")]
    sub = _Sub(id="s1", filters={})

    out = find_unsent_matches(_FakeSession(docs, sent=[]), sub)

    assert {d.id for d in out} == {"d1", "d2"}


def test_find_unsent_matches_only_considers_official_announcements():
    docs = [
        _Row(id="d1", source="official", type="announcement", title="соопштение", content="."),
        _Row(id="d2", source="official", type="course", title="соопштение", content="."),
        _Row(id="d3", source="finki_hub", type="announcement", title="соопштение", content="."),
    ]
    sub = _Sub(id="s1", filters={})

    out = find_unsent_matches(_FakeSession(docs, sent=[]), sub)

    assert [d.id for d in out] == ["d1"]


def test_find_unsent_matches_returns_empty_when_nothing_matches():
    docs = [_Row(id="d1", title="Распоред", content="за испити")]
    sub = _Sub(id="s1", filters={"keywords": ["дипломска"]})

    assert find_unsent_matches(_FakeSession(docs, sent=[]), sub) == []
