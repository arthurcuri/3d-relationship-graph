"""Orquestrador: executa os slices na ordem correta de dependência."""

from __future__ import annotations

from medicao.shared import config
from medicao.slices import artigos, aulas, cronograma, grafo, relacoes, web


def run_all() -> None:
    """Executa o pipeline completo, reaproveitando os dados em memória."""
    config.ensure_dirs()
    print("=" * 60)
    print("PIPELINE DE MEDIÇÃO DE SOFTWARE")
    print("=" * 60)

    registros_artigos = artigos.run()
    registros_aulas = aulas.run()
    registros_cronograma = cronograma.run()
    registros_relacoes = relacoes.run(artigos=registros_artigos)

    web.run(
        artigos=registros_artigos,
        aulas=registros_aulas,
        cronograma=registros_cronograma,
        relacoes=registros_relacoes,
    )
    grafo.run(
        artigos=registros_artigos,
        aulas=registros_aulas,
        cronograma=registros_cronograma,
    )

    print("=" * 60)
    print("PRONTO!")
    print(f"  Artigos:   {len(registros_artigos)}")
    print(f"  Aulas:     {len(registros_aulas)}")
    print(f"  Cronograma:{len(registros_cronograma)}")
    print(f"  Relações:  {len(registros_relacoes)}")
    print("=" * 60)


if __name__ == "__main__":
    run_all()
