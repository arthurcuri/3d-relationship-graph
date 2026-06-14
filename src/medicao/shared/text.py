"""Utilitários de texto compartilhados pelos slices."""

from __future__ import annotations

import re
from collections import Counter


def clean_text(text: str | None) -> str:
    """Remove múltiplos espaços e quebras de linha extras."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def most_common_year(text: str, window: int = 3000) -> str:
    """Retorna o ano (2000-2029) mais frequente no início do texto."""
    years = re.findall(r"\b(20[0-2]\d)\b", text[:window])
    if years:
        return Counter(years).most_common(1)[0][0]
    return ""


def first_match(patterns, text: str, flags: int = 0, group: int = 1) -> str:
    """Retorna o primeiro grupo capturado entre uma lista de padrões."""
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(group)
    return ""
