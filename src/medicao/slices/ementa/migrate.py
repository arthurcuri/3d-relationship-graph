"""Migracao do cronograma de medicao para o dataset de ementa.

Especifico do bundle ``medicao``: le o CSV bruto de cronograma da disciplina e
o classifica em modulos, produzindo o ``ementa.csv`` no padrao do contrato.
Para outros bundles, o usuario preenche o template manualmente.
"""

from __future__ import annotations

import re

from medicao.shared import config
from medicao.shared.contract import EMENTA_FIELDS, Bundle
from medicao.shared.storage import read_csv, write_csv

CRONOGRAMA_CSV = config.AULAS_DIR / "cronograma_atividades.csv"

# Atividade do cronograma -> PDF de aula relacionada.
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


def _modulo(atividade: str) -> str:
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


def build(bundle: str = config.DEFAULT_BUNDLE) -> list[dict]:
    """Gera ementa.csv do bundle a partir do cronograma bruto de medicao."""
    linhas = read_csv(CRONOGRAMA_CSV)
    registros = []
    seq = 0
    for linha in linhas:
        data = (linha.get("Dia") or "").strip()
        atividade = (linha.get("Atividade") or "").strip()
        if not data and not atividade:
            continue
        seq += 1
        registros.append(
            {
                "id": seq,
                "modulo": _modulo(atividade),
                "topico": atividade,
                "descricao": "",
                "data": data,
                "aula_relacionada": ATIVIDADE_AULA_MAP.get(atividade, ""),
            }
        )

    b = Bundle(bundle)
    b.dir.mkdir(parents=True, exist_ok=True)
    write_csv(b.path("ementa"), registros, EMENTA_FIELDS)
    print(f"[ementa.migrate] -> {b.path('ementa')} ({len(registros)} itens)")
    return registros


if __name__ == "__main__":
    build()
