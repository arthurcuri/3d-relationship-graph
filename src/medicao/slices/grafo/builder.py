"""Construção do grafo de nós e arestas a partir dos datasets ricos."""

from __future__ import annotations

import math
import random
from collections import defaultdict

SIMILARITY_THRESHOLD = 0.25
CONCEPT_MIN_FREQ = 3


def _terms(text: str) -> set[str]:
    if not text:
        return set()
    return {t.strip().lower() for t in text.split(";") if len(t.strip()) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def build(artigos: list[dict], aulas: list[dict], cronograma: list[dict]) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []

    # --- Nós de artigos ---
    artigo_terms: dict[str, set[str]] = {}
    for art in artigos:
        node_id = f"artigo_{art['id']}"
        terms = (
            _terms(art.get("areas_pesquisa", ""))
            | _terms(art.get("metricas_mencionadas", ""))
            | _terms(art.get("metodologia", ""))
            | _terms(art.get("padroes_normas", ""))
            | _terms(art.get("keywords", ""))
        )
        artigo_terms[node_id] = terms
        nodes.append(
            {
                "id": node_id,
                "type": "artigo",
                "label": art.get("titulo", art.get("arquivo", "")),
                "titulo": art.get("titulo", ""),
                "autores": art.get("autores", ""),
                "ano": art.get("ano", ""),
                "abstract": art.get("abstract", ""),
                "keywords": art.get("keywords", ""),
                "doi": art.get("doi", ""),
                "veiculo": art.get("veiculo_publicacao", ""),
                "num_paginas": art.get("num_paginas", ""),
                "metodologia": art.get("metodologia", ""),
                "areas": art.get("areas_pesquisa", ""),
                "metricas": art.get("metricas_mencionadas", ""),
                "metodos_estatisticos": art.get("metodos_estatisticos", ""),
                "ferramentas": art.get("ferramentas_tecnologias", ""),
                "padroes": art.get("padroes_normas", ""),
                "dominio": art.get("contexto_dominio", ""),
                "idioma": art.get("idioma", ""),
                "caminho_pdf": art.get("caminho_pdf", ""),
                "size": max(5, int(art.get("num_paginas") or 10) / 3),
            }
        )

    # --- Nós de aulas ---
    aula_terms: dict[str, set[str]] = {}
    aula_por_arquivo: dict[str, str] = {}
    for aula in aulas:
        node_id = f"aula_{aula['id']}"
        aula_terms[node_id] = _terms(aula.get("conceitos", "")) | _terms(aula.get("topicos", ""))
        aula_por_arquivo[aula.get("arquivo", "")] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": "aula",
                "label": aula.get("titulo", ""),
                "subtitulo": aula.get("subtitulo", ""),
                "professor": aula.get("professor", ""),
                "num_slides": aula.get("num_slides", ""),
                "topicos": aula.get("topicos", ""),
                "conceitos": aula.get("conceitos", ""),
                "resumo": aula.get("resumo", ""),
                "caminho_pdf": aula.get("caminho_pdf", ""),
                "size": 12,
            }
        )

    # --- Nós de cronograma ---
    for item in cronograma:
        nodes.append(
            {
                "id": f"crono_{item['id']}",
                "type": "cronograma",
                "label": f"{item.get('data', '')} - {item.get('atividade', '')}",
                "data": item.get("data", ""),
                "atividade": item.get("atividade", ""),
                "tipo": item.get("tipo_atividade", ""),
                "modulo": item.get("modulo_tematico", ""),
                "aula_relacionada": item.get("aula_pdf", ""),
                "size": 4,
            }
        )

    # --- Nós de conceitos (clusters intermediários) ---
    freq: dict[str, int] = defaultdict(int)
    for terms in (*artigo_terms.values(), *aula_terms.values()):
        for t in terms:
            freq[t] += 1
    major = {k: v for k, v in freq.items() if v >= CONCEPT_MIN_FREQ}

    for concept, count in major.items():
        nodes.append(
            {
                "id": f"conceito_{concept.replace(' ', '_')}",
                "type": "conceito",
                "label": concept.title(),
                "frequencia": count,
                "size": min(15, 3 + count),
            }
        )

    # --- Arestas artigo/aula <-> conceito ---
    for node_id, terms in artigo_terms.items():
        for term in terms:
            if term in major:
                edges.append({"source": node_id, "target": f"conceito_{term.replace(' ', '_')}", "type": "artigo_conceito", "weight": 1})
    for node_id, terms in aula_terms.items():
        for term in terms:
            if term in major:
                edges.append({"source": node_id, "target": f"conceito_{term.replace(' ', '_')}", "type": "aula_conceito", "weight": 2})

    # --- Arestas cronograma <-> aula ---
    for item in cronograma:
        aula_arquivo = item.get("aula_pdf", "")
        if aula_arquivo and aula_arquivo in aula_por_arquivo:
            edges.append({"source": f"crono_{item['id']}", "target": aula_por_arquivo[aula_arquivo], "type": "cronograma_aula", "weight": 3})

    # --- Arestas de sequência temporal ---
    crono_sorted = sorted(cronograma, key=lambda x: int(x["id"]))
    for i in range(len(crono_sorted) - 1):
        edges.append({"source": f"crono_{crono_sorted[i]['id']}", "target": f"crono_{crono_sorted[i + 1]['id']}", "type": "sequencia_temporal", "weight": 0.5})

    # --- Arestas artigo <-> artigo (similaridade) ---
    art_ids = list(artigo_terms.keys())
    for i in range(len(art_ids)):
        for j in range(i + 1, len(art_ids)):
            sim = _jaccard(artigo_terms[art_ids[i]], artigo_terms[art_ids[j]])
            if sim > SIMILARITY_THRESHOLD:
                edges.append({"source": art_ids[i], "target": art_ids[j], "type": "artigo_artigo", "weight": round(sim, 3)})

    _layout(nodes)

    edges_by_type: dict[str, int] = defaultdict(int)
    for e in edges:
        edges_by_type[e["type"]] += 1

    metadata = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes_by_type": {
            "artigos": sum(1 for n in nodes if n["type"] == "artigo"),
            "aulas": sum(1 for n in nodes if n["type"] == "aula"),
            "cronograma": sum(1 for n in nodes if n["type"] == "cronograma"),
            "conceitos": sum(1 for n in nodes if n["type"] == "conceito"),
        },
        "edges_by_type": dict(edges_by_type),
    }

    return {"metadata": metadata, "nodes": nodes, "edges": edges}


