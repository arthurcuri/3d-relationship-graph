"""Pipeline do slice de ementa.

Fontes da disciplina (bundle medicao), em ``data/ementa/``:
- ``ementa.pdf`` (plano de ensino oficial) -> texto rico do ``ementa.txt`` (ACARI).
- ``ementa.csv`` (Unidades de Ensino, derivada do PDF) -> nos do grafo, sincronizada
  para o bundle.

Para outros bundles, a ementa.csv ja fica dentro do proprio bundle e o ementa.txt
e gerado a partir dela.
"""

from __future__ import annotations

import shutil

from medicao.shared import config
from medicao.shared.contract import Bundle
from medicao.shared.pdf import read_pdf
from medicao.slices.ementa.builder import to_ementa_text


def _sync_raw_to_bundle(b: Bundle) -> None:
    if b.name == config.DEFAULT_BUNDLE and config.EMENTA_SRC.exists():
        b.dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.EMENTA_SRC, b.path("ementa"))


def _ementa_text(b: Bundle, registros: list[dict]) -> str:
    """Texto da disciplina para o ACARI: PDF real (se houver) ou derivado do CSV."""
    if b.name == config.DEFAULT_BUNDLE and config.EMENTA_PDF.exists():
        return read_pdf(config.EMENTA_PDF).full_text
    titulo = b.load_manifest().get("titulo", b.name)
    return to_ementa_text(registros, titulo)


def run(bundle: str = config.DEFAULT_BUNDLE, write: bool = True) -> list[dict]:
    b = Bundle(bundle)
    _sync_raw_to_bundle(b)

    if not b.has("ementa"):
        raise FileNotFoundError(
            f"ementa ausente. Crie {config.EMENTA_SRC} (bundle medicao) ou "
            f"{b.path('ementa')} a partir do template "
            f"{config.TEMPLATES_DIR / 'ementa.template.csv'}."
        )

    registros = b.load("ementa")
    print(f"[ementa] {len(registros)} itens de ementa")

    if write:
        ementa_txt = b.dir / "ementa.txt"
        ementa_txt.write_text(_ementa_text(b, registros), encoding="utf-8")
        print(f"[ementa] -> {ementa_txt}")

    return registros


if __name__ == "__main__":
    run()
