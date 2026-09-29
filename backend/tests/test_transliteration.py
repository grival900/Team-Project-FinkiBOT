from backend.core.transliteration import is_latin_only, transliterate_latin_to_cyrillic


def test_transliterate_simple_word():
    assert transliterate_latin_to_cyrillic("bazi") == "бази"


def test_transliterate_phrase():
    assert transliterate_latin_to_cyrillic("bazi na podatoci") == "бази на податоци"


def test_transliterate_digraphs():
    assert transliterate_latin_to_cyrillic("nastavnici") == "наставници"
    assert transliterate_latin_to_cyrillic("kje") == "ќе"
    assert transliterate_latin_to_cyrillic("shema") == "шема"


def test_transliterate_unmapped_letters_pass_through():
    # q, w, x, y have no Macedonian Cyrillic equivalent and aren't guessed at.
    assert transliterate_latin_to_cyrillic("qwxy") == "qwxy"


def test_transliterate_lowercases_first():
    assert transliterate_latin_to_cyrillic("BAZI") == "бази"


def test_is_latin_only_true_for_plain_latin():
    assert is_latin_only("bazi na podatoci") is True


def test_is_latin_only_false_for_cyrillic():
    assert is_latin_only("бази на податоци") is False


def test_is_latin_only_false_for_mixed_script():
    assert is_latin_only("SQL бази") is False


def test_is_latin_only_false_for_no_letters():
    assert is_latin_only("12345") is False
