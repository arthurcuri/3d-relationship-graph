"""Detectores temáticos para artigos (classificação por padrões regex).

Cada função recebe o texto do artigo e retorna uma string com os itens
detectados separados por ``; ``. São funções puras, fáceis de testar.
"""

from __future__ import annotations

import re

METHODOLOGY_MAP = {
    "Revisão Sistemática": [r"systematic\s+(literature\s+)?review", r"revisão\s+sistemática"],
    "Mapeamento Sistemático": [r"systematic\s+mapping", r"mapeamento\s+sistemático"],
    "Experimento Controlado": [r"controlled\s+experiment", r"experimento\s+controlado", r"randomized\s+experiment"],
    "Estudo de Caso": [r"case\s+stud(y|ies)", r"estudo\s+de\s+caso"],
    "Survey/Questionário": [r"\bsurvey\b", r"questionnaire", r"questionário"],
    "Estudo Empírico": [r"empirical\s+stud(y|ies)", r"estudo\s+empírico"],
    "Meta-análise": [r"meta[\-\s]analy", r"meta[\-\s]análise"],
    "Revisão Multivocal": [r"multivocal\s+(literature\s+)?review"],
    "Proposta de Framework": [r"propos(e|ed|ing)\s+(a\s+)?framework", r"framework\s+for"],
    "Análise Estatística": [r"statistical\s+analy", r"análise\s+estatística"],
    "Machine Learning": [r"machine\s+learning", r"deep\s+learning", r"neural\s+network"],
    "Replicação": [r"replicat(ion|ed|ing)", r"replicação"],
    "GQM": [r"\bgqm\b", r"goal\s+question\s+metric"],
    "Mineração de Repositórios": [r"mining\s+(software\s+)?repositor", r"mineração"],
}

METRIC_MAP = {
    "LOC/SLOC": [r"\b(loc|sloc|lines\s+of\s+code)\b"],
    "Complexidade Ciclomática": [r"cyclomatic\s+complexity", r"complexidade\s+ciclomática", r"\bmcc\b"],
    "Complexidade Cognitiva": [r"cognitive\s+complexity", r"complexidade\s+cognitiva"],
    "Function Points": [r"function\s+point", r"pontos\s+de\s+função"],
    "Code Churn": [r"code\s+churn"],
    "Code Coverage": [r"code\s+coverage", r"cobertura\s+de\s+código"],
    "Coupling/Acoplamento": [r"\bcoupling\b", r"acoplamento", r"\bcbo\b"],
    "Cohesion/Coesão": [r"\bcohesion\b", r"coesão", r"\blcom\b"],
    "Halstead": [r"halstead"],
    "Story Points": [r"story\s+point"],
    "Velocity": [r"\bvelocity\b", r"velocidade"],
    "Lead Time": [r"lead\s+time"],
    "DORA Metrics": [r"dora\s+metric", r"deployment\s+frequency", r"change\s+failure\s+rate"],
    "Technical Debt": [r"technical\s+debt", r"dívida\s+técnica"],
    "Defect Density": [r"defect\s+density", r"densidade\s+de\s+defeito"],
    "MTTR": [r"\bmttr\b", r"mean\s+time\s+to\s+r"],
    "WMC": [r"\bwmc\b", r"weighted\s+methods?\s+per\s+class"],
    "DIT": [r"\bdit\b", r"depth\s+of\s+inheritance"],
    "NOC": [r"\bnoc\b", r"number\s+of\s+children"],
    "RFC": [r"\brfc\b", r"response\s+for\s+a?\s*class"],
    "CK Metrics": [r"\bck\s+metric", r"chidamber\s+and?\s+kemerer"],
}

