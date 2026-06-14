#!/usr/bin/env python3
"""
Script para extrair metadados e informações dos PDFs e gerar um dataset enriquecido.
"""

import os
import re
import csv
import fitz  # PyMuPDF

ARTIGOS_DIR = "/Users/ak/Downloads/teste/Artigos"
OUTPUT_CSV = "/Users/ak/Downloads/teste/dataset_artigos_enriquecido.csv"


def clean_text(text):
    """Remove múltiplos espaços e quebras de linha extras."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_year(text, filename):
    """Tenta extrair o ano de publicação do texto ou metadados."""
    # Procura padrões de ano entre 2000-2026
    years = re.findall(r'\b(20[0-2]\d)\b', text[:3000])
    if years:
        # Retorna o ano mais frequente nos primeiros caracteres
        from collections import Counter
        count = Counter(years)
        return count.most_common(1)[0][0]
    return ""


def extract_authors(text):
    """Tenta extrair autores da primeira página do texto."""
    # Padrão comum: linhas após título e antes do abstract
    lines = text[:2000].split('\n')
    authors = []
    
    # Procura por padrões de nomes (Nome Sobrenome com possíveis números de afiliação)
    author_pattern = re.compile(
        r'^([A-Z][a-zà-ü]+(?:\s+[A-Z]\.?)*(?:\s+(?:de|da|do|dos|das|van|von|del|el))?\s+[A-Z][a-zà-ü]+(?:\s+[A-Z][a-zà-ü]+)*)'
    )
    
    return ""


def extract_abstract(text):
    """Extrai o abstract do artigo."""
    # Procura por "Abstract" seguido do texto
    patterns = [
        r'[Aa]bstract[\s\.\-:—\n]*(.{50,2000}?)(?:[Kk]ey\s*[Ww]ords|[Ii]ndex\s+[Tt]erms|[Ii]ntroduction|1[\.\s]+[Ii]ntro|I\.\s+INTRO)',
        r'ABSTRACT[\s\.\-:—\n]*(.{50,2000}?)(?:KEYWORDS|KEY\s*WORDS|INDEX\s+TERMS|INTRODUCTION|I\.\s+INTRO|1[\.\s])',
        r'[Rr]esumo[\s\.\-:—\n]*(.{50,2000}?)(?:[Pp]alavras|[Ii]ntrodução|1[\.\s])',
        r'[Aa]bstract[\s\.\-:—\n]*(.{50,2000}?)(?:\n\s*\n\s*\n)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            abstract = clean_text(match.group(1))
            # Limita a 600 chars para o CSV
            if len(abstract) > 600:
                abstract = abstract[:597] + "..."
            return abstract
    # Fallback: tenta pegar texto entre as primeiras linhas que parece abstract
    lines = text[:3000].split('\n')
    # Procura um parágrafo longo nas primeiras 40 linhas
    for i, line in enumerate(lines[:40]):
        if len(line.strip()) > 150:
            abstract = clean_text(line.strip())
            if len(abstract) > 600:
                abstract = abstract[:597] + "..."
            return abstract
    return ""


def extract_keywords(text):
    """Extrai palavras-chave do artigo."""
    patterns = [
        r'[Kk]ey\s*[Ww]ords[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z]|ACM|IEEE|1[\.\s]+[Ii]ntro)',
        r'KEYWORDS[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z]|ACM|IEEE)',
        r'[Pp]alavras[\s\-]*[Cc]have[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]|1[\.\s]+[Ii]ntro)',
        r'Index [Tt]erms[\s\.\-:—]*(.{10,500}?)(?:\n\s*\n|\d+[\.\s]+[A-Z])',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            kw = clean_text(match.group(1))
            # Remove pontuação final
            kw = re.sub(r'[\.\s]+$', '', kw)
            if len(kw) > 300:
                kw = kw[:300]
            return kw
    return ""


def extract_doi(text):
    """Extrai DOI do texto."""
    doi_pattern = r'(10\.\d{4,}/[^\s,;\"\'<>]+)'
    match = re.search(doi_pattern, text[:5000])
    if match:
        doi = match.group(1).rstrip('.')
        return doi
    return ""


def extract_venue(text):
    """Tenta extrair o veículo de publicação (conferência/periódico)."""
    venues_keywords = [
        r'(?:Published in|Appeared in|Proceedings of|In:)\s*(.{10,150}?)(?:\.|,|\n)',
        r'(IEEE\s+[A-Za-z\s]+(?:Conference|Transactions|Journal|Magazine|Software)[A-Za-z\s]*)',
        r'(ACM\s+[A-Za-z\s]+(?:Conference|Symposium|Journal)[A-Za-z\s]*)',
        r'(Information and Software Technology|Empirical Software Engineering|Journal of Systems and Software)',
        r'(ICSE|ESEC/FSE|ASE|MSR|ICSME|SANER|TSE|TOSEM|IST|JSS|EMSE)',
    ]
    for pattern in venues_keywords:
        match = re.search(pattern, text[:3000])
        if match:
            venue = clean_text(match.group(1))
            if len(venue) > 150:
                venue = venue[:150]
            return venue
    return ""


def detect_methodology(text):
    """Detecta a metodologia usada no artigo."""
    text_lower = text[:8000].lower()
    methods = []
    
    method_map = {
        "Revisão Sistemática": [r'systematic\s+(literature\s+)?review', r'revisão\s+sistemática'],
        "Mapeamento Sistemático": [r'systematic\s+mapping', r'mapeamento\s+sistemático'],
        "Experimento Controlado": [r'controlled\s+experiment', r'experimento\s+controlado', r'randomized\s+experiment'],
        "Estudo de Caso": [r'case\s+stud(y|ies)', r'estudo\s+de\s+caso'],
        "Survey/Questionário": [r'\bsurvey\b', r'questionnaire', r'questionário'],
        "Estudo Empírico": [r'empirical\s+stud(y|ies)', r'estudo\s+empírico'],
        "Meta-análise": [r'meta[\-\s]analy', r'meta[\-\s]análise'],
        "Revisão Multivocal": [r'multivocal\s+(literature\s+)?review'],
        "Proposta de Framework": [r'propos(e|ed|ing)\s+(a\s+)?framework', r'framework\s+for'],
        "Análise Estatística": [r'statistical\s+analy', r'análise\s+estatística'],
        "Machine Learning": [r'machine\s+learning', r'deep\s+learning', r'neural\s+network'],
        "Replicação": [r'replicat(ion|ed|ing)', r'replicação'],
        "GQM": [r'\bgqm\b', r'goal\s+question\s+metric'],
        "Mineração de Repositórios": [r'mining\s+(software\s+)?repositor', r'mineração'],
    }
    
    for method_name, patterns in method_map.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                methods.append(method_name)
                break
    
    return "; ".join(methods) if methods else ""


def detect_metrics_mentioned(text):
    """Detecta métricas de software mencionadas no artigo."""
    text_lower = text[:10000].lower()
    metrics = []
    
    metric_map = {
        "LOC/SLOC": [r'\b(loc|sloc|lines\s+of\s+code)\b'],
        "Complexidade Ciclomática": [r'cyclomatic\s+complexity', r'complexidade\s+ciclomática', r'\bmcc\b'],
        "Complexidade Cognitiva": [r'cognitive\s+complexity', r'complexidade\s+cognitiva'],
        "Function Points": [r'function\s+point', r'pontos\s+de\s+função'],
        "Code Churn": [r'code\s+churn'],
        "Code Coverage": [r'code\s+coverage', r'cobertura\s+de\s+código'],
        "Coupling/Acoplamento": [r'\bcoupling\b', r'acoplamento', r'\bcbo\b'],
        "Cohesion/Coesão": [r'\bcohesion\b', r'coesão', r'\blcom\b'],
        "Halstead": [r'halstead'],
        "Story Points": [r'story\s+point'],
        "Velocity": [r'\bvelocity\b', r'velocidade'],
        "Lead Time": [r'lead\s+time'],
        "DORA Metrics": [r'dora\s+metric', r'deployment\s+frequency', r'change\s+failure\s+rate'],
        "Technical Debt": [r'technical\s+debt', r'dívida\s+técnica'],
        "Defect Density": [r'defect\s+density', r'densidade\s+de\s+defeito'],
        "MTTR": [r'\bmttr\b', r'mean\s+time\s+to\s+r'],
        "WMC": [r'\bwmc\b', r'weighted\s+methods?\s+per\s+class'],
        "DIT": [r'\bdit\b', r'depth\s+of\s+inheritance'],
        "NOC": [r'\bnoc\b', r'number\s+of\s+children'],
        "RFC": [r'\brfc\b', r'response\s+for\s+a?\s*class'],
        "CK Metrics": [r'\bck\s+metric', r'chidamber\s+and?\s+kemerer'],
    }
    
    for metric_name, patterns in metric_map.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                metrics.append(metric_name)
                break
    
    return "; ".join(metrics) if metrics else ""


def detect_tools_technologies(text):
    """Detecta ferramentas e tecnologias mencionadas."""
    text_content = text
    tools = []
    
    tool_patterns = {
        "SonarQube": [r'[Ss]onar[Qq]ube', r'[Ss]onar[Ss]ource'],
        "GitHub": [r'[Gg]it[Hh]ub'],
        "GitLab": [r'[Gg]it[Ll]ab'],
        "JIRA": [r'\bJIRA\b', r'\bJira\b'],
        "Jenkins": [r'[Jj]enkins'],
        "Python": [r'\bPython\b'],
        "R (Estatístico)": [r'\bR\s+(?:software|language|statistical|package|version|environment)\b', r'\bcran\b'],
        "Java": [r'\bJava\b'],
        "SPSS": [r'\bSPSS\b'],
        "Weka": [r'\bWeka\b'],
        "scikit-learn": [r'scikit[\-\s]learn', r'sklearn'],
        "Maven": [r'\bMaven\b'],
        "Docker": [r'\bDocker\b'],
        "Kubernetes": [r'\bKubernetes\b'],
        "Eclipse": [r'\bEclipse\b'],
        "Visual Studio": [r'Visual\s+Studio'],
        "JUnit": [r'\bJUnit\b'],
        "Understand (SciTools)": [r'\bUnderstand\b'],
        "PMD": [r'\bPMD\b'],
        "FindBugs/SpotBugs": [r'\bFindBugs\b', r'\bSpotBugs\b'],
        "Checkstyle": [r'\bCheckstyle\b'],
        "ChatGPT/GPT": [r'\bChatGPT\b', r'\bGPT[\-\s]?[34]\b', r'\bOpenAI\b'],
        "GitHub Copilot": [r'[Cc]opilot'],
        "CodeLlama/LLaMA": [r'\bLLaMA\b', r'\bCode\s*Llama\b'],
        "Selenium": [r'\bSelenium\b'],
        "COSMIC": [r'\bCOSMIC\b'],
        "IFPUG": [r'\bIFPUG\b'],
        "Prometheus": [r'\bPrometheus\b'],
        "Grafana": [r'\bGrafana\b'],
        "Snowball/Scopus/IEEE Xplore": [r'\bScopus\b', r'IEEE\s+Xplore', r'\bSnowball'],
        "Google Scholar": [r'Google\s+Scholar'],
    }
    
    for tool_name, patterns in tool_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text_content):
                tools.append(tool_name)
                break
    
    return "; ".join(tools) if tools else ""


def detect_statistical_methods(text):
    """Detecta métodos estatísticos utilizados."""
    text_lower = text.lower()
    methods = []
    
    stat_map = {
        "Teste t": [r'\bt[\-\s]test\b', r'student[\'\s]s?\s*t'],
        "Mann-Whitney": [r'mann[\-\s]whitney'],
        "Wilcoxon": [r'wilcoxon'],
        "Chi-quadrado": [r'chi[\-\s]square', r'qui[\-\s]quadrado'],
        "ANOVA": [r'\banova\b'],
        "Kruskal-Wallis": [r'kruskal[\-\s]wallis'],
        "Correlação de Pearson": [r'pearson', r'correlação\s+de\s+pearson'],
        "Correlação de Spearman": [r'spearman'],
        "Regressão Linear": [r'linear\s+regression', r'regressão\s+linear'],
        "Regressão Logística": [r'logistic\s+regression', r'regressão\s+logística'],
        "Effect Size": [r'effect\s+size', r'cohen[\'\s]s?\s*d\b', r'cliff[\'\s]s?\s*delta'],
        "Shapiro-Wilk": [r'shapiro[\-\s]wilk'],
        "Kolmogorov-Smirnov": [r'kolmogorov[\-\s]smirnov'],
        "Bootstrap": [r'\bbootstrap\b'],
        "Fisher's Exact": [r'fisher[\'\s]s?\s*exact'],
        "Bayesiana": [r'bayesian', r'bayes'],
        "Descritiva": [r'descriptive\s+statistic', r'estatística\s+descritiva', r'mean\s+and\s+standard\s+deviation'],
        "Box Plot": [r'box[\-\s]?plot', r'boxplot'],
        "Teste de Normalidade": [r'normality\s+test', r'teste\s+de\s+normalidade'],
        "Random Forest": [r'random\s+forest'],
        "SVM": [r'\bsvm\b', r'support\s+vector'],
        "K-fold/Cross-validation": [r'cross[\-\s]validat', r'k[\-\s]fold'],
        "ROC/AUC": [r'\broc\b', r'\bauc\b', r'receiver\s+operating'],
        "Precisão/Recall/F1": [r'precision.*recall', r'f[\-\s]?1[\-\s]?(?:score|measure)', r'f[\-\s]measure'],
    }
    
    for method_name, patterns in stat_map.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                methods.append(method_name)
                break
    
    return "; ".join(methods) if methods else ""


def estimate_num_pages(doc):
    """Retorna o número de páginas."""
    return doc.page_count


def extract_references_count(text):
    """Estima o número de referências."""
    # Procura pela seção de referências e conta entradas
    ref_section = re.search(r'(?:REFERENCES|References|Referências|REFERÊNCIAS|BIBLIOGRAPHY)\s*\n(.+)', text, re.DOTALL)
    if ref_section:
        ref_text = ref_section.group(1)
        # Conta entradas numeradas [1], [2], etc.
        numbered = re.findall(r'\[\d+\]', ref_text)
        if numbered:
            # Pega o maior número
            nums = [int(re.search(r'\d+', n).group()) for n in numbered]
            return max(nums) if nums else 0
        # Conta linhas que começam com número ou autor
        lines = [l for l in ref_text.split('\n') if l.strip() and len(l.strip()) > 20]
        if lines:
            return min(len(lines), 200)
    return 0


def extract_sample_size(text):
    """Tenta extrair informação sobre tamanho da amostra."""
    text_lower = text.lower()
    patterns = [
        r'(\d+)\s+(?:participants?|subjects?|developers?|students?|professionals?|respondents?|projects?)',
        r'sample\s+(?:size|of)\s+(?:is\s+)?(\d+)',
        r'(\d+)\s+(?:open[\-\s]source|oss)\s+projects?',
        r'(\d+)\s+repositories',
        r'we\s+(?:selected|analyzed|collected|studied|surveyed)\s+(\d+)',
        r'dataset\s+(?:of|with|contains?|including)\s+(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            num = match.group(1) if match.group(1) else match.group(2) if match.lastindex > 1 else ""
            if num:
                try:
                    n = int(num)
                    if 2 <= n <= 1000000:
                        return str(n)
                except:
                    pass
    return ""


def extract_context_domain(text):
    """Detecta o contexto/domínio de aplicação."""
    text_lower = text[:8000].lower()
    domains = []
    
    domain_map = {
        "Open Source": [r'open[\-\s]source', r'\boss\b', r'github\s+(?:project|repositor)'],
        "Indústria": [r'industr(?:y|ial)', r'company', r'organization', r'empresa'],
        "Acadêmico": [r'academ(?:ic|y)', r'universit(?:y|ies)', r'student', r'classroom'],
        "Web/Mobile": [r'web\s+(?:app|system|service)', r'mobile\s+app'],
        "Sistemas Embarcados": [r'embedded\s+system'],
        "Microsserviços": [r'microservice'],
        "Sistemas Legados": [r'legacy\s+system'],
        "Saúde/Healthcare": [r'health(?:care)?', r'medical', r'saúde'],
        "Financeiro": [r'financ(?:ial|e)', r'banking'],
        "Educação": [r'educat(?:ion|ional)', r'educação', r'e[\-\s]learning'],
    }
    
    for domain_name, patterns in domain_map.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                domains.append(domain_name)
                break
    
    return "; ".join(domains) if domains else ""


def extract_quality_standards(text):
    """Detecta padrões e normas de qualidade mencionados."""
    standards = []
    
    standards_map = {
        "ISO/IEC 25010 (SQuaRE)": [r'ISO[\s/]*IEC\s*25010', r'SQuaRE'],
        "ISO/IEC 9126": [r'ISO[\s/]*IEC\s*9126'],
        "ISO/IEC 15939": [r'ISO[\s/]*IEC\s*15939', r'IEEE\s*15939'],
        "CMMI": [r'\bCMMI\b'],
        "Six Sigma": [r'[Ss]ix\s+[Ss]igma', r'[Ss]eis\s+[Ss]igma'],
        "GQM": [r'\bGQM\b', r'Goal[\-\s]Question[\-\s]Metric'],
        "ISO 9001": [r'ISO\s*9001'],
        "SWEBOK": [r'\bSWEBOK\b'],
        "IEEE 730": [r'IEEE\s*730'],
        "McCall Model": [r'McCall'],
        "Boehm Model": [r'Boehm\b'],
        "DORA": [r'\bDORA\b'],
        "SPACE Framework": [r'\bSPACE\b.*framework', r'SPACE\s+metric'],
    }
    
    for std_name, patterns in standards_map.items():
        for pattern in patterns:
            if re.search(pattern, text):
                standards.append(std_name)
                break
    
    return "; ".join(standards) if standards else ""


def classify_area_detailed(text, filename):
    """Classificação mais detalhada da área de pesquisa."""
    text_lower = (text[:5000] + filename).lower()
    areas = []
    
    area_map = {
        "Métricas de Software": [r'software\s+metric', r'code\s+metric', r'métrica'],
        "Qualidade de Software": [r'software\s+quality', r'qualidade\s+de\s+software', r'quality\s+model'],
        "Teste de Software": [r'software\s+test', r'test[\-\s]driven', r'teste\s+de\s+software'],
        "Manutenção de Software": [r'software\s+maintenance', r'maintainability', r'manutenção'],
        "Engenharia de Software Empírica": [r'empirical\s+software', r'engenharia.*empírica'],
        "Experimentação": [r'experiment(?:ation|s?\s+in)', r'experimentação', r'controlled\s+experiment'],
        "Métodos Ágeis": [r'agile', r'scrum', r'kanban', r'ágil'],
        "DevOps/CI-CD": [r'devops', r'continuous\s+(?:integration|delivery|deployment)'],
        "Gerenciamento de Projetos": [r'project\s+management', r'gerenciamento\s+de\s+projeto', r'scope\s+change', r'effort\s+estimation'],
        "Inteligência Artificial/ML": [r'machine\s+learning', r'artificial\s+intelligence', r'deep\s+learning', r'llm', r'ai[\-\s]generated'],
        "Segurança de Software": [r'security', r'vulnerability', r'segurança'],
        "Processo de Software": [r'software\s+process', r'cmmi', r'processo\s+de\s+software'],
        "Revisão de Código": [r'code\s+review', r'pull\s+request'],
        "Predição de Defeitos": [r'defect\s+predict', r'fault[\-\s]prone', r'bug\s+predict'],
        "Produtividade": [r'productivity', r'produtividade', r'developer\s+performance'],
        "Dívida Técnica": [r'technical\s+debt', r'dívida\s+técnica'],
    }
    
    for area_name, patterns in area_map.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                areas.append(area_name)
                break
    
    return "; ".join(areas) if areas else "Engenharia de Software (Geral)"


def process_pdf(filepath, filename):
    """Processa um PDF e retorna um dicionário com todos os dados extraídos."""
    result = {
        "arquivo": filename,
        "titulo": "",
        "autores": "",
        "ano": "",
        "abstract": "",
        "keywords": "",
        "doi": "",
        "veiculo_publicacao": "",
        "num_paginas": 0,
        "num_referencias": 0,
        "tamanho_amostra": "",
        "metodologia": "",
        "areas_pesquisa": "",
        "metricas_mencionadas": "",
        "metodos_estatisticos": "",
        "ferramentas_tecnologias": "",
        "padroes_normas": "",
        "contexto_dominio": "",
        "idioma": "",
    }
    
    try:
        doc = fitz.open(filepath)
        result["num_paginas"] = estimate_num_pages(doc)
        
        # Extrai texto das primeiras 5 páginas para metadados
        text_first = ""
        for i in range(min(5, doc.page_count)):
            page = doc[i]
            text_first += page.get_text() + "\n"
        
        # Extrai texto completo para análise mais profunda
        full_text = ""
        for i in range(doc.page_count):
            page = doc[i]
            full_text += page.get_text() + "\n"
        
        # Metadados do PDF
        meta = doc.metadata
        if meta:
            if meta.get("title"):
                result["titulo"] = clean_text(meta["title"])
            if meta.get("author"):
                result["autores"] = clean_text(meta["author"])
        
        # Se título não veio dos metadados, usa o nome do arquivo
        if not result["titulo"] or len(result["titulo"]) < 5:
            titulo = os.path.splitext(filename)[0]
            titulo = re.sub(r'_', ' ', titulo)
            result["titulo"] = titulo
        
        # Extrai informações do texto
        result["ano"] = extract_year(text_first, filename)
        
        abstract = extract_abstract(text_first)
        if abstract:
            result["abstract"] = abstract
        
        keywords = extract_keywords(text_first)
        if keywords:
            result["keywords"] = keywords
        
        result["doi"] = extract_doi(text_first)
        result["veiculo_publicacao"] = extract_venue(text_first)
        result["num_referencias"] = extract_references_count(full_text)
        result["tamanho_amostra"] = extract_sample_size(full_text)
        result["metodologia"] = detect_methodology(full_text)
        result["areas_pesquisa"] = classify_area_detailed(full_text, filename)
        result["metricas_mencionadas"] = detect_metrics_mentioned(full_text)
        result["metodos_estatisticos"] = detect_statistical_methods(full_text)
        result["ferramentas_tecnologias"] = detect_tools_technologies(full_text)
        result["padroes_normas"] = extract_quality_standards(full_text)
        result["contexto_dominio"] = extract_context_domain(full_text)
        
        # Detecta idioma
        if re.search(r'\b(resumo|introdução|palavras[\-\s]chave|objetivo|conclusão)\b', text_first.lower()):
            result["idioma"] = "PT"
        else:
            result["idioma"] = "EN"
        
        # Tenta extrair autores do texto se não veio dos metadados
        if not result["autores"] and meta and meta.get("author"):
            result["autores"] = clean_text(meta["author"])
        
        doc.close()
        
    except Exception as e:
        result["titulo"] = os.path.splitext(filename)[0]
        result["abstract"] = f"Erro ao processar: {str(e)}"
    
    return result


def main():
    """Função principal que processa todos os PDFs e gera o CSV."""
    print("Iniciando extração de dados dos PDFs...")
    
    files = sorted([f for f in os.listdir(ARTIGOS_DIR) if f.lower().endswith('.pdf')])
    print(f"Total de PDFs encontrados: {len(files)}")
    
    fieldnames = [
        "id", "arquivo", "titulo", "autores", "ano", "abstract", "keywords",
        "doi", "veiculo_publicacao", "num_paginas", "num_referencias",
        "tamanho_amostra", "metodologia", "areas_pesquisa", "metricas_mencionadas",
        "metodos_estatisticos", "ferramentas_tecnologias", "padroes_normas",
        "contexto_dominio", "idioma"
    ]
    
    results = []
    for i, filename in enumerate(files, 1):
        filepath = os.path.join(ARTIGOS_DIR, filename)
        print(f"  [{i}/{len(files)}] Processando: {filename[:60]}...")
        data = process_pdf(filepath, filename)
        data["id"] = i
        results.append(data)
    
    # Escreve CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\nDataset enriquecido salvo em: {OUTPUT_CSV}")
    print(f"Total de artigos processados: {len(results)}")
    
    # Estatísticas
    with_abstract = sum(1 for r in results if r["abstract"])
    with_keywords = sum(1 for r in results if r["keywords"])
    with_doi = sum(1 for r in results if r["doi"])
    with_year = sum(1 for r in results if r["ano"])
    with_methods = sum(1 for r in results if r["metodologia"])
    with_metrics = sum(1 for r in results if r["metricas_mencionadas"])
    with_stats = sum(1 for r in results if r["metodos_estatisticos"])
    with_tools = sum(1 for r in results if r["ferramentas_tecnologias"])
    with_standards = sum(1 for r in results if r["padroes_normas"])
    with_domain = sum(1 for r in results if r["contexto_dominio"])
    with_sample = sum(1 for r in results if r["tamanho_amostra"])
    with_authors = sum(1 for r in results if r["autores"])
    
    print(f"\n--- Cobertura dos campos ---")
    print(f"  Título:               {sum(1 for r in results if r['titulo'])}/{len(results)}")
    print(f"  Autores:              {with_authors}/{len(results)}")
    print(f"  Ano:                  {with_year}/{len(results)}")
    print(f"  Abstract:             {with_abstract}/{len(results)}")
    print(f"  Keywords:             {with_keywords}/{len(results)}")
    print(f"  DOI:                  {with_doi}/{len(results)}")
    print(f"  Metodologia:          {with_methods}/{len(results)}")
    print(f"  Áreas de pesquisa:    {sum(1 for r in results if r['areas_pesquisa'])}/{len(results)}")
    print(f"  Métricas detectadas:  {with_metrics}/{len(results)}")
    print(f"  Métodos estatísticos: {with_stats}/{len(results)}")
    print(f"  Ferramentas:          {with_tools}/{len(results)}")
    print(f"  Padrões/Normas:       {with_standards}/{len(results)}")
    print(f"  Contexto/Domínio:     {with_domain}/{len(results)}")
    print(f"  Tamanho da Amostra:   {with_sample}/{len(results)}")


if __name__ == "__main__":
    main()
