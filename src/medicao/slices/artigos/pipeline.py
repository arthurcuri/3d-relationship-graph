"""Pipeline do slice de artigos: PDFs -> artigos.csv (schema fundido ACARI+medicao)."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.contract import ARTIGOS_FIELDS, Bundle
from medicao.shared.pdf import PdfDocument, list_pdfs, read_pdf
from medicao.shared.storage import write_csv
from medicao.shared.text import clean_text, most_common_year
from medicao.slices.artigos import detectors, extraction


def process(doc: PdfDocument, artigo_id: int) -> dict:
    """Extrai todos os campos (nucleo ACARI + ricos de medicao) de um artigo."""
    head = doc.head_text(5)
    head3 = doc.head_text(3)
    full = doc.full_text
    meta = doc.metadata

    titulo = extraction.resolve_title(meta.get("title", "") or "", head3, doc.filename)

    return {
        "id": artigo_id,
        "title": titulo,
        "article_authors": clean_text(meta.get("author", "") or ""),
        "year": most_common_year(head),
        "doi": extraction.extract_doi(head),
        "abstract": extraction.extract_abstract(head),
        "keywords": extraction.extract_keywords(head),
        "venue_type": "",
        "in_statistical_test": "True",
        "cohort": "",
        "arquivo": doc.filename,
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
        "veiculo_publicacao": extraction.extract_venue(head),
        "caminho_pdf": config.artigo_web_path(doc.filename),
    }


def run(bundle: str = config.DEFAULT_BUNDLE, write: bool = True) -> list[dict]:
    """Processa os PDFs de artigos e grava o CSV canonico no bundle."""
    b = Bundle(bundle)
    filenames = list_pdfs(config.ARTIGOS_DIR)
    print(f"[artigos] {len(filenames)} PDFs encontrados")

    registros = []
    for i, filename in enumerate(filenames, 1):
        filepath = config.ARTIGOS_DIR / filename
        try:
            doc = read_pdf(filepath)
            registro = process(doc, i)
        except Exception as exc:  # noqa: BLE001
            registro = {f: "" for f in ARTIGOS_FIELDS}
            registro.update(
                {
                    "id": i,
                    "title": filename,
                    "arquivo": filename,
                    "in_statistical_test": "True",
                    "abstract": f"Erro ao processar: {exc}",
                    "caminho_pdf": config.artigo_web_path(filename),
                }
            )
        registros.append(registro)
        print(f"  [{i}/{len(filenames)}] {filename[:60]}")

    if write:
        b.dir.mkdir(parents=True, exist_ok=True)
        write_csv(b.path("artigos"), registros, ARTIGOS_FIELDS)
        print(f"[artigos] -> {b.path('artigos')} ({len(registros)} registros)")

    return registros


if __name__ == "__main__":
    run()