TOOL_MAP = {
    "SonarQube": [r"[Ss]onar[Qq]ube", r"[Ss]onar[Ss]ource"],
    "GitHub": [r"[Gg]it[Hh]ub"],
    "GitLab": [r"[Gg]it[Ll]ab"],
    "JIRA": [r"\bJIRA\b", r"\bJira\b"],
    "Jenkins": [r"[Jj]enkins"],
    "Python": [r"\bPython\b"],
    "R (Estatístico)": [r"\bR\s+(?:software|language|statistical|package|version|environment)\b", r"\bcran\b"],
    "Java": [r"\bJava\b"],
    "SPSS": [r"\bSPSS\b"],
    "Weka": [r"\bWeka\b"],
    "scikit-learn": [r"scikit[\-\s]learn", r"sklearn"],
    "Maven": [r"\bMaven\b"],
    "Docker": [r"\bDocker\b"],
    "Kubernetes": [r"\bKubernetes\b"],
    "Eclipse": [r"\bEclipse\b"],
    "Visual Studio": [r"Visual\s+Studio"],
    "JUnit": [r"\bJUnit\b"],
    "Understand (SciTools)": [r"\bUnderstand\b"],
    "PMD": [r"\bPMD\b"],
    "FindBugs/SpotBugs": [r"\bFindBugs\b", r"\bSpotBugs\b"],
    "Checkstyle": [r"\bCheckstyle\b"],
    "ChatGPT/GPT": [r"\bChatGPT\b", r"\bGPT[\-\s]?[34]\b", r"\bOpenAI\b"],
    "GitHub Copilot": [r"[Cc]opilot"],
    "CodeLlama/LLaMA": [r"\bLLaMA\b", r"\bCode\s*Llama\b"],
    "Selenium": [r"\bSelenium\b"],
    "COSMIC": [r"\bCOSMIC\b"],
    "IFPUG": [r"\bIFPUG\b"],
    "Prometheus": [r"\bPrometheus\b"],
    "Grafana": [r"\bGrafana\b"],
    "Snowball/Scopus/IEEE Xplore": [r"\bScopus\b", r"IEEE\s+Xplore", r"\bSnowball"],
    "Google Scholar": [r"Google\s+Scholar"],
}

STAT_MAP = {
    "Teste t": [r"\bt[\-\s]test\b", r"student[\'\s]s?\s*t"],
    "Mann-Whitney": [r"mann[\-\s]whitney"],
    "Wilcoxon": [r"wilcoxon"],
    "Chi-quadrado": [r"chi[\-\s]square", r"qui[\-\s]quadrado"],
    "ANOVA": [r"\banova\b"],
    "Kruskal-Wallis": [r"kruskal[\-\s]wallis"],
    "Correlação de Pearson": [r"pearson", r"correlação\s+de\s+pearson"],
    "Correlação de Spearman": [r"spearman"],
    "Regressão Linear": [r"linear\s+regression", r"regressão\s+linear"],
    "Regressão Logística": [r"logistic\s+regression", r"regressão\s+logística"],
    "Effect Size": [r"effect\s+size", r"cohen[\'\s]s?\s*d\b", r"cliff[\'\s]s?\s*delta"],
    "Shapiro-Wilk": [r"shapiro[\-\s]wilk"],
    "Kolmogorov-Smirnov": [r"kolmogorov[\-\s]smirnov"],
    "Bootstrap": [r"\bbootstrap\b"],
    "Fisher's Exact": [r"fisher[\'\s]s?\s*exact"],
    "Bayesiana": [r"bayesian", r"bayes"],
    "Descritiva": [r"descriptive\s+statistic", r"estatística\s+descritiva", r"mean\s+and\s+standard\s+deviation"],
    "Box Plot": [r"box[\-\s]?plot", r"boxplot"],
    "Teste de Normalidade": [r"normality\s+test", r"teste\s+de\s+normalidade"],
    "Random Forest": [r"random\s+forest"],
    "SVM": [r"\bsvm\b", r"support\s+vector"],
    "K-fold/Cross-validation": [r"cross[\-\s]validat", r"k[\-\s]fold"],
    "ROC/AUC": [r"\broc\b", r"\bauc\b", r"receiver\s+operating"],
    "Precisão/Recall/F1": [r"precision.*recall", r"f[\-\s]?1[\-\s]?(?:score|measure)", r"f[\-\s]measure"],
}

DOMAIN_MAP = {
    "Open Source": [r"open[\-\s]source", r"\boss\b", r"github\s+(?:project|repositor)"],
    "Indústria": [r"industr(?:y|ial)", r"company", r"organization", r"empresa"],
    "Acadêmico": [r"academ(?:ic|y)", r"universit(?:y|ies)", r"student", r"classroom"],
    "Web/Mobile": [r"web\s+(?:app|system|service)", r"mobile\s+app"],
    "Sistemas Embarcados": [r"embedded\s+system"],
    "Microsserviços": [r"microservice"],
    "Sistemas Legados": [r"legacy\s+system"],
    "Saúde/Healthcare": [r"health(?:care)?", r"medical", r"saúde"],
    "Financeiro": [r"financ(?:ial|e)", r"banking"],
    "Educação": [r"educat(?:ion|ional)", r"educação", r"e[\-\s]learning"],
}

