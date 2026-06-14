"""Pipeline do slice grafo: bundle -> graph.json generico."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.contract import Bundle
from medicao.shared.storage import write_json
from medicao.slices.grafo import builder


def run(
    bundle: str = config.DEFAULT_BUNDLE,
    write: bool = True,
    artigos: list[dict] | None = None,
    ementa: list[dict] | None = None,
    aulas: list[dict] | None = None,
    relacoes: list[dict] | None = None,
) -> dict:
    b = Bundle(bundle)
    manifest = b.load_manifest()

    artigos = artigos if artigos is not None else b.load("artigos")
    ementa = ementa if ementa is not None else b.load("ementa")
    aulas = aulas if aulas is not None else b.load("aulas")
    relacoes = relacoes if relacoes is not None else b.load("relacoes")

    grafo = builder.build(
        name=bundle,
        titulo=manifest.get("titulo", bundle),
        node_types=manifest.get("node_types", {}),
        artigos=artigos,
        ementa=ementa,
        aulas=aulas,
        relacoes=relacoes,
    )

    if write:
        write_json(b.graph_path, grafo)
        c = grafo["meta"]["counts"]
        print(f"[grafo] -> {b.graph_path} ({c['nos']} nos, {c['arestas']} arestas)")

    return grafo


if __name__ == "__main__":
    run()
