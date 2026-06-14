"""Pipeline do slice web: agrega os datasets em data.json para o index.html."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.storage import read_csv, write_json


def run(
    write: bool = True,
    artigos: list[dict] | None = None,
    aulas: list[dict] | None = None,
    cronograma: list[dict] | None = None,
    relacoes: list[dict] | None = None,
) -> dict:
    """Monta o JSON unificado. Usa os datasets em memória ou lê os CSVs."""
    data = {
        "artigos": artigos if artigos is not None else read_csv(config.DATASET_ARTIGOS),
        "aulas": aulas if aulas is not None else read_csv(config.DATASET_AULAS),
        "cronograma": cronograma if cronograma is not None else read_csv(config.DATASET_CRONOGRAMA),
        "relacoes_artigo_aula": relacoes if relacoes is not None else read_csv(config.DATASET_RELACOES),
    }

    if write:
        write_json(config.WEB_DATA_JSON, data)
        print(f"[web] -> {config.WEB_DATA_JSON}")

    return data


if __name__ == "__main__":
    run()
