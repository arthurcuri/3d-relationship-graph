#!/usr/bin/env python3
"""
Reconstrói os datasets com melhor qualidade:
1. Corrige títulos de artigos
2. Relaciona TODAS as atividades do cronograma com aulas
3. Relaciona artigos com aulas baseado em temas
4. Gera um dataset unificado de relacionamentos
"""

import os
import re
import csv
import json
import fitz

ARTIGOS_DIR = "/Users/ak/Downloads/teste/Artigos"
AULAS_DIR = "/Users/ak/Downloads/teste/aulas"
OUTPUT_DIR = "/Users/ak/Downloads/teste"

# =============================================================================
# MAPEAMENTO MANUAL: Cronograma -> Aula (baseado no conteúdo)
# =============================================================================
# Cada atividade do cronograma é mapeada para a aula PDF mais relevante
CRONOGRAMA_AULA_MAP = {
    "Apresentação do curso": "Aula 1.pdf",
    "Nivelamento": "Aula 1.pdf",
    "Escopo de Medição": "Aula 2 - Escopo e Normas de Medição de Software.pdf",
    "Conceitos Básicos de Medição": "Aula 2 - Escopo e Normas de Medição de Software.pdf",
    "Conceitos Básicos de Experimentação": "Aula 3 - Introdução à Experimentação.pdf",
    "Etapas de Experimentação e Relatórios": "Aula 8 - Processo de Experimentos.pdf",
    "Entidades, Atributos e Objetivos de Medição": "Aula 4 - Entidades, Atributos e Objetivos de Medição.pdf",
    "Métricas de Produto": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Métricas de Processo": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Métricas de Projeto": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Modelos: Custo & Esforço, Produtividade Data Collection": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Modelos: confiabilidade, qualidade": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Pontos de Função": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
    "Revisão de Estatística": "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf",
    "Estatística para Experimentos": "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf",
    "Intrd. à Experimentação": "Aula 3 - Introdução à Experimentação.pdf",
    "Métodos e Estratégias Empíricas": "Aula 8 - Processo de Experimentos.pdf",
    "Variáveis em Experimentos": "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf",
    "Revisão Sistemática da Literatura": "Aula 8 - Processo de Experimentos.pdf",
    "Etapas: Escopo e Planejamento": "Aula 8 - Processo de Experimentos.pdf",
    "Etapas: Operação": "Aula 8 - Processo de Experimentos.pdf",
    "Etapas: Análise e Interpretação": "Aula 8 - Processo de Experimentos.pdf",
    "Data Analysis - Data collection and Data Validation": "Aula 8 - Processo de Experimentos.pdf",
    "Tomada de Decisão em Experimentos": "Aula 8 - Processo de Experimentos.pdf",
    "Relatórios e Documentação Técnica": "Aula 8 - Processo de Experimentos.pdf",
    "Métricas modernas": "Aula 5 - Medições de Produto, Processo e Recurso.pdf",
}

# =============================================================================
# MAPEAMENTO TEMÁTICO: Aula -> Temas para busca em artigos
# =============================================================================
AULA_TEMAS = {
    "Aula 1.pdf": [
        "medição de software", "experimentação", "engenharia de software",
        "decisões baseadas em dados", "qualidade de software",
    ],
    "Aula 2 - Escopo e Normas de Medição de Software.pdf": [
        "métricas de software", "normas", "iso", "cmmi", "gqm",
        "custo", "esforço", "confiabilidade", "complexidade",
        "maturidade", "medição", "escopo",
    ],
    "Aula 3 - Introdução à Experimentação.pdf": [
        "experimentação", "experimento controlado", "validade",
        "variáveis", "survey", "estudo de caso", "métodos empíricos",
    ],
    "Aula 4 - Entidades, Atributos e Objetivos de Medição.pdf": [
        "gqm", "entidades", "atributos", "objetivos de medição",
        "métricas", "escala de medição", "tipos de medida",
    ],
    "Aula 5 - Medições de Produto, Processo e Recurso.pdf": [
        "loc", "sloc", "complexidade ciclomática", "halstead",
        "pontos de função", "acoplamento", "coesão", "métricas de produto",
        "métricas de processo", "defeitos", "manutenibilidade",
        "produtividade", "custo", "esforço", "cocomo", "dora",
    ],
    "Aula 7 - Variáveis aleatórias, Distribuição de Probabilidade e Testes de Hipótese.pdf": [
        "estatística", "distribuição", "teste de hipótese", "variáveis",
        "normal", "probabilidade", "amostra", "significância",
        "desvio padrão", "média", "mediana",
    ],
    "Aula 8 - Processo de Experimentos.pdf": [
        "experimentação", "planejamento de experimentos", "escopo",
        "operação", "análise", "interpretação", "ameaças à validade",
        "revisão sistemática", "replicação", "relatório",
        "variáveis dependentes", "variáveis independentes",
    ],
}


