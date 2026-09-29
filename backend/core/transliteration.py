"""Rough latinica -> Cyrillic conversion ("bazi na podatoci" -> "бази на податоци")
so queries typed without a Cyrillic keyboard still find something. Not meant to be
perfect - retrieval searches the original query too.
"""

import re

# digraphs first, so "zh" isn't read as "z" + "h"
_DIGRAPHS = [
    ("nj", "њ"),
    ("lj", "љ"),
    ("gj", "ѓ"),
    ("kj", "ќ"),
    ("dz", "ѕ"),
    ("dj", "џ"),
    ("zh", "ж"),
    ("ch", "ч"),
    ("sh", "ш"),
]
_SINGLE = {
    "a": "а",
    "b": "б",
    "v": "в",
    "g": "г",
    "d": "д",
    "e": "е",
    "z": "з",
    "i": "и",
    "j": "ј",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "f": "ф",
    "h": "х",
    "c": "ц",
}
_MAP: dict[str, str] = dict(_DIGRAPHS) | _SINGLE
# q, w, x, y have no Macedonian equivalent and are left as they are
_PATTERN = re.compile("|".join(re.escape(p) for p, _ in _DIGRAPHS) + "|[a-z]")

_CYRILLIC_RE = re.compile("[Ѐ-ӿ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")


def transliterate_latin_to_cyrillic(text: str) -> str:
    return _PATTERN.sub(lambda m: _MAP.get(m.group(0), m.group(0)), text.lower())


def is_latin_only(text: str) -> bool:
    """Has Latin letters and no Cyrillic."""
    return bool(_LATIN_RE.search(text)) and not _CYRILLIC_RE.search(text)
