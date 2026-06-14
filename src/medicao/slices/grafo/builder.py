"""Construcao de um grafo generico e auto-descritivo a partir de um bundle.

O grafo resultante e independente do dominio: a visualizacao 3D apenas le os
``node_types`` (cor/forma/rotulo) e renderiza nos e arestas, de modo que novos
bundles ou novos tipos de no funcionem sem alterar o front-end.
"""

from __future__ import annotations

from medicao.shared.text import significant_terms

ARTIGO_SIM_THRESHOLD = 0.30

# Campos exibidos no painel de detalhe por tipo de no.
ARTIGO_DETAIL = [
    ("Autores", "article_authors"),
    ("Ano", "year"),
    ("Abstract", "abstract"),
    ("Keywords", "keywords"),
    ("DOI", "doi"),
    ("Areas", "areas_pesquisa"),
    ("Metricas", "metricas_mencionadas"),
    ("Metodologia", "metodologia"),
    ("Paginas", "num_paginas"),
]
EMENTA_DETAIL = [
    ("Modulo", "modulo"),
    ("Topico", "topico"),
    ("Descricao", "descricao"),
    ("Data", "data"),
]
AULA_DETAIL = [
    ("Professor", "professor"),
    ("Slides", "num_slides"),
    ("Topicos", "topicos"),
    ("Conceitos", "conceitos"),
]


def _detail(row: dict, fields: list[tuple[str, str]]) -> dict:
    return {label: row.get(key, "") for label, key in fields if row.get(key)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build(
    name: str,
    titulo: str,
    node_types: dict,
    artigos: list[dict],
    ementa: list[dict],
    aulas: list[dict],
    relacoes: list[dict],
) -> dict:
    nodes: list[dict] = []
    links: list[dict] = []

    # Artigos
    artigo_terms: dict[str, set[str]] = {}
    for a in artigos:
        nid = f"artigo_{a['id']}"
        artigo_terms[nid] = significant_terms(
            " ".join(str(a.get(c, "")) for c in ("areas_pesquisa", "metricas_mencionadas", "keywords"))
        )
        nodes.append(
            {
                "id": nid,
                "type": "artigo",
                "label": a.get("title", a.get("arquivo", "")),
                "pdf": a.get("caminho_pdf", ""),
                "detail": _detail(a, ARTIGO_DETAIL),
            }
        )

    # Ementa
    aula_por_arquivo = {a.get("arquivo", ""): f"aula_{a['id']}" for a in aulas}
    for e in ementa:
        nid = f"ementa_{e['id']}"
        nodes.append(
            {
                "id": nid,
                "type": "ementa",
                "label": e.get("topico", ""),
                "pdf": "",
                "detail": _detail(e, EMENTA_DETAIL),
            }
        )
        rel = e.get("aula_relacionada", "")
        if rel and rel in aula_por_arquivo:
            links.append({"source": nid, "target": aula_por_arquivo[rel], "type": "ementa_aula"})

    # Sequencia temporal da ementa
    try:
        ementa_sorted = sorted(ementa, key=lambda x: int(x["id"]))
    except (ValueError, KeyError):
        ementa_sorted = ementa
    for i in range(len(ementa_sorted) - 1):
        links.append(
            {
                "source": f"ementa_{ementa_sorted[i]['id']}",
                "target": f"ementa_{ementa_sorted[i + 1]['id']}",
                "type": "sequencia",
            }
        )

    # Aulas (opcional)
    ementa_terms = {
        f"ementa_{e['id']}": significant_terms(
            f"{e.get('modulo', '')} {e.get('topico', '')}"
        )
        for e in ementa
    }
    for a in aulas:
        nid = f"aula_{a['id']}"
        nodes.append(
            {
                "id": nid,
                "type": "aula",
                "label": a.get("titulo", ""),
                "pdf": a.get("caminho_pdf", ""),
                "detail": _detail(a, AULA_DETAIL),
            }
        )
        # liga a aula aos itens de ementa com termos em comum (mantem conexao)
        at = significant_terms(
            " ".join(str(a.get(c, "")) for c in ("titulo", "topicos", "conceitos"))
        )
        for eid, et in ementa_terms.items():
            if len(at & et) >= 2:
                links.append({"source": nid, "target": eid, "type": "ementa_aula"})

    # Relacoes artigo <-> ementa
    for r in relacoes:
        links.append(
            {
                "source": f"artigo_{r['artigo_id']}",
                "target": f"ementa_{r['ementa_id']}",
                "type": "artigo_ementa",
            }
        )

    # Similaridade artigo <-> artigo (constelacao tematica)
    ids = list(artigo_terms)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if _jaccard(artigo_terms[ids[i]], artigo_terms[ids[j]]) > ARTIGO_SIM_THRESHOLD:
                links.append({"source": ids[i], "target": ids[j], "type": "artigo_artigo"})

    counts = {
        "artigos": len(artigos),
        "ementa": len(ementa),
        "aulas": len(aulas),
        "nos": len(nodes),
        "arestas": len(links),
    }

    return {
        "meta": {"name": name, "titulo": titulo, "counts": counts},
        "node_types": node_types,
        "nodes": nodes,
        "links": links,
    }
