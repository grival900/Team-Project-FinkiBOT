from backend.scripts.seed import row_to_ndoc


def test_row_to_ndoc_builds_normalized_document():
    row = {
        "source": "official",
        "type": "announcement",
        "title": "  Тест   соопштение  ",
        "url": "https://finki.ukim.mk/announcements/test/",
        "content": "линија 1\n\nлинија 2  ",
        "published_at": "2026-01-15T10:00:00+00:00",
        "metadata": {"foo": "bar"},
    }

    ndoc = row_to_ndoc(row)

    assert ndoc.source == "official"
    assert ndoc.type == "announcement"
    assert ndoc.title == "Тест соопштение"  # .clean() collapses whitespace
    assert ndoc.url == row["url"]
    assert ndoc.content == "линија 1\nлинија 2"
    assert ndoc.published_at is not None and ndoc.published_at.year == 2026
    assert ndoc.metadata == {"foo": "bar"}


def test_row_to_ndoc_handles_missing_published_at():
    row = {
        "source": "finki_hub",
        "type": "course",
        "title": "Курс",
        "url": "https://predmeti.finki-hub.com/?course=Курс",
        "content": "содржина",
        "published_at": None,
        "metadata": {},
    }

    ndoc = row_to_ndoc(row)

    assert ndoc.published_at is None


def test_vectors_survive_the_seed_encoding():
    import numpy as np

    from backend.scripts.export_seed import decode_vector, encode_vector

    vector = np.random.default_rng(0).normal(size=1024).astype(np.float32)
    vector /= np.linalg.norm(vector)

    decoded = np.array(decode_vector(encode_vector(vector)))

    assert decoded.shape == (1024,)
    assert float(vector @ decoded) > 0.9999


def test_read_seed_uses_vectors_only_for_the_same_model():
    from backend.core.config import get_settings
    from backend.scripts.seed import read_seed

    rows = [{"url": "x"}]
    model = get_settings().embedding_model_name

    assert read_seed({"embedding_model": model, "documents": rows}) == (rows, True)
    assert read_seed({"embedding_model": "some/other-model", "documents": rows}) == (rows, False)
    assert read_seed(rows) == (rows, False)  # old format, no vectors
