"""Semeia data/ementa/ementa.csv (dataset da disciplina) a partir da fonte real.

Preferencia de fonte (bundle medicao):
1. ``data/ementa/ementa.pdf`` -> parse das "Unidades de Ensino".
2. ``data/ementa/cronograma_atividades.csv`` -> fallback (cronograma).

Para outros bundles, o usuario preenche ementa.csv pelo template.
"""

from __future__ import annotations

import re

from medicao.shared import config
from medicao.shared.contract import EMENTA_FIELDS
from medicao.shared.pdf import read_pdf
from medicao.shared.storage import read_csv, write_csv

# ── fallback: cronograma -> aula relacionada ────────────────────────────────
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


def _modulo_cronograma(atividade: str) -> str:
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


def _from_cronograma() -> list[dict]:
    linhas = read_csv(config.CRONOGRAMA_CSV)
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
                "modulo": _modulo_cronograma(atividade),
                "topico": atividade,
                "descricao": "",
                "data": data,
                "aula_relacionada": ATIVIDADE_AULA_MAP.get(atividade, ""),
            }
        )
    return registros


def _from_pdf() -> list[dict]:
    """Parse das 'Unidades de Ensino' do plano de ensino (ementa.pdf)."""
    full = read_pdf(config.EMENTA_PDF).full_text
    section = re.search(
        r"Unidades de Ensino\s*(.+?)(?:Processo de Avalia|Processo de Avalia..o)",
        full,
        re.I | re.S,
    )
    if not section:
        return []

    # PyMuPDF costuma preservar as quebras; pypdf pode colar tudo em uma linha.
    # Reinsere quebras antes de marcadores "1." e "a." para manter o parser unico.
    section_text = re.sub(
        r"(?<!^)(?=(?:\d+|[a-z])\.\s*)",
        "\n",
        section.group(1),
    )
    secao = [l.strip() for l in section_text.split("\n")]

    mod_re = re.compile(r"^(\d+)\.\s+(.+?)(?:\s*\(([\d\s]+h/a)\))?\s*$")
    sub_re = re.compile(r"^([a-z])\.\s+(.+)$")

    registros = []
    seq = 0
    modulo_atual = ""
    pend_modulo_sem_sub = None
    for l in secao:
        if not l:
            continue
        m = mod_re.match(l)
        if m and not sub_re.match(l):
            # fecha modulo anterior sem subitens
            if pend_modulo_sem_sub:
                seq += 1
                registros.append(pend_modulo_sem_sub | {"id": seq})
            num, titulo, ch = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
            modulo_atual = f"{num}. {titulo}"
            pend_modulo_sem_sub = {
                "modulo": modulo_atual,
                "topico": titulo,
                "descricao": ch,
                "data": "",
                "aula_relacionada": "",
            }
            continue
        s = sub_re.match(l)
        if s and modulo_atual:
            pend_modulo_sem_sub = None  # modulo tem subitens
            seq += 1
            registros.append(
                {
                    "id": seq,
                    "modulo": modulo_atual,
                    "topico": s.group(2).strip(),
                    "descricao": "",
                    "data": "",
                    "aula_relacionada": "",
                }
            )
    if pend_modulo_sem_sub:
        seq += 1
        registros.append(pend_modulo_sem_sub | {"id": seq})

    return registros


def build() -> list[dict]:
    """Gera data/ementa/ementa.csv a partir do PDF (preferencial) ou cronograma."""
    if config.EMENTA_PDF.exists():
        registros = _from_pdf()
        fonte = "ementa.pdf"
        if not registros and config.CRONOGRAMA_CSV.exists():
            registros = _from_cronograma()
            fonte = "cronograma (fallback)"
    elif config.CRONOGRAMA_CSV.exists():
        registros = _from_cronograma()
        fonte = "cronograma"
    else:
        raise FileNotFoundError(
            f"Sem fonte de ementa: adicione {config.EMENTA_PDF} ou {config.CRONOGRAMA_CSV}."
        )

    config.EMENTA_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(config.EMENTA_SRC, registros, EMENTA_FIELDS)
    print(f"[ementa.migrate] {fonte} -> {config.EMENTA_SRC} ({len(registros)} itens)")
    return registros


if __name__ == "__main__":
    build()
