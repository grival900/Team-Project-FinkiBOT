from backend.core.exam_schedule import course_matches, parse_exam_records, pick_sessions

_CHUNK = (
    "[10.09.2026 11:30-17:30 200ц, лаб. 117, лаб. 12: Оперативни системи / Operating systems] "
    "[10.09.2026 14:00-16:00 лаб. 3: Податочно рударење]"
)


def test_parse_exam_records_reads_date_time_rooms_and_course():
    first, second = parse_exam_records(_CHUNK)

    assert (first.date, first.time, first.rooms) == ("10.09.2026", "11:30-17:30", "200ц, лаб. 117, лаб. 12")
    assert first.course == "Оперативни системи / Operating systems"
    assert (second.rooms, second.course) == ("лаб. 3", "Податочно рударење")


def test_course_matches_ignores_the_english_name():
    assert course_matches("Оперативни системи", "Оперативни системи / Operating systems")


def test_course_matches_tolerates_a_slightly_different_session_name():
    assert course_matches("Електронска и мобилна трговија", "Електронска и мобилна комерција (трговија)")


def test_course_matches_does_not_confuse_a_shorter_course_name():
    assert not course_matches("Компјутерски мрежи и безбедност", "Компјутерски мрежи")
    assert not course_matches("Компјутерски мрежи", "Компјутерски мрежи и безбедност")


_TITLES = [
    "2025/2026 Јуни",
    "2025/2026 Септември",
    "2025/2026 Летен - Прв Колоквиум",
    "2025/2026 Летен - Втор Колоквиум",
]


def test_pick_sessions_matches_adjective_forms():
    assert pick_sessions(_TITLES, "септемвриска сесија") == ["2025/2026 Септември"]
    assert pick_sessions(_TITLES, "јунска") == ["2025/2026 Јуни"]


def test_pick_sessions_prefers_the_closest_colloquium():
    assert pick_sessions(_TITLES, "втор колоквиум летен") == ["2025/2026 Летен - Втор Колоквиум"]


def test_pick_sessions_returns_everything_when_nothing_matches():
    assert pick_sessions(_TITLES, "") == _TITLES
    assert pick_sessions(_TITLES, "2025/2026") == _TITLES


def test_course_matches_loosely_accepts_a_partial_name():
    from backend.core.exam_schedule import course_matches_loosely

    assert course_matches_loosely("веб програмирање", "Веб програмирање")
    assert course_matches_loosely("мрежи", "Компјутерски мрежи и безбедност")
    assert not course_matches_loosely("веб програмирање", "Интернет програмирање на клиентска страна")
