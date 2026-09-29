from backend.core.prerequisites import split_prerequisite_text


def test_split_single_course():
    assert split_prerequisite_text("Криптографија") == ["Криптографија"]


def test_split_or_alternatives():
    text = "Алгоритми и податочни структури или Примена на алгоритми и податочни структури"
    assert split_prerequisite_text(text) == [
        "Алгоритми и податочни структури",
        "Примена на алгоритми и податочни структури",
    ]


def test_split_comma_separated_requirements():
    text = "Бази на податоци, Веројатност и статистика"
    assert split_prerequisite_text(text) == ["Бази на податоци", "Веројатност и статистика"]


def test_split_non_course_credit_requirement_passes_through_unmatched():
    """Not a course name — resolve_prerequisites will just fail to match it and leave
    it unlinked, but splitting still returns it as a single candidate segment."""
    assert split_prerequisite_text("100 кредити") == ["100 кредити"]


def test_split_empty_text():
    assert split_prerequisite_text("") == []
    assert split_prerequisite_text(None) == []
