"""Pipeline do slice de aulas: PDFs de slides -> dataset_aulas.csv."""

from __future__ import annotations

import os
import re

from medicao.shared import config
from medicao.shared.pdf import PdfDocument, list_pdfs, read_pdf
from medicao.shared.storage import write_csv
from medicao.shared.text import clean_text
from medicao.slices.aulas import extraction
from medicao.slices.aulas.schema import DISCIPLINA, FIELDS, PROFESSOR_PADRAO

# Separadores de subtítulo no nome do arquivo (hífen, en-dash, dois-pontos).
_SEP_SUBTITULO = r"^Aula\s*\d+\s*[\-" + "\u2013" + r":]\s*"


def _numero_aula(filename: str, fallback: int) -> str:
    match = re.search(r"[Aa]ula\s*(\d+)", filename)
    return match.group(1) if match else str(fallback)


def _subtitulo(filename: str) -> str:
    base = os.path.splitext(filename)[0]
    subtitulo = re.sub(_SEP_SUBTITULO, "", base).strip()
    return subtitulo if subtitulo != base else "Introdução ao Curso"


def _professor(first_page: str) -> str:
    match = re.search(r"Prof\.?\s*(.+?)(?:\n|$)", first_page)
    if match:
        nome = clean_text(match.group(1))
        if nome:
            return nome if nome.lower().startswith("prof") else f"Prof. {nome}"
    return PROFESSOR_PADRAO


def process(doc: PdfDocument, aula_id: int) -> dict:
    full = doc.full_text
    first_page = doc.pages[0] if doc.pages else ""

    numero = _numero_aula(doc.filename, aula_id)
    subtitulo = _subtitulo(doc.filename)
    topicos = extraction.extract_topics(full)
    conceitos = extraction.extract_concepts(full)
    referencias = extraction.extract_references(full)
    objetivos = extraction.extract_objectives(full)

    return {
        "id": aula_id,
        "arquivo": doc.filename,
        "numero_aula": numero,
        "titulo": f"Aula {numero} - {subtitulo}",
        "subtitulo": subtitulo,
        "professor": _professor(first_page),
        "disciplina": DISCIPLINA,
        "num_slides": doc.page_count,
        "topicos": "; ".join(topicos[:20]),
        "conceitos": "; ".join(conceitos),
        "referencias": "; ".join(referencias[:10]),
        "objetivos": "; ".join(objetivos[:5]),
        "resumo": extraction.extract_summary(full),
        "caminho_pdf": config.aula_web_path(doc.filename),
    }


def run(write: bool = True) -> list[dict]:
    filenames = list_pdfs(config.AULAS_DIR)
    print(f"[aulas] {len(filenames)} PDFs encontrados")

    registros = []
    for i, filename in enumerate(filenames, 1):
        filepath = config.AULAS_DIR / filename
        try:
            doc = read_pdf(filepath)
            registro = process(doc, i)
        except Exception as exc:  # noqa: BLE001
            registro = {f: "" for f in FIELDS}
            registro.update(
                {
                    "id": i,
                    "arquivo": filename,
                    "numero_aula": str(i),
                    "titulo": os.path.splitext(filename)[0],
                    "professor": PROFESSOR_PADRAO,
                    "disciplina": DISCIPLINA,
                    "resumo": f"Erro: {exc}",
                    "caminho_pdf": config.aula_web_path(filename),
                }
            )
        registros.append(registro)
        print(f"  [{i}/{len(filenames)}] {filename[:60]}")

    if write:
        write_csv(config.DATASET_AULAS, registros, FIELDS)
        print(f"[aulas] -> {config.DATASET_AULAS} ({len(registros)} registros)")

    return registros


if __name__ == "__main__":
    run()
