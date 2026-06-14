"""Pipeline do slice de relacoes: artigos x ementa -> relacoes.csv."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.contract import RELACOES_FIELDS, Bundle
from medicao.shared.storage import write_csv
from medicao.slices.relacoes import scoring


def run(
    bundle: str = config.DEFAULT_BUNDLE,
    write: bool = True,
    artigos: list[dict] | None = None,
    ementa: list[dict] | None = None,
) -> list[dict]:
    """Liga cada artigo aos itens de ementa com termos em comum."""
    b = Bundle(bundle)
    artigos = artigos if artigos is not None else b.load("artigos")
    ementa = ementa if ementa is not None else b.load("ementa")
    print(f"[relacoes] {len(artigos)} artigos x {len(ementa)} itens de ementa")

    termos_ementa = [(item, scoring.ementa_terms(item)) for item in ementa]

    relacoes = []
    for art in artigos:
        ta = scoring.artigo_terms(art)
        if not ta:
            continue
        for item, te in termos_ementa:
            if not te:
                continue
            pontos = scoring.score(ta, te)
            if pontos >= scoring.SCORE_MINIMO:
                relacoes.append(
                    {
                        "artigo_id": art.get("id", ""),
                        "artigo_titulo": art.get("title", ""),
                        "artigo_arquivo": art.get("arquivo", ""),
                        "ementa_id": item.get("id", ""),
                        "ementa_topico": item.get("topico", ""),
                        "score_relevancia": pontos,
                        "total_temas": len(te),
                        "percentual_match": round(pontos / len(te) * 100, 1),
                    }
                )

    relacoes.sort(key=lambda r: (-r["score_relevancia"], str(r["artigo_id"])))
    print(f"[relacoes] {len(relacoes)} relacoes (score >= {scoring.SCORE_MINIMO})")

    if write:
        b.dir.mkdir(parents=True, exist_ok=True)
        write_csv(b.path("relacoes"), relacoes, RELACOES_FIELDS)
        print(f"[relacoes] -> {b.path('relacoes')}")

    return relacoes


if __name__ == "__main__":
    run()
