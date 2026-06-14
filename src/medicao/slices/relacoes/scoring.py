"""Pontuacao de relevancia entre artigos e itens de ementa por termos em comum.

Trabalha apenas com campos textuais dos CSVs (sem reabrir PDFs), o que torna o
calculo independente da forma como o dataset de artigos foi gerado.
"""

from __future__ import annotations

from medicao.shared.text import significant_terms

SCORE_MINIMO = 2

_ARTIGO_CAMPOS = (
    "title",
    "abstract",
    "keywords",
    "areas_pesquisa",
    "metricas_mencionadas",
    "metodologia",
)

_EMENTA_CAMPOS = ("modulo", "topico", "descricao")


def artigo_terms(artigo: dict) -> set[str]:
    texto = " ".join(str(artigo.get(c, "") or "") for c in _ARTIGO_CAMPOS)
    return significant_terms(texto)


def ementa_terms(item: dict) -> set[str]:
    texto = " ".join(str(item.get(c, "") or "") for c in _EMENTA_CAMPOS)
    return significant_terms(texto)


def score(termos_artigo: set[str], termos_ementa: set[str]) -> int:
    return len(termos_artigo & termos_ementa)
