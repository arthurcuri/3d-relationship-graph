"""Pipeline do slice de relações: artigos + aulas -> dataset_relacoes_artigo_aula.csv.

A pontuação usa o texto completo de cada artigo. Para permitir execução isolada,
o pipeline relê os PDFs quando os textos não são injetados pelo orquestrador.
"""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.pdf import read_pdf
from medicao.shared.storage import read_csv, write_csv
from medicao.slices.relacoes import scoring

FIELDS = [
    "artigo_id",
    "artigo_titulo",
    "artigo_arquivo",
    "aula_arquivo",
    "score_relevancia",
    "total_temas_aula",
    "percentual_match",
]


def _carregar_artigos() -> list[dict]:
    return read_csv(config.DATASET_ARTIGOS)


def _texto_artigo(arquivo: str) -> str:
    try:
        return read_pdf(config.ARTIGOS_DIR / arquivo).full_text.lower()
    except Exception:  # noqa: BLE001
        return ""


def run(
    write: bool = True,
    artigos: list[dict] | None = None,
    textos: dict[str, str] | None = None,
) -> list[dict]:
    """Calcula relações artigo<->aula.

    Args:
        artigos: registros de artigos (default: lê o CSV processado).
        textos: mapa ``arquivo -> texto_completo_minúsculo`` (default: relê PDFs).
    """
    artigos = artigos if artigos is not None else _carregar_artigos()
    print(f"[relacoes] avaliando {len(artigos)} artigos x {len(scoring.AULA_TEMAS)} aulas")

    relacoes = []
    for art in artigos:
        arquivo = art["arquivo"]
        texto = textos.get(arquivo) if textos else None
        if texto is None:
            texto = _texto_artigo(arquivo)
        if not texto:
            continue

        for aula_arquivo, temas in scoring.AULA_TEMAS.items():
            pontos = scoring.score(texto, temas)
            if pontos >= scoring.SCORE_MINIMO:
                relacoes.append(
                    {
                        "artigo_id": int(art["id"]),
                        "artigo_titulo": art["titulo"],
                        "artigo_arquivo": arquivo,
                        "aula_arquivo": aula_arquivo,
                        "score_relevancia": pontos,
                        "total_temas_aula": len(temas),
                        "percentual_match": round(pontos / len(temas) * 100, 1),
                    }
                )

    relacoes.sort(key=lambda r: (-r["score_relevancia"], r["artigo_id"]))
    print(f"[relacoes] {len(relacoes)} relações (score >= {scoring.SCORE_MINIMO})")

    if write:
        write_csv(config.DATASET_RELACOES, relacoes, FIELDS)
        print(f"[relacoes] -> {config.DATASET_RELACOES}")

    return relacoes


if __name__ == "__main__":
    run()
