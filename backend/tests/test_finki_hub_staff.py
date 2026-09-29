from backend.scrapers.finki_hub.staff import parse_staff_entry


def _make_entry(**overrides) -> dict:
    base = {
        "name": "Марјан Гушев",
        "active": "1",
        "title": "д-р",
        "position": "Редовен професор",
        "email": "marjan.gushev@finki.ukim.mk",
        "cabinet": "224",
        "profile": "https://www.finki.ukim.mk/mk/staff/marjan-gushev",
        "courses": "https://courses.finki.ukim.mk/user/profile.php?id=100",
        "consultations": "https://consultations.finki.ukim.mk/display/marjan.gushev",
    }
    base.update(overrides)
    return base


def test_parse_staff_entry_extracts_all_fields():
    name, content, metadata = parse_staff_entry(_make_entry())
    assert name == "Марјан Гушев"
    assert "д-р, Редовен професор" in content
    assert "marjan.gushev@finki.ukim.mk" in content
    assert "Кабинет: 224" in content
    assert metadata["email"] == "marjan.gushev@finki.ukim.mk"
    assert metadata["position"] == "Редовен професор"
    assert metadata["cabinet"] == "224"
    assert "consultations" in metadata


def test_parse_staff_entry_minimal():
    entry = {"name": "Тест", "active": "1", "title": "", "position": "", "email": ""}
    name, content, metadata = parse_staff_entry(entry)
    assert name == "Тест"
    assert "Е-пошта" not in content
    assert "email" not in metadata


def test_parse_staff_entry_empty():
    name, content, metadata = parse_staff_entry({})
    assert name == ""
    assert content == ""
    assert metadata == {}


def test_content_includes_consultations_link():
    _, content, _ = parse_staff_entry(_make_entry())
    assert "consultations.finki.ukim.mk" in content