def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def fix_title(titulo, text_first_page):
    """Corrige títulos ruins pegando da primeira página do PDF."""
    # Se o título parece ser nome de arquivo interno
    bad_patterns = [r'\.dvi$', r'\.tex$', r'^paper_', r'^manuscript', r'^\d+$', r'^untitled']
    is_bad = len(titulo) < 10 or any(re.search(p, titulo.lower()) for p in bad_patterns)
    
    if is_bad and text_first_page:
        # Tenta pegar o título real das primeiras linhas
        lines = text_first_page.strip().split('\n')
        candidate = ""
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 15 and len(line) < 200 and not re.match(r'^(Abstract|Keywords|Author|IEEE|ACM|\d)', line):
                candidate = line
                break
        if candidate:
            return candidate
    return titulo


def score_artigo_aula(artigo_text_lower, aula_temas):
    """Calcula score de relevância entre artigo e aula."""
    score = 0
    for tema in aula_temas:
        if tema in artigo_text_lower:
            score += 1
    return score


def main():
    print("=" * 60)
    print("RECONSTRUINDO DATASETS COM MELHOR QUALIDADE")
    print("=" * 60)
    
    # =========================================================================
    # 1. REPROCESSAR ARTIGOS (corrigir títulos, melhorar extração)
    # =========================================================================
    print("\n[1/4] Reprocessando artigos...")
    
    pdf_files = sorted([f for f in os.listdir(ARTIGOS_DIR) if f.lower().endswith('.pdf')])
    artigos = []
    artigos_text_cache = {}  # para scoring posterior
    
    for i, filename in enumerate(pdf_files, 1):
        filepath = os.path.join(ARTIGOS_DIR, filename)
        
        try:
            doc = fitz.open(filepath)
            
            # Texto das primeiras páginas
            text_first = ""
            for p in range(min(3, doc.page_count)):
                text_first += doc[p].get_text() + "\n"
            
            # Texto completo
            full_text = ""
            for p in range(doc.page_count):
                full_text += doc[p].get_text() + "\n"
            
            # Metadados do PDF
            meta = doc.metadata or {}
            
            # Título
            titulo = meta.get("title", "") or ""
            titulo = clean_text(titulo)
            titulo = fix_title(titulo, text_first)
            if not titulo or len(titulo) < 5:
                titulo = re.sub(r'_', ' ', os.path.splitext(filename)[0])
            
            # Autores
            autores = clean_text(meta.get("author", "")) or ""
            
            # Ano
            ano = ""
            years = re.findall(r'\b(20[0-2]\d)\b', text_first[:3000])
            if years:
                from collections import Counter
                ano = Counter(years).most_common(1)[0][0]
            
            # Abstract
            abstract = ""
            for pattern in [
                r'[Aa]bstract[\s\.\-:—\n]*(.{50,2000}?)(?:[Kk]ey\s*[Ww]ords|[Ii]ndex\s+[Tt]erms|[Ii]ntroduction|1[\.\s]+[Ii]ntro|I\.\s+INTRO)',
                r'ABSTRACT[\s\.\-:—\n]*(.{50,2000}?)(?:KEYWORDS|KEY\s*WORDS|INTRODUCTION|I\.\s+INTRO)',
                r'[Rr]esumo[\s\.\-:—\n]*(.{50,2000}?)(?:[Pp]alavras|[Ii]ntrodução|1[\.\s])',
                r'[Aa]bstract[\s\.\-:—\n]*(.{50,2000}?)(?:\n\s*\n\s*\n)',
            ]:
                m = re.search(pattern, text_first, re.DOTALL)
                if m:
                    abstract = clean_text(m.group(1))[:600]
                    break
            
            # Keywords
            keywords = ""
            for pattern in [
                r'[Kk]ey\s*[Ww]ords[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z]|ACM|IEEE|1[\.\s]+[Ii]ntro)',
                r'KEYWORDS[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z])',
                r'[Pp]alavras[\s\-]*[Cc]have[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n)',
                r'Index [Tt]erms[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n)',
            ]:
                m = re.search(pattern, text_first, re.DOTALL)
                if m:
                    keywords = clean_text(m.group(1))[:300]
                    break
            
            # DOI
            doi = ""
            dm = re.search(r'(10\.\d{4,}/[^\s,;\"\'<>]+)', text_first[:5000])
            if dm:
                doi = dm.group(1).rstrip('.')
            
            # Cache para scoring
            artigos_text_cache[filename] = full_text.lower()
            
            artigos.append({
                "id": i,
                "arquivo": filename,
                "titulo": titulo,
                "autores": autores,
                "ano": ano,
                "abstract": abstract,
                "keywords": keywords,
                "doi": doi,
                "num_paginas": doc.page_count,
                "caminho_pdf": f"Artigos/{filename}",
            })
            
            doc.close()
            
        except Exception as e:
            artigos.append({
                "id": i,
                "arquivo": filename,
                "titulo": re.sub(r'_', ' ', os.path.splitext(filename)[0]),
                "autores": "",
                "ano": "",
                "abstract": f"Erro: {e}",
                "keywords": "",
                "doi": "",
                "num_paginas": 0,
                "caminho_pdf": f"Artigos/{filename}",
            })
    
    print(f"  {len(artigos)} artigos processados")
    
    # =========================================================================
    # 2. DATASET DE AULAS (com caminho PDF)
    # =========================================================================
    print("\n[2/4] Processando aulas...")
    
    aula_files = sorted([f for f in os.listdir(AULAS_DIR) if f.lower().endswith('.pdf')])
    aulas = []
    
    for i, filename in enumerate(aula_files, 1):
        filepath = os.path.join(AULAS_DIR, filename)
        
        try:
            doc = fitz.open(filepath)
            
            full_text = ""
            for p in range(doc.page_count):
                full_text += doc[p].get_text() + "\n"
            
            # Número da aula
            num = re.search(r'[Aa]ula\s*(\d+)', filename)
            numero = num.group(1) if num else str(i)
            
            # Subtítulo
            subtitulo = re.sub(r'^Aula\s*\d+\s*[\-–:]\s*', '', os.path.splitext(filename)[0]).strip()
            if subtitulo == os.path.splitext(filename)[0]:
                subtitulo = "Introdução ao Curso"
            
            # Tópicos do sumário
            topicos = []
            lines = full_text.split('\n')
            in_sumario = False
            for line in lines:
                line = line.strip()
                if re.match(r'^Sum', line):
                    in_sumario = True
                    continue
                if in_sumario:
                    if re.match(r'^Prof\.|^\d+\s*/\s*\d+', line):
                        in_sumario = False
                        continue
                    if re.match(r'^\d+\s+[A-ZÀ-Ú]', line):
                        t = re.sub(r'^\d+\s+', '', line).strip()
                        if t and t not in topicos:
                            topicos.append(t)
                    elif len(line) > 3 and line[0].isupper() and len(line) < 120:
                        if not re.match(r'^(Prof|Medi|Figura)', line) and line not in topicos:
                            topicos.append(line)
            
            aulas.append({
                "id": i,
                "arquivo": filename,
                "numero_aula": numero,
                "titulo": f"Aula {numero} - {subtitulo}",
                "subtitulo": subtitulo,
                "professor": "Prof. Danilo de Quadros Maia Filho",
                "disciplina": "Medição e Experimentação em Engenharia de Software",
                "num_slides": doc.page_count,
                "topicos": "; ".join(topicos[:20]),
                "caminho_pdf": f"aulas/{filename}",
            })
            
            doc.close()
            
        except Exception as e:
            aulas.append({
                "id": i,
                "arquivo": filename,
                "numero_aula": str(i),
                "titulo": os.path.splitext(filename)[0],
                "subtitulo": "",
                "professor": "Prof. Danilo de Quadros Maia Filho",
                "disciplina": "Medição e Experimentação em Engenharia de Software",
                "num_slides": 0,
                "topicos": "",
                "caminho_pdf": f"aulas/{filename}",
            })
    
    print(f"  {len(aulas)} aulas processadas")
    
    # =========================================================================
    # 3. CRONOGRAMA ENRIQUECIDO (todas atividades -> aula)
    # =========================================================================
    print("\n[3/4] Reconstruindo cronograma com relacionamentos completos...")
    
    cronograma_path = os.path.join(AULAS_DIR, "cronograma_atividades.csv")
    cronograma = []
    
    with open(cronograma_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dia = row.get("Dia", "").strip()
            atividade = row.get("Atividade", "").strip()
            if not dia and not atividade:
                continue
            cronograma.append({"data": dia, "atividade": atividade})
    
    cronograma_enriched = []
    for i, item in enumerate(cronograma, 1):
        atividade = item["atividade"]
        
        # Tipo
        tipo = "Aula Expositiva"
        if re.search(r'[Aa]valiação\s*\d', atividade):
            tipo = "Avaliação"
        elif re.search(r'[Rr]evisão\s+de\s+[Pp]rova', atividade):
            tipo = "Revisão de Prova"
        elif re.search(r'[Rr]evisão\s+de\s+[Mm]atéria', atividade):
            tipo = "Revisão de Matéria"
        elif re.search(r'[Pp]resentação.*[Tt]rabalho', atividade):
            tipo = "Apresentação de Trabalho"
        elif re.search(r'[Nn]ivelamento', atividade):
            tipo = "Nivelamento"
        elif re.search(r'[Pp]resentação\s+do\s+curso', atividade):
            tipo = "Apresentação do Curso"
        elif re.search(r'[Ee]nunciado', atividade):
            tipo = "Orientação de Trabalho"
        elif re.search(r'[Rr]eavaliação', atividade):
            tipo = "Reavaliação"
        
        # Módulo
        modulo = ""
        if re.search(r'[Nn]ivelamento|[Pp]resentação\s+do\s+curso', atividade):
            modulo = "Módulo 0 - Introdução"
        elif re.search(r'[Ee]scopo|[Cc]onceitos\s+[Bb]ásicos\s+de\s+[Mm]edição', atividade):
            modulo = "Módulo 1 - Fundamentos de Medição"
        elif re.search(r'[Mm]étrica|[Pp]ontos\s+de\s+[Ff]unção|[Mm]odelo|[Mm]edições|[Ee]ntidades|[Mm]odernas', atividade):
            modulo = "Módulo 2 - Métricas e Modelos"
        elif re.search(r'[Ee]xperimentação|[Mm]étodos.*[Ee]mpíric|[Rr]evisão\s+[Ss]istemática|[Vv]ariáve|[Ee]tapas|[Oo]peração', atividade):
            modulo = "Módulo 3 - Experimentação"
        elif re.search(r'[Ee]statística|[Dd]ata\s+[Aa]nalysis|[Dd]ecisão', atividade):
            modulo = "Módulo 4 - Análise Estatística"
        elif re.search(r'[Aa]valiação|[Pp]rova|[Rr]eavaliação|[Rr]evisão\s+de', atividade):
            modulo = "Avaliações"
        elif re.search(r'[Tt]rabalho|[Ee]nunciado|[Rr]elatório|[Dd]ocumentação', atividade):
            modulo = "Módulo 5 - Prática e Encerramento"
        else:
            modulo = "Módulo 3 - Experimentação"
        
        # Aula PDF relacionada (usando mapeamento manual)
        aula_pdf = CRONOGRAMA_AULA_MAP.get(atividade, "")
        
        cronograma_enriched.append({
            "id": i,
            "data": item["data"],
            "atividade": atividade,
            "tipo_atividade": tipo,
            "modulo_tematico": modulo,
            "aula_pdf": aula_pdf,
            "caminho_pdf_aula": f"aulas/{aula_pdf}" if aula_pdf else "",
        })
    
    linked = sum(1 for c in cronograma_enriched if c["aula_pdf"])
    print(f"  {len(cronograma_enriched)} atividades, {linked} com aula PDF vinculada")
    
    # =========================================================================
    # 4. RELACIONAMENTOS: Artigos <-> Aulas
    # =========================================================================
    print("\n[4/4] Calculando relacionamentos artigos <-> aulas...")
    
    relacoes = []  # (artigo_id, aula_arquivo, score)
    
    for art in artigos:
        art_text = artigos_text_cache.get(art["arquivo"], "")
        if not art_text:
            continue
        
        for aula_file, temas in AULA_TEMAS.items():
            score = score_artigo_aula(art_text, temas)
            # Só inclui se pelo menos 3 temas batem
            if score >= 3:
                relacoes.append({
                    "artigo_id": art["id"],
                    "artigo_titulo": art["titulo"],
                    "artigo_arquivo": art["arquivo"],
                    "aula_arquivo": aula_file,
                    "score_relevancia": score,
                    "total_temas_aula": len(temas),
                    "percentual_match": round(score / len(temas) * 100, 1),
                })
    
    # Ordena por score
    relacoes.sort(key=lambda x: (-x["score_relevancia"], x["artigo_id"]))
    print(f"  {len(relacoes)} relações artigo-aula encontradas (score >= 3)")
    
    # =========================================================================
    # SALVAR TUDO
    # =========================================================================
    print("\n" + "=" * 60)
    print("SALVANDO DATASETS...")
    
    # Artigos
    art_fields = ["id", "arquivo", "titulo", "autores", "ano", "abstract", "keywords", "doi", "num_paginas", "caminho_pdf"]
    with open(os.path.join(OUTPUT_DIR, "dataset_artigos.csv"), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=art_fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(artigos)
    print(f"  ✓ dataset_artigos.csv ({len(artigos)} registros)")
    
    # Aulas
    aula_fields = ["id", "arquivo", "numero_aula", "titulo", "subtitulo", "professor", "disciplina", "num_slides", "topicos", "caminho_pdf"]
    with open(os.path.join(OUTPUT_DIR, "dataset_aulas.csv"), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=aula_fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(aulas)
    print(f"  ✓ dataset_aulas.csv ({len(aulas)} registros)")
    
    # Cronograma
    crono_fields = ["id", "data", "atividade", "tipo_atividade", "modulo_tematico", "aula_pdf", "caminho_pdf_aula"]
    with open(os.path.join(OUTPUT_DIR, "dataset_cronograma.csv"), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=crono_fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(cronograma_enriched)
    print(f"  ✓ dataset_cronograma.csv ({len(cronograma_enriched)} registros)")
    
    # Relações
    rel_fields = ["artigo_id", "artigo_titulo", "artigo_arquivo", "aula_arquivo", "score_relevancia", "total_temas_aula", "percentual_match"]
    with open(os.path.join(OUTPUT_DIR, "dataset_relacoes_artigo_aula.csv"), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=rel_fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(relacoes)
    print(f"  ✓ dataset_relacoes_artigo_aula.csv ({len(relacoes)} registros)")
    
    # JSON unificado para visualização
    graph = {
        "artigos": artigos,
        "aulas": aulas,
        "cronograma": cronograma_enriched,
        "relacoes_artigo_aula": relacoes,
    }
    
    os.makedirs(os.path.join(OUTPUT_DIR, "visualizacao"), exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "visualizacao", "data.json"), 'w', encoding='utf-8') as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    print(f"  ✓ visualizacao/data.json (unificado)")
    
    print("\n" + "=" * 60)
    print("PRONTO!")
    print(f"  Artigos: {len(artigos)}")
    print(f"  Aulas: {len(aulas)}")
    print(f"  Cronograma: {len(cronograma_enriched)} ({linked} com PDF)")
    print(f"  Relações artigo-aula: {len(relacoes)}")
    
    # Stats das relações
    print("\n  Distribuição de artigos por aula:")
    from collections import Counter
    aula_count = Counter(r["aula_arquivo"] for r in relacoes)
    for aula, count in aula_count.most_common():
        print(f"    {aula[:50]:50s} → {count} artigos")


if __name__ == "__main__":
    main()