# Normas usam o texto original (case-sensitive)
STANDARDS_MAP = {
    "ISO/IEC 25010 (SQuaRE)": [r"ISO[\s/]*IEC\s*25010", r"SQuaRE"],
    "ISO/IEC 9126": [r"ISO[\s/]*IEC\s*9126"],
    "ISO/IEC 15939": [r"ISO[\s/]*IEC\s*15939", r"IEEE\s*15939"],
    "CMMI": [r"\bCMMI\b"],
    "Six Sigma": [r"[Ss]ix\s+[Ss]igma", r"[Ss]eis\s+[Ss]igma"],
    "GQM": [r"\bGQM\b", r"Goal[\-\s]Question[\-\s]Metric"],
    "ISO 9001": [r"ISO\s*9001"],
    "SWEBOK": [r"\bSWEBOK\b"],
    "IEEE 730": [r"IEEE\s*730"],
    "McCall Model": [r"McCall"],
    "Boehm Model": [r"Boehm\b"],
    "DORA": [r"\bDORA\b"],
    "SPACE Framework": [r"\bSPACE\b.*framework", r"SPACE\s+metric"],
}

AREA_MAP = {
    "Métricas de Software": [r"software\s+metric", r"code\s+metric", r"métrica"],
    "Qualidade de Software": [r"software\s+quality", r"qualidade\s+de\s+software", r"quality\s+model"],
    "Teste de Software": [r"software\s+test", r"test[\-\s]driven", r"teste\s+de\s+software"],
    "Manutenção de Software": [r"software\s+maintenance", r"maintainability", r"manutenção"],
    "Engenharia de Software Empírica": [r"empirical\s+software", r"engenharia.*empírica"],
    "Experimentação": [r"experiment(?:ation|s?\s+in)", r"experimentação", r"controlled\s+experiment"],
    "Métodos Ágeis": [r"agile", r"scrum", r"kanban", r"ágil"],
    "DevOps/CI-CD": [r"devops", r"continuous\s+(?:integration|delivery|deployment)"],
    "Gerenciamento de Projetos": [r"project\s+management", r"gerenciamento\s+de\s+projeto", r"scope\s+change", r"effort\s+estimation"],
    "Inteligência Artificial/ML": [r"machine\s+learning", r"artificial\s+intelligence", r"deep\s+learning", r"llm", r"ai[\-\s]generated"],
    "Segurança de Software": [r"security", r"vulnerability", r"segurança"],
    "Processo de Software": [r"software\s+process", r"cmmi", r"processo\s+de\s+software"],
    "Revisão de Código": [r"code\s+review", r"pull\s+request"],
    "Predição de Defeitos": [r"defect\s+predict", r"fault[\-\s]prone", r"bug\s+predict"],
    "Produtividade": [r"productivity", r"produtividade", r"developer\s+performance"],
    "Dívida Técnica": [r"technical\s+debt", r"dívida\s+técnica"],
}


def _detect(text: str, mapping: dict[str, list[str]]) -> list[str]:
    found = []
    for label, patterns in mapping.items():
        for pattern in patterns:
            if re.search(pattern, text):
                found.append(label)
                break
    return found


def detect_methodology(text: str) -> str:
    return "; ".join(_detect(text[:8000].lower(), METHODOLOGY_MAP))


def detect_metrics(text: str) -> str:
    return "; ".join(_detect(text[:10000].lower(), METRIC_MAP))


def detect_tools(text: str) -> str:
    return "; ".join(_detect(text, TOOL_MAP))


def detect_statistical_methods(text: str) -> str:
    return "; ".join(_detect(text.lower(), STAT_MAP))


def detect_domains(text: str) -> str:
    return "; ".join(_detect(text[:8000].lower(), DOMAIN_MAP))


def detect_standards(text: str) -> str:
    return "; ".join(_detect(text, STANDARDS_MAP))


def classify_area(text: str, filename: str) -> str:
    areas = _detect((text[:5000] + filename).lower(), AREA_MAP)
    return "; ".join(areas) if areas else "Engenharia de Software (Geral)"
