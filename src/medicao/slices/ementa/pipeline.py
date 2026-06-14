"""Pipeline do slice de ementa: ementa.csv -> ementa.txt (+ registros)."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.contract import Bundle
from medicao.slices.ementa.builder import to_ementa_text


def run(bundle: str = config.DEFAULT_BUNDLE, write: bool = True) -> list[dict]:
    """Carrega a ementa do bundle e gera o ementa.txt para o ACARI."""
    b = Bundle(bundle)
    if not b.has("ementa"):
        raise FileNotFoundError(
            f"ementa.csv ausente em {b.dir}. Use o template em "
            f"{config.TEMPLATES_DIR / 'ementa.template.csv'}."
        )

    registros = b.load("ementa")
    print(f"[ementa] {len(registros)} itens de ementa")

    if write:
        titulo = b.load_manifest().get("titulo", bundle)
        ementa_txt = b.dir / "ementa.txt"
        ementa_txt.write_text(to_ementa_text(registros, titulo), encoding="utf-8")
        print(f"[ementa] -> {ementa_txt}")

    return registros


if __name__ == "__main__":
    run()
