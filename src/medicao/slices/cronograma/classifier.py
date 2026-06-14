"""Classificação de atividades do cronograma (tipo, módulo e aula vinculada)."""

from __future__ import annotations

import re

# Mapeamento manual: atividade do cronograma -> PDF de aula mais relevante.
ATIVIDADE_AULA_MAP = {
    "Apresentação do curso": "Aula 1.pdf",
    "Nivelamento": "Aula 1.pdf",
    "Escopo de Medição": "Aula 2 - Escopo e Normas de Medição de Software.pdf",
    "Conceitos Básicos de Medição": "Aula 2 - Escopo e Normas de Medição de Software.pdf",
    "Conceitos Básicos de Experimentação": "Aula 3 - Introdução à Experimentação.pdf",
    "Etapas de Experimentação e Relatórios": "Aula 8 - Processo de Experimentos.pdf",
    "Entidades, Atributos e Objetivos de Medição": "Aula 4 - Entidades, Atributos e Objetivos de Medição.pdf",
    "Métricas de Produto": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Métricas de Processo": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Métricas de Projeto": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Modelos: Custo & Esforço, Produtividade Data Collection": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Modelos: confiabilidade, qualidade": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Pontos de Função": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Revisão de Estatística": "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf",
    "Estatística para Experimentos": "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf",
    "Intrd. à Experimentação": "Aula 3 - Introdução à Experimentação.pdf",
    "Métodos e Estratégias Empíricas": "Aula 8 - Processo de Experimentos.pdf",
    "Variáveis em Experimentos": "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf",
    "Revisão Sistemática da Literatura": "Aula 8 - Processo de Experimentos.pdf",
    "Etapas: Escopo e Planejamento": "Aula 8 - Processo de Experimentos.pdf",
    "Etapas: Operação": "Aula 8 - Processo de Experimentos.pdf",
    "Etapas: Análise e Interpretação": "Aula 8 - Processo de Experimentos.pdf",
    "Data Analysis - Data collection and Data Validation": "Aula 8 - Processo de Experimentos.pdf",
    "Tomada de Decisão em Experimentos": "Aula 8 - Processo de Experimentos.pdf",
    "Relatórios e Documentação Técnica": "Aula 8 - Processo de Experimentos.pdf",
    "Métricas modernas": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
}


def classify_tipo(atividade: str) -> str:
    if re.search(r"[Aa]valiação\s*\d", atividade):
        return "Avaliação"
    if re.search(r"[Rr]evisão\s+de\s+[Pp]rova", atividade):
        return "Revisão de Prova"
    if re.search(r"[Rr]evisão\s+de\s+[Mm]atéria", atividade):
        return "Revisão de Matéria"
    if re.search(r"[Pp]resentação.*[Tt]rabalho", atividade):
        return "Apresentação de Trabalho"
    if re.search(r"[Nn]ivelamento", atividade):
        return "Nivelamento"
    if re.search(r"[Pp]resentação\s+do\s+curso", atividade):
        return "Apresentação do Curso"
    if re.search(r"[Ee]nunciado", atividade):
        return "Orientação de Trabalho"
    if re.search(r"[Rr]eavaliação", atividade):
        return "Reavaliação"
    return "Aula Expositiva"


def classify_modulo(atividade: str) -> str:
    if re.search(r"[Nn]ivelamento|[Pp]resentação\s+do\s+curso", atividade):
        return "Módulo 0 - Introdução"
    if re.search(r"[Ee]scopo|[Cc]onceitos\s+[Bb]ásicos\s+de\s+[Mm]edição", atividade):
        return "Módulo 1 - Fundamentos de Medição"
    if re.search(r"[Mm]étrica|[Pp]ontos\s+de\s+[Ff]unção|[Mm]odelo|[Mm]edições|[Ee]ntidades|[Mm]odernas", atividade):
        return "Módulo 2 - Métricas e Modelos"
    if re.search(r"[Ee]xperimentação|[Mm]étodos.*[Ee]mpíric|[Rr]evisão\s+[Ss]istemática|[Vv]ariáve|[Ee]tapas|[Oo]peração", atividade):
        return "Módulo 3 - Experimentação"
    if re.search(r"[Ee]statística|[Dd]ata\s+[Aa]nalysis|[Dd]ecisão", atividade):
        return "Módulo 4 - Análise Estatística"
    if re.search(r"[Aa]valiação|[Pp]rova|[Rr]eavaliação|[Rr]evisão\s+de", atividade):
        return "Avaliações"
    if re.search(r"[Tt]rabalho|[Ee]nunciado|[Rr]elatório|[Dd]ocumentação", atividade):
        return "Módulo 5 - Prática e Encerramento"
    return "Módulo 3 - Experimentação"


def aula_vinculada(atividade: str) -> str:
    return ATIVIDADE_AULA_MAP.get(atividade, "")
