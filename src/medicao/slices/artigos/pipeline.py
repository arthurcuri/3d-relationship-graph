"""Pipeline do slice de artigos: PDFs -> dataset_artigos.csv."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.pdf import PdfDocument, list_pdfs, read_pdf
from medicao.shared.storage import write_csv
from medicao.shared.text import clean_text, most_common_year
from medicao.slices.artigos import detectors, extraction
from medicao.slices.artigos.schema import FIELDS


def process(doc: PdfDocument, artigo_id: int) -> dict:
    """Extrai todos os campos ricos de um artigo já lido."""
    head = doc.head_text(5)
    head3 = doc.head_text(3)
    full = doc.full_text
    meta = doc.metadata

    titulo = extraction.resolve_title(meta.get("title", "") or "", head3, doc.filename)

    return {
        "id": artigo_id,
        "arquivo": doc.filename,
        "titulo": titulo,
        "autores": clean_text(meta.get("author", "") or ""),
        "ano": most_common_year(head),
        "abstract": extraction.extract_abstract(head),
        "keywords": extraction.extract_keywords(head),
        "doi": extraction.extract_doi(head),
        "veiculo_publicacao": extraction.extract_venue(head),
        "num_paginas": doc.page_count,
        "num_referencias": extraction.count_references(full),
        "tamanho_amostra": extraction.extract_sample_size(full),
        "metodologia": detectors.detect_methodology(full),
        "areas_pesquisa": detectors.classify_area(full, doc.filename),
        "metricas_mencionadas": detectors.detect_metrics(full),
        "metodos_estatisticos": detectors.detect_statistical_methods(full),
        "ferramentas_tecnologias": detectors.detect_tools(full),
        "padroes_normas": detectors.detect_standards(full),
        "contexto_dominio": detectors.detect_domains(full),
        "idioma": extraction.detect_language(head),
        "caminho_pdf": config.artigo_web_path(doc.filename),
    }


def run(write: bool = True) -> list[dict]:
    """Processa todos os PDFs de artigos e (opcionalmente) grava o CSV."""
    filenames = list_pdfs(config.ARTIGOS_DIR)
    print(f"[artigos] {len(filenames)} PDFs encontrados")

    registros = []
    for i, filename in enumerate(filenames, 1):
        filepath = config.ARTIGOS_DIR / filename
        try:
            doc = read_pdf(filepath)
            registro = process(doc, i)
        except Exception as exc:  # noqa: BLE001 - registra erro sem abortar lote
            registro = {f: "" for f in FIELDS}
            registro["id"] = i
            registro["arquivo"] = filename
            registro["abstract"] = f"Erro ao processar: {exc}"
            registro["caminho_pdf"] = config.artigo_web_path(filename)
        registros.append(registro)
        print(f"  [{i}/{len(filenames)}] {filename[:60]}")

    if write:
        write_csv(config.DATASET_ARTIGOS, registros, FIELDS)
        print(f"[artigos] -> {config.DATASET_ARTIGOS} ({len(registros)} registros)")

    return registros


if __name__ == "__main__":
    run()
