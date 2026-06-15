from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


REPO_ROOT = Path(__file__).resolve().parent
OUT_DIR = Path("outputs/metricas_bons_artigos")


def has_value(value) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text != "" and text.lower() not in {"nan", "none", "na", "n/a"}


def norm_score(value, cap: float) -> float:
    try:
        numeric = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(numeric) or math.isinf(numeric):
        return 0.0
    if cap <= 0:
        return 0.0
    return max(0.0, min(1.0, numeric / cap))


def safe_float(value, default: float = 0.0) -> float:
    try:
        numeric = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default
    if math.isnan(numeric) or math.isinf(numeric):
        return default
    return numeric


def bool_score(flag: bool) -> float:
    return 1.0 if flag else 0.0


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    return re.sub(r"\s+", " ", text).strip()


def read_pdf_text(path: Path, max_pages: int = 8) -> str:
    try:
        reader = PdfReader(str(path))
        chunks = []
        for page in reader.pages[:max_pages]:
            chunks.append(page.extract_text() or "")
        return clean_text(" ".join(chunks))
    except Exception as exc:
        return f"__PDF_READ_ERROR__ {exc}"


def count_terms(text: str, terms: list[str]) -> int:
    lower = text.lower()
    return sum(1 for term in terms if term in lower)


def split_terms(value: str) -> list[str]:
    if not has_value(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def classify_type(row: pd.Series, text: str) -> str:
    combined = " ".join(
        str(row.get(col, ""))
        for col in ["title", "abstract", "metodologia", "areas_pesquisa", "metodos_estatisticos"]
    ).lower()
    combined += " " + text[:12000].lower()

    if any(term in combined for term in ["systematic review", "literature review", "mapping study", "revisao sistematica", "survey of"]):
        return "revisao"
    if any(term in combined for term in ["experiment", "empirical", "case study", "survey", "dataset", "mining", "questionnaire", "estudo empirico"]):
        return "empirico"
    if any(term in combined for term in ["framework", "model", "approach", "tool", "taxonomy", "metodo", "modelo"]):
        return "propositivo"
    return "teorico"


def page_accessibility_score(pages: float) -> float:
    if pages <= 0:
        return 0.5
    if 8 <= pages <= 25:
        return 1.0
    if 5 <= pages < 8 or 26 <= pages <= 40:
        return 0.75
    if 41 <= pages <= 70:
        return 0.45
    return 0.3


def build_metrics() -> tuple[pd.DataFrame, dict]:
    artigos = pd.read_csv(REPO_ROOT / "datasets/medicao/artigos.csv", encoding="utf-8-sig")
    respostas = pd.read_csv(REPO_ROOT / "datasets/medicao/grupo2_respostas.csv", encoding="utf-8-sig")
    relacoes = pd.read_csv(REPO_ROOT / "datasets/medicao/relacoes.csv", encoding="utf-8-sig")

    rel_summary = (
        relacoes.groupby("artigo_id")
        .agg(
            qtd_temas_ementa=("ementa_id", "nunique"),
            max_score_relevancia=("score_relevancia", "max"),
            max_percentual_match=("percentual_match", "max"),
        )
        .reset_index()
        .rename(columns={"artigo_id": "id"})
    )

    base = artigos.merge(
        respostas[
            [
                "id",
                "alignment_nivel",
                "relacao_disciplina_proxy",
                "alinhado_plano_proxy",
                "sobreposicao_tematica_qtd",
            ]
        ],
        on="id",
        how="left",
    ).merge(rel_summary, on="id", how="left")

    rows = []
    for _, row in base.iterrows():
        pdf_path = REPO_ROOT / "data/raw/artigos" / str(row.get("arquivo", ""))
        text = read_pdf_text(pdf_path)
        lower = text.lower()

        method_terms = [
            "methodology",
            "method",
            "materials and methods",
            "metodologia",
            "research method",
            "study design",
            "experimental setup",
            "proposed method",
        ]
        results_terms = ["results", "resultados", "findings", "evaluation", "analysis"]
        limitation_terms = ["limitation", "limitations", "threats to validity", "ameacas a validade", "validity threats"]
        availability_terms = [
            "replication package",
            "data availability",
            "github.com",
            "zenodo",
            "figshare",
            "available online",
            "source code",
            "dataset is available",
            "we provide the dataset",
        ]

        has_abstract = "abstract" in lower[:6000] or has_value(row.get("abstract"))
        has_method = count_terms(lower, method_terms) > 0 or has_value(row.get("metodologia"))
        has_results = count_terms(lower, results_terms) > 0
        has_limitations = count_terms(lower, limitation_terms) > 0
        has_availability = count_terms(lower, availability_terms) > 0

        method_count = len(split_terms(row.get("metodologia", "")))
        stats_count = len(split_terms(row.get("metodos_estatisticos", "")))
        metrics_count = len(split_terms(row.get("metricas_mencionadas", "")))
        refs = safe_float(row.get("num_referencias"))
        sample = safe_float(row.get("tamanho_amostra"))
        pages = safe_float(row.get("num_paginas"))
        temas = safe_float(row.get("qtd_temas_ementa"))
        max_match = safe_float(row.get("max_percentual_match"))
        overlap = safe_float(row.get("sobreposicao_tematica_qtd"))

        article_type = classify_type(row, text)
        language = str(row.get("idioma", "")).strip().upper()
        venue_type = str(row.get("venue_type", "")).strip().lower()

        replicability = (
            0.20 * bool_score(has_method)
            + 0.15 * bool_score(sample > 0)
            + 0.15 * bool_score(stats_count > 0)
            + 0.10 * bool_score(metrics_count > 0)
            + 0.15 * bool_score(has_availability)
            + 0.10 * bool_score(has_limitations)
            + 0.15 * norm_score(refs, 40)
        )

        method_quality = (
            0.20 * norm_score(method_count, 3)
            + 0.20 * norm_score(stats_count, 5)
            + 0.15 * norm_score(math.log1p(sample), math.log1p(100))
            + 0.15 * norm_score(refs, 60)
            + 0.15 * bool_score(has_results)
            + 0.15 * bool_score(has_limitations)
        )

        pedagogical_fit = (
            0.35 * (max_match / 100.0)
            + 0.20 * norm_score(temas, 6)
            + 0.15 * bool_score(str(row.get("relacao_disciplina_proxy", "")).lower() == "direta")
            + 0.15 * bool_score(str(row.get("alinhado_plano_proxy", "")).lower() == "sim")
            + 0.15 * norm_score(overlap, 5)
        )

        practicality = (
            0.35 * bool_score(article_type == "empirico")
            + 0.20 * bool_score(sample > 0)
            + 0.15 * bool_score(metrics_count > 0)
            + 0.15 * bool_score(any(word in lower for word in ["tool", "framework", "dataset", "case study", "industrial", "repository"]))
            + 0.15 * bool_score(has_results)
        )

        complexity_penalty = min(0.35, stats_count * 0.035 + (0.15 if "bayesian" in lower or "deep learning" in lower else 0))
        accessibility = (
            0.25 * bool_score(has_abstract)
            + 0.25 * page_accessibility_score(pages)
            + 0.20 * (1.0 if language == "PT" else 0.80 if language == "EN" else 0.65)
            + 0.20 * bool_score(stats_count <= 4)
            + 0.10 * bool_score(metrics_count <= 5)
            - complexity_penalty
        )
        accessibility = max(0.0, min(1.0, accessibility))

        bibliographic_quality = (
            0.35 * norm_score(refs, 60)
            + 0.25 * bool_score(venue_type in {"journal", "conference"})
            + 0.20 * norm_score(safe_float(row.get("year")) - 2000, 26)
            + 0.20 * bool_score(has_value(row.get("doi")))
        )

        iqap = (
            0.25 * pedagogical_fit
            + 0.20 * method_quality
            + 0.20 * replicability
            + 0.15 * practicality
            + 0.10 * accessibility
            + 0.10 * bibliographic_quality
        )

        if iqap >= 0.75:
            category = "excelente"
        elif iqap >= 0.60:
            category = "bom"
        elif iqap >= 0.45:
            category = "regular"
        else:
            category = "fraco"

        rows.append(
            {
                "id": row.get("id"),
                "title": row.get("title"),
                "arquivo": row.get("arquivo"),
                "year": row.get("year"),
                "venue_type": row.get("venue_type"),
                "idioma": row.get("idioma"),
                "tipo_artigo_detectado": article_type,
                "qtd_temas_ementa": temas,
                "max_percentual_match": max_match,
                "sobreposicao_tematica_qtd": overlap,
                "num_paginas": pages,
                "num_referencias": refs,
                "tamanho_amostra": sample,
                "method_count": method_count,
                "stats_count": stats_count,
                "metrics_count": metrics_count,
                "has_abstract": has_abstract,
                "has_method": has_method,
                "has_results": has_results,
                "has_limitations_or_threats": has_limitations,
                "has_data_or_code_availability": has_availability,
                "replicability_score": round(replicability, 3),
                "method_quality_score": round(method_quality, 3),
                "pedagogical_fit_score": round(pedagogical_fit, 3),
                "practicality_score": round(practicality, 3),
                "accessibility_score": round(accessibility, 3),
                "bibliographic_quality_score": round(bibliographic_quality, 3),
                "IQAP": round(iqap, 3),
                "categoria_IQAP": category,
                "evidencia_curta": clean_text(text[:450]),
            }
        )

    metrics = pd.DataFrame(rows).sort_values(["IQAP", "method_quality_score"], ascending=False)
    summary = {
        "n_artigos": int(len(metrics)),
        "iqap_media": float(metrics["IQAP"].mean()),
        "iqap_mediana": float(metrics["IQAP"].median()),
        "categorias": metrics["categoria_IQAP"].value_counts().to_dict(),
        "tipo_artigo": metrics["tipo_artigo_detectado"].value_counts().to_dict(),
        "replicabilidade_media": float(metrics["replicability_score"].mean()),
        "qualidade_metodologica_media": float(metrics["method_quality_score"].mean()),
        "adequacao_pedagogica_media": float(metrics["pedagogical_fit_score"].mean()),
        "disponibilidade_dados_codigo": int(metrics["has_data_or_code_availability"].sum()),
        "com_limitacoes_ameacas": int(metrics["has_limitations_or_threats"].sum()),
    }
    return metrics, summary


def write_report(metrics: pd.DataFrame, summary: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUT_DIR / "metricas_bons_artigos.csv"
    report_path = OUT_DIR / "resumo_metricas_bons_artigos.md"
    metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")

    top = metrics.head(10)[["id", "title", "IQAP", "categoria_IQAP", "replicability_score", "method_quality_score", "pedagogical_fit_score"]]
    bottom = metrics.tail(10)[["id", "title", "IQAP", "categoria_IQAP", "replicability_score", "method_quality_score", "pedagogical_fit_score"]]

    def markdown_table(df: pd.DataFrame) -> str:
        cols = list(df.columns)
        lines = [
            "| " + " | ".join(cols) + " |",
            "| " + " | ".join(["---"] * len(cols)) + " |",
        ]
        for _, item in df.iterrows():
            values = []
            for col in cols:
                value = item[col]
                if isinstance(value, float):
                    value = f"{value:.3f}"
                text = str(value).replace("|", "/").replace("\n", " ")
                if len(text) > 72:
                    text = text[:69] + "..."
                values.append(text)
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    report = [
        "# Metricas adicionais para definir bons artigos",
        "",
        "Indicador proposto: IQAP (Indice de Qualidade Academica e Pedagogica).",
        "",
        "Formula:",
        "",
        "`IQAP = 0.25*adequacao_pedagogica + 0.20*qualidade_metodologica + 0.20*replicabilidade + 0.15*aplicabilidade + 0.10*acessibilidade + 0.10*qualidade_bibliografica`",
        "",
        "## Resumo",
        "",
        f"- Artigos avaliados: {summary['n_artigos']}",
        f"- IQAP medio: {summary['iqap_media']:.3f}",
        f"- IQAP mediano: {summary['iqap_mediana']:.3f}",
        f"- Categorias: {summary['categorias']}",
        f"- Tipos detectados: {summary['tipo_artigo']}",
        f"- Replicabilidade media: {summary['replicabilidade_media']:.3f}",
        f"- Qualidade metodologica media: {summary['qualidade_metodologica_media']:.3f}",
        f"- Adequacao pedagogica media: {summary['adequacao_pedagogica_media']:.3f}",
        f"- Artigos com indicio de dados/codigo disponivel: {summary['disponibilidade_dados_codigo']}",
        f"- Artigos com limitacoes/ameacas detectadas: {summary['com_limitacoes_ameacas']}",
        "",
        "## Top 10 por IQAP",
        "",
        markdown_table(top),
        "",
        "## 10 menores IQAP",
        "",
        markdown_table(bottom),
        "",
        "## Como usar no trabalho",
        "",
        "Use o ARQI como indicador bibliometrico/semantico e o IQAP como indicador pedagogico-metodologico. "
        "Assim, um bom artigo para a disciplina nao e apenas famoso ou recente: ele tambem precisa ser alinhado ao plano de ensino, "
        "metodologicamente claro, replicavel, aplicavel e compreensivel no nivel do aluno.",
    ]
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(metrics_path.resolve())
    print(report_path.resolve())


if __name__ == "__main__":
    metrics_df, summary_dict = build_metrics()
    write_report(metrics_df, summary_dict)
