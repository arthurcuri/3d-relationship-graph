#!/usr/bin/env python3
"""
Script para extrair dados dos PDFs de aulas e do cronograma,
gerando um dataset enriquecido da disciplina.
"""

import os
import re
import csv
import fitz  # PyMuPDF

AULAS_DIR = "/Users/ak/Downloads/teste/aulas"
OUTPUT_CSV = "/Users/ak/Downloads/teste/dataset_aulas.csv"


def clean_text(text):
    """Remove múltiplos espaços e quebras de linha extras."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_topics_from_text(text):
    """Extrai tópicos/bullet points da aula."""
    topics = []
    lines = text.split('\n')
    
    # Primeiro tenta extrair do Sumário (Table of Contents)
    in_sumario = False
    sumario_topics = []
    for line in lines:
        line = line.strip()
        if re.match(r'^Sum[áa´]rio$', line) or re.match(r'^Conte[uú]do$', line):
            in_sumario = True
            continue
        if in_sumario:
            # Fim do sumário quando encontra rodapé do slide
            if re.match(r'^Prof\.|^\d+\s*/\s*\d+', line):
                in_sumario = False
                continue
            # Itens numerados do sumário
            if re.match(r'^\d+\s+[A-ZÀ-Ú]', line):
                topic = re.sub(r'^\d+\s+', '', line).strip()
                if topic and topic not in sumario_topics:
                    sumario_topics.append(topic)
            # Sub-itens do sumário
            elif len(line) > 3 and line[0].isupper() and len(line) < 150:
                if line not in sumario_topics and not re.match(r'^(Prof|Medi|Figura)', line):
                    sumario_topics.append(line)
    
    if sumario_topics:
        return sumario_topics[:30]
    
    # Fallback: linhas que parecem tópicos
    for line in lines:
        line = line.strip()
        if re.match(r'^[\•\-\▪\◦\➢\►\●\○]\s*', line):
            topic = re.sub(r'^[\•\-\▪\◦\➢\►\●\○]\s*', '', line).strip()
            if 5 < len(topic) < 200:
                topics.append(topic)
        elif re.match(r'^\d+[\.\)]\s+[A-ZÀ-Ú]', line):
            topic = re.sub(r'^\d+[\.\)]\s+', '', line).strip()
            if 5 < len(topic) < 200 and topic not in topics:
                topics.append(topic)
    
    return topics[:25]


def extract_concepts(text):
    """Extrai conceitos e definições mencionados."""
    concepts = []
    text_lower = text.lower()
    
    concept_patterns = {
        "Métricas de Software": r'métrica[s]?\s+de\s+software|software\s+metric',
        "GQM (Goal-Question-Metric)": r'\bgqm\b|goal[\-\s]question[\-\s]metric',
        "Medição de Software": r'medição\s+de\s+software|software\s+measurement',
        "Experimentação": r'experimentação|experiment(?:ation|s?\b)',
        "Variáveis Dependentes/Independentes": r'variáve[il]\s+(?:dependente|independente)|dependent\s+variable|independent\s+variable',
        "Hipótese Nula/Alternativa": r'hipótese\s+(?:nula|alternativa)|null\s+hypothesis|h[01]',
        "Teste de Hipótese": r'teste\s+de\s+hipótese|hypothesis\s+test',
        "Distribuição Normal": r'distribuição\s+normal|normal\s+distribution|gaussiana',
        "Complexidade Ciclomática": r'complexidade\s+ciclomática|cyclomatic\s+complexity',
        "LOC/SLOC": r'\b(?:loc|sloc)\b|lines?\s+of\s+code|linhas\s+de\s+código',
        "Pontos de Função": r'pontos?\s+de\s+função|function\s+point',
        "CMMI": r'\bcmmi\b',
        "ISO/IEC 25010": r'iso[\s/]*iec\s*25010|square',
        "ISO/IEC 9126": r'iso[\s/]*iec\s*9126',
        "ISO/IEC 15939": r'iso[\s/]*iec\s*15939',
        "Validade Interna": r'validade\s+interna|internal\s+validity',
        "Validade Externa": r'validade\s+externa|external\s+validity',
        "Revisão Sistemática": r'revisão\s+sistemática|systematic\s+(?:literature\s+)?review',
        "Estudo de Caso": r'estudo\s+de\s+caso|case\s+study',
        "Survey": r'\bsurvey\b|questionário',
        "Regressão": r'regressão|regression',
        "Correlação": r'correlação|correlation',
        "Desvio Padrão": r'desvio\s+padrão|standard\s+deviation',
        "Média/Mediana": r'\bmédia\b.*\bmediana\b|\bmean\b.*\bmedian\b',
        "Acoplamento": r'acoplamento|\bcoupling\b|\bcbo\b',
        "Coesão": r'coesão|\bcohesion\b|\blcom\b',
        "Dívida Técnica": r'dívida\s+técnica|technical\s+debt',
        "Code Churn": r'code\s+churn',
        "Halstead": r'halstead',
        "McCabe": r'mccabe',
        "COCOMO": r'\bcocomo\b',
        "Six Sigma": r'six\s+sigma|seis\s+sigma',
        "Story Points": r'story\s+point',
        "Velocity": r'\bvelocity\b|velocidade',
        "Lead Time": r'lead\s+time',
        "DORA Metrics": r'\bdora\b',
        "Produtividade": r'produtividade|productivity',
        "Confiabilidade": r'confiabilidade|reliability',
        "Manutenibilidade": r'manutenibilidade|maintainability',
        "Qualidade de Software": r'qualidade\s+de\s+software|software\s+quality',
        "Processo de Software": r'processo\s+de\s+software|software\s+process',
        "Amostragem": r'amostragem|sampling',
        "População": r'população|population',
        "Nível de Significância": r'nível\s+de\s+significância|significance\s+level|p[\-\s]?value|α\s*=',
        "Intervalo de Confiança": r'intervalo\s+de\s+confiança|confidence\s+interval',
    }
    
    for concept_name, pattern in concept_patterns.items():
        if re.search(pattern, text_lower):
            concepts.append(concept_name)
    
    return concepts


def extract_references_from_slides(text):
    """Extrai referências bibliográficas dos slides."""
    refs = []
    patterns = [
        r'(?:Referências?|References?|Bibliografia|REFERÊNCIAS)\s*[:\n](.+?)(?:\n\s*\n|\Z)',
        r'(?:Fonte|Source)[:\s]+(.+?)(?:\n|$)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            lines = match.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) > 20 and not line.startswith('http'):
                    refs.append(clean_text(line))
    return refs


def detect_learning_objectives(text):
    """Detecta objetivos de aprendizagem da aula."""
    objectives = []
    patterns = [
        r'(?:[Oo]bjetivo[s]?|[Oo]bjective[s]?|[Mm]eta[s]?)[:\s\n]+(.{20,500}?)(?:\n\s*\n)',
        r'(?:Ao final|Após|After).*?(?:aluno|estudante|student|you).*?(?:será capaz|poderá|will be able)(.{20,300})',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            obj = clean_text(match)
            if obj:
                objectives.append(obj)
    return objectives


def process_aula_pdf(filepath, filename):
    """Processa um PDF de aula e retorna dados extraídos."""
    result = {
        "arquivo": filename,
        "titulo_aula": "",
        "numero_aula": "",
        "subtitulo": "",
        "professor": "",
        "disciplina": "",
        "num_slides": 0,
        "topicos_principais": "",
        "titulos_slides": "",
        "conceitos_abordados": "",
        "referencias_citadas": "",
        "objetivos": "",
        "resumo_conteudo": "",
    }
    
    try:
        doc = fitz.open(filepath)
        result["num_slides"] = doc.page_count
        
        # Extrai texto completo
        full_text = ""
        slide_titles = []
        for page_idx, page in enumerate(doc):
            page_text = page.get_text()
            full_text += page_text + "\n"
            
            # Extrai título de cada slide (geralmente a primeira linha substantiva)
            lines = page_text.strip().split('\n')
            for line in lines[:3]:
                line = line.strip()
                if (len(line) > 3 and len(line) < 120 and 
                    not re.match(r'^(Prof\.|Figura|\d+\s*/\s*\d+|Sum|Medi)', line) and
                    line[0].isupper() and
                    line not in slide_titles):
                    slide_titles.append(line)
                    break
        
        # Extrai texto da primeira página para metadados
        first_page_text = doc[0].get_text() if doc.page_count > 0 else ""
        
        # Professor
        prof_match = re.search(r'Prof\.?\s*(.+?)(?:\n|$)', first_page_text)
        if prof_match:
            result["professor"] = clean_text(prof_match.group(1))
        
        # Disciplina
        disc_match = re.search(r'(?:Medi[çc]|Medição).*?(?:Eng|Software)', first_page_text)
        if disc_match:
            result["disciplina"] = "Medição e Experimentação em Engenharia de Software"
        
        # Número da aula
        aula_num = re.search(r'[Aa]ula\s*(\d+)', filename)
        if aula_num:
            result["numero_aula"] = aula_num.group(1)
        
        # Título da aula (do filename)
        titulo = os.path.splitext(filename)[0]
        titulo_clean = re.sub(r'^Aula\s*\d+\s*[\-–:]\s*', '', titulo).strip()
        if titulo_clean and titulo_clean != titulo:
            result["subtitulo"] = titulo_clean
        result["titulo_aula"] = titulo
        
        # Tópicos do sumário
        topics = extract_topics_from_text(full_text)
        if topics:
            result["topicos_principais"] = "; ".join(topics[:25])
        
        # Títulos dos slides (únicos, sem repetição)
        unique_titles = []
        seen = set()
        for t in slide_titles:
            t_norm = t.lower().strip()
            if t_norm not in seen and len(t) > 5:
                seen.add(t_norm)
                unique_titles.append(t)
        if unique_titles:
            result["titulos_slides"] = "; ".join(unique_titles[:20])
        
        # Conceitos
        concepts = extract_concepts(full_text)
        if concepts:
            result["conceitos_abordados"] = "; ".join(concepts)
        
        # Referências
        refs = extract_references_from_slides(full_text)
        if refs:
            result["referencias_citadas"] = "; ".join(refs[:10])
        
        # Objetivos
        objectives = detect_learning_objectives(full_text)
        if objectives:
            result["objetivos"] = "; ".join(objectives[:5])
        
        # Resumo do conteúdo (parágrafos substanciais dos slides)
        paragraphs = []
        lines = full_text.split('\n')
        current_para = ""
        for line in lines:
            line = line.strip()
            if len(line) > 50 and not re.match(r'^(Prof\.|Figura|\d+\s*/\s*\d+)', line):
                current_para += " " + line
            elif current_para:
                if len(current_para.strip()) > 80:
                    paragraphs.append(clean_text(current_para))
                current_para = ""
        
        if paragraphs:
            resumo = " | ".join(paragraphs[:10])
            if len(resumo) > 1000:
                resumo = resumo[:997] + "..."
            result["resumo_conteudo"] = resumo
        
        doc.close()
        
    except Exception as e:
        result["titulo_aula"] = os.path.splitext(filename)[0]
        result["resumo_conteudo"] = f"Erro: {str(e)}"
    
    return result


def main():
    """Função principal."""
    print("Iniciando extração de dados das aulas...")
    
    # Processa PDFs das aulas
    pdf_files = sorted([f for f in os.listdir(AULAS_DIR) if f.lower().endswith('.pdf')])
    print(f"Total de PDFs de aulas: {len(pdf_files)}")
    
    aulas_results = []
    for i, filename in enumerate(pdf_files, 1):
        filepath = os.path.join(AULAS_DIR, filename)
        print(f"  [{i}/{len(pdf_files)}] Processando: {filename[:60]}...")
        data = process_aula_pdf(filepath, filename)
        data["id"] = i
        aulas_results.append(data)
    
    # Salva dataset das aulas
    fieldnames_aulas = [
        "id", "arquivo", "numero_aula", "titulo_aula", "subtitulo",
        "professor", "disciplina", "num_slides", "topicos_principais",
        "titulos_slides", "conceitos_abordados", "referencias_citadas",
        "objetivos", "resumo_conteudo"
    ]
    
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_aulas, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(aulas_results)
    
    print(f"\nDataset de aulas salvo em: {OUTPUT_CSV}")
    
    # Agora processa o cronograma e cria dataset integrado
    cronograma_path = os.path.join(AULAS_DIR, "cronograma_atividades.csv")
    cronograma_data = []
    
    if os.path.exists(cronograma_path):
        with open(cronograma_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cronograma_data.append(row)
    
    # Dataset do cronograma enriquecido
    OUTPUT_CRONOGRAMA = "/Users/ak/Downloads/teste/dataset_cronograma.csv"
    
    cronograma_enriched = []
    for i, item in enumerate(cronograma_data, 1):
        dia = item.get("Dia", "").strip()
        atividade = item.get("Atividade", "").strip()
        
        if not dia and not atividade:
            continue
        
        # Classifica o tipo de atividade
        tipo = "Aula Expositiva"
        if re.search(r'[Aa]valiação|[Pp]rova', atividade):
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
        
        # Identifica módulo/bloco temático
        modulo = ""
        if re.search(r'[Nn]ivelamento|[Pp]resentação\s+do\s+curso', atividade):
            modulo = "Módulo 0 - Introdução"
        elif re.search(r'[Ee]scopo|[Cc]onceitos\s+[Bb]ásicos\s+de\s+[Mm]edição', atividade):
            modulo = "Módulo 1 - Fundamentos de Medição"
        elif re.search(r'[Ee]xperimentação|[Mm]étodos.*[Ee]mpíric|[Rr]evisão\s+[Ss]istemática|[Vv]ariáve', atividade):
            modulo = "Módulo 3 - Experimentação"
        elif re.search(r'[Mm]étrica|[Pp]ontos\s+de\s+[Ff]unção|[Mm]odelo|[Mm]edições|[Ee]ntidades', atividade):
            modulo = "Módulo 2 - Métricas e Modelos"
        elif re.search(r'[Ee]statística|[Dd]ata\s+[Aa]nalysis|[Dd]ecisão', atividade):
            modulo = "Módulo 4 - Análise Estatística"
        elif re.search(r'[Aa]valiação|[Pp]rova|[Rr]eavaliação|[Rr]evisão', atividade):
            modulo = "Avaliações"
        elif re.search(r'[Tt]rabalho|[Ee]nunciado|[Rr]elatório|[Dd]ocumentação|[Mm]odernas', atividade):
            modulo = "Módulo 5 - Prática e Encerramento"
        else:
            modulo = "Módulo 3 - Experimentação"
        
        # Mapeia para a aula correspondente (se houver)
        aula_relacionada = ""
        for aula in aulas_results:
            sub = aula.get("subtitulo", "").lower()
            if sub and atividade.lower():
                # Verifica se há sobreposição temática
                words_ativ = set(re.findall(r'\b\w{4,}\b', atividade.lower()))
                words_aula = set(re.findall(r'\b\w{4,}\b', sub))
                overlap = words_ativ & words_aula
                if len(overlap) >= 2:
                    aula_relacionada = aula["titulo_aula"]
                    break
        
        cronograma_enriched.append({
            "id": i,
            "data": dia,
            "atividade": atividade,
            "tipo_atividade": tipo,
            "modulo_tematico": modulo,
            "aula_pdf_relacionada": aula_relacionada,
        })
    
    fieldnames_crono = [
        "id", "data", "atividade", "tipo_atividade",
        "modulo_tematico", "aula_pdf_relacionada"
    ]
    
    with open(OUTPUT_CRONOGRAMA, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_crono, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(cronograma_enriched)
    
    print(f"Dataset do cronograma salvo em: {OUTPUT_CRONOGRAMA}")
    
    # Estatísticas
    print(f"\n--- Resumo ---")
    print(f"  Aulas processadas: {len(aulas_results)}")
    print(f"  Entradas no cronograma: {len(cronograma_enriched)}")
    print(f"  Com tópicos: {sum(1 for r in aulas_results if r['topicos_principais'])}/{len(aulas_results)}")
    print(f"  Com conceitos: {sum(1 for r in aulas_results if r['conceitos_abordados'])}/{len(aulas_results)}")
    print(f"  Com referências: {sum(1 for r in aulas_results if r['referencias_citadas'])}/{len(aulas_results)}")
    print(f"  Com resumo: {sum(1 for r in aulas_results if r['resumo_conteudo'])}/{len(aulas_results)}")
    
    # Tipos de atividade no cronograma
    tipos = {}
    for item in cronograma_enriched:
        t = item["tipo_atividade"]
        tipos[t] = tipos.get(t, 0) + 1
    print(f"\n--- Tipos de atividade no cronograma ---")
    for t, count in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}")
    
    # Módulos
    modulos = {}
    for item in cronograma_enriched:
        m = item["modulo_tematico"]
        modulos[m] = modulos.get(m, 0) + 1
    print(f"\n--- Distribuição por módulo ---")
    for m, count in sorted(modulos.items()):
        print(f"  {m}: {count} aulas")


if __name__ == "__main__":
    main()
