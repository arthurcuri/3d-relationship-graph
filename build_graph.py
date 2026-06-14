#!/usr/bin/env python3
"""
Gera um grafo de relacionamentos entre os 3 datasets (artigos, aulas, cronograma)
e exporta como JSON para visualização 3D interativa.

Estratégia de relacionamento:
- Artigos <-> Aulas: por conceitos/temas em comum
- Aulas <-> Cronograma: por data e tema
- Artigos <-> Artigos: por áreas de pesquisa e métricas em comum
- Conceitos como nós intermediários conectando tudo
"""

import csv
import json
import re
import math
import random
from collections import defaultdict

# Paths
ARTIGOS_CSV = "/Users/ak/Downloads/teste/dataset_artigos.csv"
AULAS_CSV = "/Users/ak/Downloads/teste/dataset_aulas.csv"
CRONOGRAMA_CSV = "/Users/ak/Downloads/teste/dataset_cronograma.csv"
OUTPUT_JSON = "/Users/ak/Downloads/teste/visualizacao/graph_data.json"


def load_csv(path):
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def extract_terms(text):
    """Extrai termos normalizados de um campo separado por ;"""
    if not text:
        return set()
    terms = set()
    for t in text.split(';'):
        t = t.strip().lower()
        if t and len(t) > 2:
            terms.add(t)
    return terms


def compute_similarity(terms_a, terms_b):
    """Calcula similaridade de Jaccard entre dois conjuntos de termos."""
    if not terms_a or not terms_b:
        return 0
    intersection = terms_a & terms_b
    union = terms_a | terms_b
    return len(intersection) / len(union) if union else 0


