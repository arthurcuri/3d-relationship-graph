"""Pontuação de relevância entre artigos e aulas por temas em comum."""

from __future__ import annotations

# Temas buscados no texto completo de cada artigo, por aula.
AULA_TEMAS = {
    "Aula 1.pdf": [
        "medição de software", "experimentação", "engenharia de software",
        "decisões baseadas em dados", "qualidade de software",
    ],
    "Aula 2 - Escopo e Normas de Medição de Software.pdf": [
        "métricas de software", "normas", "iso", "cmmi", "gqm",
        "custo", "esforço", "confiabilidade", "complexidade",
        "maturidade", "medição", "escopo",
    ],
    "Aula 3 - Introdução à Experimentação.pdf": [
        "experimentação", "experimento controlado", "validade",
        "variáveis", "survey", "estudo de caso", "métodos empíricos",
    ],
    "Aula 4 - Entidades, Atributos e Objetivos de Medição.pdf": [
        "gqm", "entidades", "atributos", "objetivos de medição",
        "métricas", "escala de medição", "tipos de medida",
    ],
    "Aula 5 - Medições de Produto, Processo e Recurso.pdf": [
        "loc", "sloc", "complexidade ciclomática", "halstead",
        "pontos de função", "acoplamento", "coesão", "métricas de produto",
        "métricas de processo", "defeitos", "manutenibilidade",
        "produtividade", "custo", "esforço", "cocomo", "dora",
    ],
    "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf": [
        "estatística", "distribuição", "teste de hipótese", "variáveis",
        "normal", "probabilidade", "amostra", "significância",
        "desvio padrão", "média", "mediana",
    ],
    "Aula 8 - Processo de Experimentos.pdf": [
        "experimentação", "planejamento de experimentos", "escopo",
        "operação", "análise", "interpretação", "ameaças à validade",
        "revisão sistemática", "replicação", "relatório",
        "variáveis dependentes", "variáveis independentes",
    ],
}

# Mínimo de temas que precisam casar para registrar uma relação.
SCORE_MINIMO = 3


def score(artigo_text_lower: str, temas: list[str]) -> int:
    return sum(1 for tema in temas if tema in artigo_text_lower)
