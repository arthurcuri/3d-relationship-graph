"""Orquestrador: gera um bundle completo a partir dos PDFs/dados de medicao."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.contract import Bundle
from medicao.slices import artigos, aulas, grafo, grupo2, relacoes, web
from medicao.slices.ementa import migrate as ementa_migrate
from medicao.slices.ementa import run as ementa_run

# Titulo amigavel por bundle (cai no nome do bundle se ausente).
TITULOS = {
    "medicao": "Medição e Experimentação em Engenharia de Software",
}


def run_all(bundle: str = config.DEFAULT_BUNDLE) -> None:
    """Pipeline completo do bundle: artigos + aulas + ementa + relacoes + grafo."""
    config.ensure_dirs(bundle)
    b = Bundle(bundle)
    print("=" * 60)
    print(f"PIPELINE DE BUNDLE: {bundle}")
    print("=" * 60)

    registros_artigos = artigos.run(bundle)
    registros_aulas = aulas.run(bundle)

    # ementa.csv e responsabilidade do usuario; so regeneramos a partir do PDF/cronograma
    # quando ementa.csv NAO existe ainda em data/<bundle>/ementa/.
    ementa_src = config.ementa_src(bundle)
    if not ementa_src.exists():
        ementa_pdf = config.ementa_pdf(bundle)
        cronograma = config.cronograma_csv(bundle)
        if ementa_pdf.exists() or cronograma.exists():
            ementa_migrate.build(bundle)
    registros_ementa = ementa_run(bundle)

    registros_relacoes = relacoes.run(
        bundle, artigos=registros_artigos, ementa=registros_ementa
    )

    grafo.run(
        bundle,
        artigos=registros_artigos,
        ementa=registros_ementa,
        aulas=registros_aulas,
        relacoes=registros_relacoes,
    )
    grupo2.run(bundle)

    titulo = TITULOS.get(bundle, bundle)
    b.write_manifest(titulo=titulo)
    web.run()

    print("=" * 60)
    print("PRONTO!")
    print(f"  Artigos:  {len(registros_artigos)}")
    print(f"  Ementa:   {len(registros_ementa)}")
    print(f"  Aulas:    {len(registros_aulas)}")
    print(f"  Relacoes: {len(registros_relacoes)}")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
