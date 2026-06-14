"""Extração de conteúdo dos slides de aula (tópicos, conceitos, etc.).

Os slides são gerados via LaTeX e o texto extraído costuma trazer acentos
quebrados (ex.: ``Sum´ario``, ``medi¸cao``). Por isso a detecção de sumário
usa o prefixo solto ``^Sum`` e os padrões priorizam termos ASCII/ISO quando
possível. Caracteres fora do Latin-1 (bullets, alfa grego) são escritos como
escapes ``\\u`` para preservar a codificação do arquivo-fonte.
"""

from __future__ import annotations

import re

from medicao.shared.text import clean_text

# Glifos de bullet usados em listas de slides (fora do Latin-1).
_BULLET_CHARS = "\u2022\u25aa\u25e6\u27a2\u25ba\u25cf\u25cb"

CONCEPT_PATTERNS = {
    "Métricas de Software": r"métrica[s]?\s+de\s+software|software\s+metric",
    "GQM (Goal-Question-Metric)": r"\bgqm\b|goal[\-\s]question[\-\s]metric",
    "Medição de Software": r"medição\s+de\s+software|software\s+measurement",
    "Experimentação": r"experimentação|experiment(?:ation|s?\b)",
    "Variáveis Dependentes/Independentes": r"variáve[il]\s+(?:dependente|independente)|dependent\s+variable|independent\s+variable",
    "Hipótese Nula/Alternativa": r"hipótese\s+(?:nula|alternativa)|null\s+hypothesis|h[01]",
    "Teste de Hipótese": r"teste\s+de\s+hipótese|hypothesis\s+test",
    "Distribuição Normal": r"distribuição\s+normal|normal\s+distribution|gaussiana",
    "Complexidade Ciclomática": r"complexidade\s+ciclomática|cyclomatic\s+complexity",
    "LOC/SLOC": r"\b(?:loc|sloc)\b|lines?\s+of\s+code|linhas\s+de\s+código",
    "Pontos de Função": r"pontos?\s+de\s+função|function\s+point",
    "CMMI": r"\bcmmi\b",
    "ISO/IEC 25010": r"iso[\s/]*iec\s*25010|square",
    "ISO/IEC 9126": r"iso[\s/]*iec\s*9126",
    "ISO/IEC 15939": r"iso[\s/]*iec\s*15939",
    "Validade Interna": r"validade\s+interna|internal\s+validity",
    "Validade Externa": r"validade\s+externa|external\s+validity",
    "Revisão Sistemática": r"revisão\s+sistemática|systematic\s+(?:literature\s+)?review",
    "Estudo de Caso": r"estudo\s+de\s+caso|case\s+study",
    "Survey": r"\bsurvey\b|questionário",
    "Regressão": r"regressão|regression",
    "Correlação": r"correlação|correlation",
    "Desvio Padrão": r"desvio\s+padrão|standard\s+deviation",
    "Média/Mediana": r"\bmédia\b.*\bmediana\b|\bmean\b.*\bmedian\b",
    "Acoplamento": r"acoplamento|\bcoupling\b|\bcbo\b",
    "Coesão": r"coesão|\bcohesion\b|\blcom\b",
    "Dívida Técnica": r"dívida\s+técnica|technical\s+debt",
    "Code Churn": r"code\s+churn",
    "Halstead": r"halstead",
    "McCabe": r"mccabe",
    "COCOMO": r"\bcocomo\b",
    "Six Sigma": r"six\s+sigma|seis\s+sigma",
    "Story Points": r"story\s+point",
    "Velocity": r"\bvelocity\b|velocidade",
    "Lead Time": r"lead\s+time",
    "DORA Metrics": r"\bdora\b",
    "Produtividade": r"produtividade|productivity",
    "Confiabilidade": r"confiabilidade|reliability",
    "Manutenibilidade": r"manutenibilidade|maintainability",
    "Qualidade de Software": r"qualidade\s+de\s+software|software\s+quality",
    "Processo de Software": r"processo\s+de\s+software|software\s+process",
    "Amostragem": r"amostragem|sampling",
    "População": r"população|population",
    "Nível de Significância": r"nível\s+de\s+significância|significance\s+level|p[\-\s]?value|" + "\u03b1" + r"\s*=",
    "Intervalo de Confiança": r"intervalo\s+de\s+confiança|confidence\s+interval",
}


