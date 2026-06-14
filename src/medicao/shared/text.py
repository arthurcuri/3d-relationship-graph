"""Utilitarios de texto compartilhados pelos slices."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# Stopwords PT/EN comuns, para extracao de termos significativos.
STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "das", "dos", "em", "no", "na", "nos",
    "nas", "um", "uma", "para", "por", "com", "sem", "que", "como", "ao",
    "aos", "as", "os", "se", "ou", "the", "of", "and", "to", "in", "for",
    "on", "with", "an", "is", "are", "from", "by", "at", "as", "be", "este",
    "esta", "esse", "essa", "seu", "sua", "sobre", "entre", "mais", "menos",
}


def clean_text(text: str | None) -> str:
    """Remove multiplos espacos e quebras de linha extras."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def most_common_year(text: str, window: int = 3000) -> str:
    """Retorna o ano (2000-2029) mais frequente no inicio do texto."""
    years = re.findall(r"\b(20[0-2]\d)\b", text[:window])
    if years:
        return Counter(years).most_common(1)[0][0]
    return ""


def first_match(patterns, text: str, flags: int = 0, group: int = 1) -> str:
    """Retorna o primeiro grupo capturado entre uma lista de padroes."""
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(group)
    return ""


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def significant_terms(text: str, min_len: int = 4) -> set[str]:
    """Conjunto de termos significativos (sem acento, sem stopwords)."""
    if not text:
        return set()
    norm = _strip_accents(text.lower())
    words = re.findall(r"[a-z0-9]{%d,}" % min_len, norm)
    return {w for w in words if w not in STOPWORDS}
