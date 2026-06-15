"""Extração de campos pontuais de um artigo (abstract, keywords, DOI, etc.)."""

from __future__ import annotations

import os
import re

from medicao.shared.text import clean_text

# Em-dash (fora do Latin-1) usado como separador em alguns cabeçalhos.
_EM = "\u2014"

ABSTRACT_PATTERNS = [
    r"[Aa]bstract[\s\.\-:" + _EM + r"\n]*(.{50,2000}?)(?:[Kk]ey\s*[Ww]ords|[Ii]ndex\s+[Tt]erms|[Ii]ntroduction|1[\.\s]+[Ii]ntro|I\.\s+INTRO)",
    r"ABSTRACT[\s\.\-:" + _EM + r"\n]*(.{50,2000}?)(?:KEYWORDS|KEY\s*WORDS|INDEX\s+TERMS|INTRODUCTION|I\.\s+INTRO|1[\.\s])",
    r"[Rr]esumo[\s\.\-:" + _EM + r"\n]*(.{50,2000}?)(?:[Pp]alavras|[Ii]ntrodução|1[\.\s])",
    r"[Aa]bstract[\s\.\-:" + _EM + r"\n]*(.{50,2000}?)(?:\n\s*\n\s*\n)",
]

KEYWORDS_PATTERNS = [
    r"[Kk]ey\s*[Ww]ords[\s\.\-:" + _EM + r"]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z]|ACM|IEEE|1[\.\s]+[Ii]ntro)",
    r"KEYWORDS[\s\.\-:" + _EM + r"]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z]|ACM|IEEE)",
    r"[Pp]alavras[\s\-]*[Cc]have[\s\.\-:" + _EM + r"]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]|1[\.\s]+[Ii]ntro)",
    r"Index [Tt]erms[\s\.\-:" + _EM + r"]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z])",
]

_BAD_TITLE_PATTERNS = [r"\.dvi$", r"\.tex$", r"^paper_", r"^manuscript", r"^\d+$", r"^untitled"]


def extract_abstract(text: str) -> str:
    for pattern in ABSTRACT_PATTERNS:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            abstract = clean_text(match.group(1))
            return abstract[:597] + "..." if len(abstract) > 600 else abstract
    # Fallback: primeiro parágrafo longo
    for line in text[:3000].split("\n")[:40]:
        if len(line.strip()) > 150:
            abstract = clean_text(line.strip())
            return abstract[:597] + "..." if len(abstract) > 600 else abstract
    return ""


def extract_keywords(text: str) -> str:
    for pattern in KEYWORDS_PATTERNS:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            kw = clean_text(match.group(1))
            kw = re.sub(r"[\.\s]+$", "", kw)
            return kw[:300]
    return ""


def extract_doi(text: str) -> str:
    match = re.search(r"(10\.\d{4,}/[^\s,;\"\'<>]+)", text[:5000])
    return match.group(1).rstrip(".") if match else ""


def extract_venue(text: str) -> str:
    patterns = [
        r"(?:Published in|Appeared in|Proceedings of|In:)\s*(.{10,150}?)(?:\.|,|\n)",
        r"(IEEE\s+[A-Za-z\s]+(?:Conference|Transactions|Journal|Magazine|Software)[A-Za-z\s]*)",
        r"(ACM\s+[A-Za-z\s]+(?:Conference|Symposium|Journal)[A-Za-z\s]*)",
        r"(Information and Software Technology|Empirical Software Engineering|Journal of Systems and Software)",
        r"(ICSE|ESEC/FSE|ASE|MSR|ICSME|SANER|TSE|TOSEM|IST|JSS|EMSE)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:3000])
        if match:
            return clean_text(match.group(1))[:150]
    return ""


def extract_venue_type(text: str) -> str:
    """Classifica localmente o tipo de veiculo quando a API externa nao rodou."""
    zone = text[:5000].lower()
    if re.search(r"\b(arxiv|preprint)\b", zone):
        return "preprint"
    if re.search(r"\b(thesis|dissertation|monografia|tcc)\b", zone):
        return "thesis"
    if re.search(r"\btechnical\s+report\b|relat[oó]rio\s+t[eé]cnico", zone):
        return "report"
    if re.search(r"\b(acm\s+queue|magazine|potentials)\b", zone):
        return "magazine"
    if re.search(
        r"\b(proceedings|conference|symposium|workshop|congress|icse|esem|ease|"
        r"fse|ase|msr|icsme|saner|sbes|sbqs|sac|chi)\b",
        zone,
    ):
        return "conference"
    if re.search(
        r"\b(journal|transactions|empirical software engineering|information and software technology|"
        r"journal of systems and software|software quality journal|tosem|tse)\b",
        zone,
    ):
        return "journal"
    if re.search(r"\b(book|monograph|isbn)\b", zone):
        return "book"
    return ""


def count_references(text: str) -> int:
    section = re.search(
        r"(?:REFERENCES|References|Referências|REFERÊNCIAS|BIBLIOGRAPHY)\s*\n(.+)",
        text,
        re.DOTALL,
    )
    if not section:
        return 0
    ref_text = section.group(1)
    numbered = re.findall(r"\[\d+\]", ref_text)
    if numbered:
        nums = [int(re.search(r"\d+", n).group()) for n in numbered]
        return max(nums) if nums else 0
    lines = [l for l in ref_text.split("\n") if l.strip() and len(l.strip()) > 20]
    return min(len(lines), 200) if lines else 0


def extract_sample_size(text: str) -> str:
    text_lower = text.lower()
    patterns = [
        r"(\d+)\s+(?:participants?|subjects?|developers?|students?|professionals?|respondents?|projects?)",
        r"sample\s+(?:size|of)\s+(?:is\s+)?(\d+)",
        r"(\d+)\s+(?:open[\-\s]source|oss)\s+projects?",
        r"(\d+)\s+repositories",
        r"we\s+(?:selected|analyzed|collected|studied|surveyed)\s+(\d+)",
        r"dataset\s+(?:of|with|contains?|including)\s+(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match and match.group(1):
            try:
                n = int(match.group(1))
                if 2 <= n <= 1_000_000:
                    return str(n)
            except ValueError:
                pass
    return ""


def _looks_bad(title: str) -> bool:
    return len(title) < 10 or any(re.search(p, title.lower()) for p in _BAD_TITLE_PATTERNS)


def resolve_title(metadata_title: str, first_page_text: str, filename: str) -> str:
    """Resolve o melhor título: metadados -> primeira página -> nome do arquivo."""
    title = clean_text(metadata_title)
    if not _looks_bad(title):
        return title

    if first_page_text:
        for line in first_page_text.strip().split("\n")[:10]:
            line = line.strip()
            if (
                15 < len(line) < 200
                and not re.match(r"^(Abstract|Keywords|Author|IEEE|ACM|\d)", line)
            ):
                return line

    if not title or len(title) < 5:
        return re.sub(r"_", " ", os.path.splitext(filename)[0])
    return title


def detect_language(head_text: str) -> str:
    if re.search(
        r"\b(resumo|introdução|palavras[\-\s]chave|objetivo|conclusão)\b",
        head_text.lower(),
    ):
        return "PT"
    return "EN"