def extract_topics(text: str) -> list[str]:
    """Extrai tópicos do sumário (com fallback para bullets/numeração)."""
    lines = text.split("\n")

    in_sumario = False
    sumario_topics: list[str] = []
    for line in lines:
        line = line.strip()
        if re.match(r"^Sum", line) or re.match(r"^Conte", line):
            in_sumario = True
            continue
        if in_sumario:
            if re.match(r"^Prof\.|^\d+\s*/\s*\d+", line):
                in_sumario = False
                continue
            if re.match(r"^\d+\s+[A-ZÀ-Ú]", line):
                topic = re.sub(r"^\d+\s+", "", line).strip()
                if topic and topic not in sumario_topics:
                    sumario_topics.append(topic)
            elif len(line) > 3 and line[0].isupper() and len(line) < 120:
                if line not in sumario_topics and not re.match(r"^(Prof|Medi|Figura)", line):
                    sumario_topics.append(line)

    if sumario_topics:
        return sumario_topics[:30]

    topics: list[str] = []
    bullet_re = rf"^[{_BULLET_CHARS}\-]\s*"
    for line in lines:
        line = line.strip()
        if re.match(bullet_re, line):
            topic = re.sub(bullet_re, "", line).strip()
            if 5 < len(topic) < 200:
                topics.append(topic)
        elif re.match(r"^\d+[\.\)]\s+[A-ZÀ-Ú]", line):
            topic = re.sub(r"^\d+[\.\)]\s+", "", line).strip()
            if 5 < len(topic) < 200 and topic not in topics:
                topics.append(topic)

    return topics[:25]


def extract_concepts(text: str) -> list[str]:
    text_lower = text.lower()
    return [
        name for name, pattern in CONCEPT_PATTERNS.items()
        if re.search(pattern, text_lower)
    ]


def extract_references(text: str) -> list[str]:
    refs: list[str] = []
    patterns = [
        r"(?:Referências?|References?|Bibliografia|REFERÊNCIAS)\s*[:\n](.+?)(?:\n\s*\n|\Z)",
        r"(?:Fonte|Source)[:\s]+(.+?)(?:\n|$)",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, re.DOTALL):
            for line in match.split("\n"):
                line = line.strip()
                if len(line) > 20 and not line.startswith("http"):
                    refs.append(clean_text(line))
    return refs


def extract_objectives(text: str) -> list[str]:
    objectives: list[str] = []
    patterns = [
        r"(?:[Oo]bjetivo[s]?|[Oo]bjective[s]?|[Mm]eta[s]?)[:\s\n]+(.{20,500}?)(?:\n\s*\n)",
        r"(?:Ao final|Após|After).*?(?:aluno|estudante|student|you).*?(?:será capaz|poderá|will be able)(.{20,300})",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, re.DOTALL):
            obj = clean_text(match)
            if obj:
                objectives.append(obj)
    return objectives


def extract_slide_titles(pages: list[str]) -> list[str]:
    """Título representativo de cada slide (primeira linha substantiva)."""
    titles: list[str] = []
    for page_text in pages:
        for line in page_text.strip().split("\n")[:3]:
            line = line.strip()
            if (
                3 < len(line) < 120
                and not re.match(r"^(Prof\.|Figura|\d+\s*/\s*\d+|Sum|Medi)", line)
                and line[0:1].isupper()
                and line not in titles
            ):
                titles.append(line)
                break

    unique: list[str] = []
    seen: set[str] = set()
    for t in titles:
        key = t.lower().strip()
        if key not in seen and len(t) > 5:
            seen.add(key)
            unique.append(t)
    return unique


def extract_summary(text: str) -> str:
    """Resume os parágrafos substanciais dos slides."""
    paragraphs: list[str] = []
    current = ""
    for line in text.split("\n"):
        line = line.strip()
        if len(line) > 50 and not re.match(r"^(Prof\.|Figura|\d+\s*/\s*\d+)", line):
            current += " " + line
        elif current:
            if len(current.strip()) > 80:
                paragraphs.append(clean_text(current))
            current = ""

    if not paragraphs:
        return ""
    resumo = " | ".join(paragraphs[:10])
    return resumo[:997] + "..." if len(resumo) > 1000 else resumo