def _layout(nodes: list[dict]) -> None:
    """Posicionamento 3D inicial por tipo (esfera/anel/hélice)."""
    random.seed(42)
    area_angles: dict[str, float] = {}
    area_idx = 0

    for node in nodes:
        kind = node["type"]
        if kind == "artigo":
            area = (node.get("areas") or "geral").split(";")[0].strip().lower()
            if area not in area_angles:
                area_angles[area] = area_idx * (2 * math.pi / 16)
                area_idx += 1
            theta = area_angles[area] + random.uniform(-0.4, 0.4)
            phi = random.uniform(0.3, 2.8)
            r = 160 + random.uniform(-30, 30)
            node["x"] = round(r * math.sin(phi) * math.cos(theta), 2)
            node["y"] = round(r * math.sin(phi) * math.sin(theta), 2)
            node["z"] = round(r * math.cos(phi), 2)
        elif kind == "aula":
            idx = int(node["id"].split("_")[1])
            angle = (idx / 8) * 2 * math.pi
            node["x"] = round(50 * math.cos(angle), 2)
            node["y"] = round(20 * math.sin(angle * 0.5), 2)
            node["z"] = round(50 * math.sin(angle), 2)
        elif kind == "cronograma":
            idx = int(node["id"].split("_")[1])
            angle = (idx / 39) * 6 * math.pi
            r = 60 + idx * 0.8
            node["x"] = round(r * math.cos(angle), 2)
            node["y"] = round(-80 + idx * 3, 2)
            node["z"] = round(r * math.sin(angle), 2)
        elif kind == "conceito":
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(0.4, 2.7)
            r = 90 + random.uniform(-20, 20)
            node["x"] = round(r * math.sin(phi) * math.cos(theta), 2)
            node["y"] = round(r * math.sin(phi) * math.sin(theta), 2)
            node["z"] = round(r * math.cos(phi), 2)
