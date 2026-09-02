"""Shared text-matching utilities.

Ported from ``automation/persona.py`` unchanged (same normalization rules, same
word-boundary matching behavior) so scoring/clustering/safety keep producing
identical results to the working CLI reference. See
``docs/architecture-assessment.md`` § C for why this is a port, not a rewrite.
"""

from __future__ import annotations

import re
import unicodedata

_AR_NORMALIZE = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "into", "after", "over", "its",
    "new", "says", "said", "will", "has", "have", "are", "was", "were", "amid", "than",
    "على", "من", "في", "عن", "الى", "الي", "مع", "بعد", "بين", "هذا", "التي", "الذي", "قد",
}


def normalize(text: str) -> str:
    """Normalize Arabic/English text for matching: lowercase, no diacritics, unified alef/ya/ta."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.translate(_AR_NORMALIZE))


def hits(text: str, terms) -> list:
    """Terms present in text — whole-word match for short terms, substring for compound ones."""
    found = []
    for term in terms:
        t = normalize(str(term))
        if not t:
            continue
        if " " in t or len(t) > 6:
            if t in text:
                found.append(term)
        elif re.search(rf"(?<![\w؀-ۿ]){re.escape(t)}(?![\w؀-ۿ])", text):
            found.append(term)
    return found


def saturate(n: int, full: int = 3) -> float:
    """Match count -> 0..1 with saturation; `full` matches reach the full score."""
    return min(1.0, n / full) if full else 0.0


def stem(token: str) -> str:
    """Light stemmer unifying headline word forms: backed/backs -> back, raises -> raise."""
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > 4 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokens(text: str) -> set:
    raw = re.findall(r"[\w؀-ۿ]+", normalize(text))
    return {stem(t) for t in raw if len(t) > 2 and t not in STOPWORDS}


def similarity(a: str, b: str) -> float:
    """Headline similarity = Jaccard (penalizes difference) + overlap (catches rephrasing)."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    shared = ta & tb
    if len(shared) < 2:
        return 0.0
    jaccard = len(shared) / len(ta | tb)
    overlap = len(shared) / min(len(ta), len(tb))
    return round(0.5 * jaccard + 0.5 * overlap, 3)