def main():
    artigos = load_csv(ARTIGOS_CSV)
    aulas = load_csv(AULAS_CSV)
    cronograma = load_csv(CRONOGRAMA_CSV)
    
    nodes = []
    edges = []
    
    # --- NODOS ---
    
    # 1. Artigos como nós
    artigo_terms = {}  # id -> set of terms
    for art in artigos:
        art_id = f"artigo_{art['id']}"
        
        # Combina termos de múltiplos campos
        terms = set()
        terms |= extract_terms(art.get('areas_pesquisa', ''))
        terms |= extract_terms(art.get('metricas_mencionadas', ''))
        terms |= extract_terms(art.get('metodologia', ''))
        terms |= extract_terms(art.get('padroes_normas', ''))
        terms |= extract_terms(art.get('keywords', ''))
        artigo_terms[art_id] = terms
        
        nodes.append({
            "id": art_id,
            "type": "artigo",
            "label": art.get('titulo', art.get('arquivo', '')),
            "titulo": art.get('titulo', ''),
            "autores": art.get('autores', ''),
            "ano": art.get('ano', ''),
            "abstract": art.get('abstract', ''),
            "keywords": art.get('keywords', ''),
            "doi": art.get('doi', ''),
            "veiculo": art.get('veiculo_publicacao', ''),
            "num_paginas": art.get('num_paginas', ''),
            "metodologia": art.get('metodologia', ''),
            "areas": art.get('areas_pesquisa', ''),
            "metricas": art.get('metricas_mencionadas', ''),
            "metodos_estatisticos": art.get('metodos_estatisticos', ''),
            "ferramentas": art.get('ferramentas_tecnologias', ''),
            "padroes": art.get('padroes_normas', ''),
            "dominio": art.get('contexto_dominio', ''),
            "idioma": art.get('idioma', ''),
            "size": max(5, int(art.get('num_paginas', '10') or '10') / 3),
        })
    
    # 2. Aulas como nós
    aula_terms = {}
    for aula in aulas:
        aula_id = f"aula_{aula['id']}"
        
        terms = extract_terms(aula.get('conceitos_abordados', ''))
        terms |= extract_terms(aula.get('topicos_principais', ''))
        aula_terms[aula_id] = terms
        
        nodes.append({
            "id": aula_id,
            "type": "aula",
            "label": aula.get('titulo_aula', ''),
            "subtitulo": aula.get('subtitulo', ''),
            "professor": aula.get('professor', ''),
            "num_slides": aula.get('num_slides', ''),
            "topicos": aula.get('topicos_principais', ''),
            "titulos_slides": aula.get('titulos_slides', ''),
            "conceitos": aula.get('conceitos_abordados', ''),
            "resumo": aula.get('resumo_conteudo', ''),
            "size": 12,
        })
    
    # 3. Cronograma como nós (agrupados por módulo)
    for item in cronograma:
        crono_id = f"crono_{item['id']}"
        nodes.append({
            "id": crono_id,
            "type": "cronograma",
            "label": f"{item.get('data', '')} - {item.get('atividade', '')}",
            "data": item.get('data', ''),
            "atividade": item.get('atividade', ''),
            "tipo": item.get('tipo_atividade', ''),
            "modulo": item.get('modulo_tematico', ''),
            "aula_relacionada": item.get('aula_pdf_relacionada', ''),
            "size": 4,
        })
    
    # 4. Conceitos/Temas como nós intermediários (clusters)
    all_concepts = defaultdict(int)
    for terms in artigo_terms.values():
        for t in terms:
            all_concepts[t] += 1
    for terms in aula_terms.values():
        for t in terms:
            all_concepts[t] += 1
    
    # Filtra conceitos que aparecem em pelo menos 2 nós
    major_concepts = {k: v for k, v in all_concepts.items() if v >= 3}
    
    for concept, count in major_concepts.items():
        concept_id = f"conceito_{concept.replace(' ', '_')}"
        nodes.append({
            "id": concept_id,
            "type": "conceito",
            "label": concept.title(),
            "frequencia": count,
            "size": min(15, 3 + count),
        })
    
    # --- ARESTAS ---
    
    # Artigo <-> Conceito
    for art_id, terms in artigo_terms.items():
        for term in terms:
            if term in major_concepts:
                concept_id = f"conceito_{term.replace(' ', '_')}"
                edges.append({
                    "source": art_id,
                    "target": concept_id,
                    "type": "artigo_conceito",
                    "weight": 1,
                })
    
    # Aula <-> Conceito
    for aula_id, terms in aula_terms.items():
        for term in terms:
            if term in major_concepts:
                concept_id = f"conceito_{term.replace(' ', '_')}"
                edges.append({
                    "source": aula_id,
                    "target": concept_id,
                    "type": "aula_conceito",
                    "weight": 2,
                })
    
    # Cronograma <-> Aula (pela relação direta)
    for item in cronograma:
        crono_id = f"crono_{item['id']}"
        if item.get('aula_pdf_relacionada'):
            # Encontra a aula correspondente
            for aula in aulas:
                if aula.get('titulo_aula') == item['aula_pdf_relacionada']:
                    aula_id = f"aula_{aula['id']}"
                    edges.append({
                        "source": crono_id,
                        "target": aula_id,
                        "type": "cronograma_aula",
                        "weight": 3,
                    })
                    break
    
    # Cronograma -> Cronograma (sequência temporal)
    crono_sorted = sorted(cronograma, key=lambda x: x['id'])
    for i in range(len(crono_sorted) - 1):
        edges.append({
            "source": f"crono_{crono_sorted[i]['id']}",
            "target": f"crono_{crono_sorted[i+1]['id']}",
            "type": "sequencia_temporal",
            "weight": 0.5,
        })
    
    # Artigo <-> Artigo (alta similaridade temática)
    art_ids = list(artigo_terms.keys())
    for i in range(len(art_ids)):
        for j in range(i + 1, len(art_ids)):
            sim = compute_similarity(artigo_terms[art_ids[i]], artigo_terms[art_ids[j]])
            if sim > 0.25:  # threshold
                edges.append({
                    "source": art_ids[i],
                    "target": art_ids[j],
                    "type": "artigo_artigo",
                    "weight": round(sim, 3),
                })
    
    # --- POSICIONAMENTO INICIAL (layout esférico por tipo) ---
    # Distribui nós em regiões do espaço 3D por tipo, bem espaçados
    random.seed(42)
    
    # Agrupa artigos por área para clustering
    area_angles = {}
    area_idx = 0
    
    for node in nodes:
        if node["type"] == "artigo":
            # Distribui na esfera externa, agrupado por área principal
            area = node.get("areas", "geral").split(";")[0].strip().lower() if node.get("areas") else "geral"
            if area not in area_angles:
                area_angles[area] = area_idx * (2 * math.pi / 16)
                area_idx += 1
            
            base_angle = area_angles[area]
            theta = base_angle + random.uniform(-0.4, 0.4)
            phi = random.uniform(0.3, 2.8)
            r = 160 + random.uniform(-30, 30)
            node["x"] = round(r * math.sin(phi) * math.cos(theta), 2)
            node["y"] = round(r * math.sin(phi) * math.sin(theta), 2)
            node["z"] = round(r * math.cos(phi), 2)
            
        elif node["type"] == "aula":
            # Anel central proeminente
            idx = int(node["id"].split("_")[1])
            angle = (idx / 8) * 2 * math.pi
            r = 50
            node["x"] = round(r * math.cos(angle), 2)
            node["y"] = round(20 * math.sin(angle * 0.5), 2)
            node["z"] = round(r * math.sin(angle), 2)
            
        elif node["type"] == "cronograma":
            # Helix temporal abaixo
            idx = int(node["id"].split("_")[1])
            angle = (idx / 39) * 6 * math.pi
            r = 60 + idx * 0.8
            node["x"] = round(r * math.cos(angle), 2)
            node["y"] = round(-80 + idx * 3, 2)
            node["z"] = round(r * math.sin(angle), 2)
            
        elif node["type"] == "conceito":
            # Nuvem intermediária entre artigos e aulas
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(0.4, 2.7)
            r = 90 + random.uniform(-20, 20)
            node["x"] = round(r * math.sin(phi) * math.cos(theta), 2)
            node["y"] = round(r * math.sin(phi) * math.sin(theta), 2)
            node["z"] = round(r * math.cos(phi), 2)
    
    # --- METADADOS ---
    metadata = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes_by_type": {
            "artigos": sum(1 for n in nodes if n["type"] == "artigo"),
            "aulas": sum(1 for n in nodes if n["type"] == "aula"),
            "cronograma": sum(1 for n in nodes if n["type"] == "cronograma"),
            "conceitos": sum(1 for n in nodes if n["type"] == "conceito"),
        },
        "edges_by_type": {},
    }
    
    edge_types = defaultdict(int)
    for e in edges:
        edge_types[e["type"]] += 1
    metadata["edges_by_type"] = dict(edge_types)
    
    output = {
        "metadata": metadata,
        "nodes": nodes,
        "edges": edges,
    }
    
    # Cria diretório e salva
    import os
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Grafo gerado: {OUTPUT_JSON}")
    print(f"  Nós: {len(nodes)}")
    print(f"  Arestas: {len(edges)}")
    print(f"  Nós por tipo: {metadata['nodes_by_type']}")
    print(f"  Arestas por tipo: {metadata['edges_by_type']}")


if __name__ == "__main__":
    main()
