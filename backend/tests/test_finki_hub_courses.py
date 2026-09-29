from backend.scrapers.finki_hub.courses import _format_content, parse_course_entry


def _make_entry(**overrides) -> dict:
    base = {
        "name": "Web3 апликации",
        "professors": "Марјан Гушев",
        "assistants": "Ана Мадевска Богданова",
        "tags": "Веб",
        "2023-available": "TRUE",
        "2023-code": "F23L3S139",
        "2023-level": "3",
        "2023-semester": "8",
        "2023-channel": "1",
        "2023-name": "Web3 апликации",
        "2023-prerequisite": "Алгоритми и податочни структури",
        "2023-credits": "6",
        "2023-state-kn": "изборен",
        "2023-state-siis": "нема",
        "2023-state-pit": "изборен",
        "2018-available": "FALSE",
    }
    base.update(overrides)
    return base


def test_parse_course_entry_extracts_professors_and_assistants():
    _, _, details = parse_course_entry(_make_entry())
    assert details["professors"] == ["Марјан Гушев"]
    assert details["assistants"] == ["Ана Мадевска Богданова"]


def test_parse_course_entry_splits_multiple_names():
    entry = _make_entry(professors="Марјан Гушев\nАна Мадевска Богданова")
    _, _, details = parse_course_entry(entry)
    assert details["professors"] == ["Марјан Гушев", "Ана Мадевска Богданова"]


def test_parse_course_entry_extracts_accreditation_fields():
    _, _, details = parse_course_entry(_make_entry())
    assert len(details["accreditations"]) == 1
    acc = details["accreditations"][0]
    assert acc["year"] == "2023"
    assert acc["official_url"] == "https://www.finki.ukim.mk/mk/subject/F23L3S139"
    assert acc["Код"] == "F23L3S139"
    assert acc["Ниво"] == "3"
    assert acc["Семестар"] == "8"
    assert acc["Предуслов"] == "Алгоритми и податочни структури"


def test_parse_course_entry_skips_unavailable_accreditation():
    _, _, details = parse_course_entry(_make_entry(**{"2018-available": "FALSE"}))
    assert len(details["accreditations"]) == 1
    assert details["accreditations"][0]["year"] == "2023"


def test_parse_course_entry_includes_both_accreditations():
    entry = _make_entry(**{
        "2018-available": "TRUE",
        "2018-code": "F18L3W065",
        "2018-level": "3",
        "2018-semester": "7",
    })
    _, _, details = parse_course_entry(entry)
    assert len(details["accreditations"]) == 2
    assert details["accreditations"][0]["year"] == "2023"
    assert details["accreditations"][1]["year"] == "2018"


def test_parse_course_entry_handles_missing_optional_fields():
    entry = {"name": "Тест", "2023-available": "FALSE", "2018-available": "FALSE"}
    name, tags, details = parse_course_entry(entry)
    assert name == "Тест"
    assert tags == []
    assert details["professors"] == []
    assert details["assistants"] == []
    assert details["accreditations"] == []


def test_parse_course_entry_empty_entry():
    name, tags, details = parse_course_entry({})
    assert name == ""
    assert tags == []
    assert details == {"professors": [], "assistants": [], "accreditations": []}


def test_format_content_includes_level_prerequisite_and_staff():
    _, tags, details = parse_course_entry(_make_entry())
    content = _format_content("Web3 апликации", tags, details)

    assert "Код: F23L3S139" in content
    assert "Ниво: 3, Семестар: 8" in content
    assert "Кредити: 6" in content
    assert "Предуслов: Алгоритми и податочни структури" in content
    assert "Професори: Марјан Гушев" in content
    assert "Асистенти: Ана Мадевска Богданова" in content
    assert "Тагови: Веб" in content
    assert "Изборен за:" in content
    assert "КНИ" in content
    assert "Акредитации: 2023" in content


def test_parse_course_entry_extracts_program_statuses():
    entry = _make_entry(**{
        "2023-state-kn": "задолжителен",
        "2023-state-siis": "задолжителен",
        "2023-state-pit": "изборен",
    })
    _, _, details = parse_course_entry(entry)
    programs = details["accreditations"][0]["programs"]
    assert programs["КНИ"] == "задолжителен"
    assert programs["СИИС"] == "задолжителен"
    assert programs["ПИТ"] == "изборен"


def test_split_tags_comma_separated():
    entry = _make_entry(tags="Веб, Блокчејн, Криптовалути")
    _, tags, _ = parse_course_entry(entry)
    assert tags == ["Веб", "Блокчејн", "Криптовалути"]
