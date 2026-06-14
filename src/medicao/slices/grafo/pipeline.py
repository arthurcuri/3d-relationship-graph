"""Pipeline do slice grafo: datasets -> graph_data.json."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.storage import read_csv, write_json
from medicao.slices.grafo import builder


def run(
    write: bool = True,
    artigos: list[dict] | None = None,
    aulas: list[dict] | None = None,
    cronograma: list[dict] | None = None,
) -> dict:
    artigos = artigos if artigos is not None else read_csv(config.DATASET_ARTIGOS)
    aulas = aulas if aulas is not None else read_csv(config.DATASET_AULAS)
    cronograma = cronograma if cronograma is not None else read_csv(config.DATASET_CRONOGRAMA)

    grafo = builder.build(artigos, aulas, cronograma)

    if write:
        write_json(config.WEB_GRAPH_JSON, grafo)
        meta = grafo["metadata"]
        print(f"[grafo] -> {config.WEB_GRAPH_JSON} ({meta['total_nodes']} nós, {meta['total_edges']} arestas)")

    return grafo


if __name__ == "__main__":
    run()
