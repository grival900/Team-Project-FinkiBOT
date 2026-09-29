from backend.scrapers.normalize import NormalizedDocument


def _doc(**overrides) -> NormalizedDocument:
    defaults = dict(source="official", type="announcement", title="T", url="u", content="hello")
    defaults.update(overrides)
    return NormalizedDocument(**defaults)


def test_content_hash_changes_with_content():
    assert _doc(content="hello").content_hash != _doc(content="world").content_hash


def test_content_hash_stable_for_identical_content():
    assert _doc(content="hello").content_hash == _doc(content="hello").content_hash


def test_clean_collapses_title_whitespace():
    doc = _doc(title="  Многу   празни места  ").clean()
    assert doc.title == "Многу празни места"


def test_clean_strips_lines_and_drops_blank_lines():
    doc = _doc(content="ред 1  \n\n   \nред 2\n").clean()
    assert doc.content == "ред 1\nред 2"
