"""Gera evidencias para o Grupo 2 a partir do bundle.

Saidas:
- grupo2_respostas.csv: uma linha por artigo com os campos necessarios para
  responder as perguntas do enunciado.
- grupo2_auditoria.csv: cobertura dos dados requeridos por pergunta/RQ.
- grupo2_resumo.json: resumo de cobertura para tomada de decisao.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path

from medicao.shared import config
from medicao.shared.contract import Bundle
from medicao.shared.pdf import read_pdf
from medicao.shared.storage import read_csv, write_csv, write_json
from medicao.shared.text import clean_text, significant_terms

EXPECTED_CORPUS_SIZE = int(os.environ.get("MEDICAO_EXPECTED_CORPUS_SIZE", "73"))

RESPOSTAS_FIELDS = [
    "id",
    "title",
    "article_authors",
    "cohort",
    "year",
    "arquivo",
    "areas_pesquisa",
    "metodologia",
    "metricas_mencionadas",
    "metodos_estatisticos",
    "venue",
    "venue_type",
    "citations",
    "num_referencias",
    "n_references",
    "alignment_score",
    "alignment_nivel",
    "temas_ementa",
    "qtd_temas_ementa",
    "max_score_relevancia",
    "max_percentual_match",
    "relacao_disciplina_proxy",
    "alinhado_plano_proxy",
    "replicabilidade_proxy",
    "natureza_artigo_proxy",
    "nivel_aluno_proxy",
    "qualidade_proxy",
    "prestige_score",
    "pagerank_centrality",
    "community_id",
    "rubric_score",
    "arqi_equal",
    "arqi_pca",
    "arqi_no_prestige",
    "replicavel",
    "pratico_teorico",
    "nivel_aluno",
    "agregou",
    "relacao_disciplina",
    "alinhado_plano",
    "artigos_relacionados",
    "sobreposicao_tematica_qtd",
    "evidencias_extraidas",
    "pendencias",
]

AUDITORIA_FIELDS = [
    "grupo",
    "pergunta",
    "dados_necessarios",
    "arquivo_fonte",
    "linhas_cobertas",
    "linhas_total",
    "cobertura_percentual",
    "status",
    "observacao",
]


def _norm_key(value: str) -> str:
    return " ".join(significant_terms(value, min_len=3))


def _has_value(value) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return text != "" and text.lower() not in {"nan", "none", "na", "n/a", "pd.na"}


def _float(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _load_optional_csv(path: Path) -> list[dict]:
    return read_csv(path) if path.exists() else []


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("id", "")).strip(): r for r in rows if _has_value(r.get("id"))}


def _by_title(rows: list[dict]) -> dict[str, dict]:
    return {
        _norm_key(str(r.get("title", ""))): r
        for r in rows
        if _has_value(r.get("title"))
    }


def _merge_extra(artigo: dict, rows_by_id: dict[str, dict], rows_by_title: dict[str, dict]) -> dict:
    row = rows_by_id.get(str(artigo.get("id", "")).strip())
    if row:
        return row
    return rows_by_title.get(_norm_key(str(artigo.get("title", ""))), {})


def _article_text(artigo: dict) -> str:
    filename = str(artigo.get("arquivo", "")).strip()
    if not filename:
        return ""
    path = config.ARTIGOS_DIR / filename
    if not path.exists():
        return ""
    try:
        return read_pdf(path).full_text[:60_000]
    except Exception:
        return ""


def _replicabilidade(text: str) -> str:
    t = text.lower()
    strong = [
        "replication package",
        "artifact available",
        "data availability",
        "github.com",
        "zenodo",
        "source code is available",
        "dataset is available",
    ]
    medium = [
        "dataset",
        "experimental protocol",
        "survey instrument",
        "we provide",
        "available at",
        "appendix",
    ]
    if any(p in t for p in strong):
        return "2-alta"
    if any(p in t for p in medium):
        return "1-parcial"
    return "0-nao_detectada"


def _natureza(artigo: dict, text: str) -> str:
    metodologia = str(artigo.get("metodologia", "")).lower()
    t = text.lower()
    empirico = bool(
        re.search(r"\b(empirical|experiment|case study|survey|questionnaire|dataset)\b", t)
        or "estudo empirico" in metodologia
        or "experimento" in metodologia
        or "survey" in metodologia
    )
    secundario = any(k in metodologia for k in ("revis", "mapeamento", "meta"))
    propositivo = bool(re.search(r"\b(framework|model|approach|tool|method)\b", t[:8000]))
    if empirico and propositivo:
        return "misto"
    if empirico:
        return "pratico_empirico"
    if secundario:
        return "teorico_secundario"
    if propositivo:
        return "teorico_propositivo"
    return "nao_classificado"


def _nivel_aluno(artigo: dict, text: str) -> str:
    methods = str(artigo.get("metodos_estatisticos", ""))
    metrics = str(artigo.get("metricas_mencionadas", ""))
    advanced_hits = len([m for m in methods.split(";") if m.strip()])
    advanced_hits += len([m for m in metrics.split(";") if m.strip()]) // 3
    if re.search(r"\b(deep learning|bayesian|random forest|svm|pca|meta-analysis)\b", text.lower()):
        advanced_hits += 2
    if advanced_hits >= 5:
        return "avancado"
    if advanced_hits >= 2:
        return "intermediario"
    return "basico_intermediario"


def _alignment_nivel(score: str, max_score: int) -> str:
    if _has_value(score):
        value = _float(score)
        if value >= 0.50:
            return "alto"
        if value >= 0.35:
            return "medio"
        return "baixo"
    if max_score >= 4:
        return "alto"
    if max_score >= 2:
        return "medio"
    return "baixo"


def _qualidade(row: dict, artigo: dict) -> str:
    if _has_value(row.get("arqi_equal")):
        value = _float(row.get("arqi_equal"))
        if value >= 0.70:
            return "alta_por_arqi"
        if value >= 0.45:
            return "media_por_arqi"
        return "baixa_por_arqi"

    refs = int(_float(row.get("n_references") or artigo.get("num_referencias"), 0))
    has_method = _has_value(artigo.get("metodologia"))
    has_abstract = _has_value(artigo.get("abstract"))
    if refs >= 30 and has_method and has_abstract:
        return "alta_proxy_local"
    if refs >= 10 and (has_method or has_abstract):
        return "media_proxy_local"
    return "baixa_proxy_local"


def _relation_summary(relacoes: list[dict]) -> tuple[str, int, int, float]:
    if not relacoes:
        return "", 0, 0, 0.0
    ordered = sorted(relacoes, key=lambda r: _float(r.get("score_relevancia")), reverse=True)
    topics = []
    seen = set()
    for rel in ordered:
        topic = str(rel.get("ementa_topico", "")).strip()
        if topic and topic not in seen:
            seen.add(topic)
            topics.append(topic)
    max_score = int(_float(ordered[0].get("score_relevancia"), 0))
    max_pct = _float(ordered[0].get("percentual_match"), 0.0)
    return "; ".join(topics[:6]), len(topics), max_score, max_pct


def _similar_articles(artigos: list[dict]) -> dict[str, list[tuple[str, float]]]:
    ids = [str(a.get("id", "")) for a in artigos]
    terms = {
        str(a.get("id", "")): significant_terms(
            " ".join(
                str(a.get(c, ""))
                for c in (
                    "title",
                    "keywords",
                    "areas_pesquisa",
                    "metricas_mencionadas",
                    "metodologia",
                    "metodos_estatisticos",
                )
            )
        )
        for a in artigos
    }
    titles = {str(a.get("id", "")): str(a.get("title", "")) for a in artigos}
    out: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1 :]:
            a, b = terms[id_a], terms[id_b]
            if not a or not b:
                continue
            score = len(a & b) / len(a | b)
            if score >= 0.20:
                out[id_a].append((f"{id_b}:{titles[id_b][:70]}", score))
                out[id_b].append((f"{id_a}:{titles[id_a][:70]}", score))
    for artigo_id in out:
        out[artigo_id].sort(key=lambda item: item[1], reverse=True)
    return out


def _coverage(rows: list[dict], cols: list[str]) -> tuple[int, int, float]:
    total = len(rows)
    if total == 0:
        return 0, 0, 0.0
    covered = sum(1 for row in rows if all(_has_value(row.get(col)) for col in cols))
    pct = round(covered / total * 100, 1)
    return covered, total, pct


def _status(pct: float) -> str:
    if pct >= 95:
        return "ok"
    if pct >= 60:
        return "parcial"
    return "ausente"


def _audit_row(
    grupo: str,
    pergunta: str,
    dados: str,
    fonte: str,
    rows: list[dict],
    cols: list[str],
    observacao: str = "",
) -> dict:
    covered, total, pct = _coverage(rows, cols)
    return {
        "grupo": grupo,
        "pergunta": pergunta,
        "dados_necessarios": dados,
        "arquivo_fonte": fonte,
        "linhas_cobertas": covered,
        "linhas_total": total,
        "cobertura_percentual": pct,
        "status": _status(pct),
        "observacao": observacao,
    }


def _build_audit(
    b: Bundle,
    artigos: list[dict],
    respostas: list[dict],
    enriched_rows: list[dict],
    baseline_exists: bool,
    figs_count: int,
) -> list[dict]:
    audit = []
    corpus_pct = round(min(len(artigos), EXPECTED_CORPUS_SIZE) / EXPECTED_CORPUS_SIZE * 100, 1)
    audit.append(
        {
            "grupo": "Corpus",
            "pergunta": "Compilado de todos os artigos apresentados em sala",
            "dados_necessarios": f"{EXPECTED_CORPUS_SIZE} artigos esperados",
            "arquivo_fonte": str(b.path("artigos")),
            "linhas_cobertas": len(artigos),
            "linhas_total": EXPECTED_CORPUS_SIZE,
            "cobertura_percentual": corpus_pct,
            "status": _status(corpus_pct),
            "observacao": "Ajuste MEDICAO_EXPECTED_CORPUS_SIZE se a turma tiver outro total oficial.",
        }
    )
    audit.extend(
        [
            _audit_row(
                "RQ01",
                "Caracterizacao de temas e anos",
                "title, year, areas_pesquisa",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["title", "year", "areas_pesquisa"],
            ),
            _audit_row(
                "RQ01",
                "Revista/conferencia e tipo de veiculo",
                "venue_type e venue",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["venue_type"],
                "venue local e heuristico; ACARI enrich melhora o nome do veiculo.",
            ),
            _audit_row(
                "RQ01",
                "Citacoes e referencias",
                "citations, n_references/num_referencias",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["citations", "n_references"],
                "Sem OpenAlex/Crossref, citacoes ficam ausentes.",
            ),
            _audit_row(
                "RQ02",
                "Corpus supera baseline aleatoria em alinhamento",
                "alignment_score e baseline.csv",
                str(b.dir / "acari" / "data"),
                enriched_rows,
                ["alignment_score"],
                "baseline.csv presente" if baseline_exists else "baseline.csv ausente; rode ACARI baseline.",
            ),
            _audit_row(
                "RQ03",
                "Alinhamento difere entre turmas",
                "cohort e alignment_score",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["cohort", "alignment_score"],
                "A coluna cohort precisa estar preenchida para H2.",
            ),
            _audit_row(
                "RQ04",
                "Tipos de veiculo diferem entre turmas",
                "cohort e venue_type",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["cohort", "venue_type"],
                "A coluna cohort precisa estar preenchida para H3.",
            ),
            _audit_row(
                "RQ05",
                "Ranking ARQI estavel",
                "arqi_equal, arqi_pca, arqi_no_prestige",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["arqi_equal", "arqi_pca", "arqi_no_prestige"],
                "Rode ACARI ate index para preencher o indicador final.",
            ),
            _audit_row(
                "Qualidade",
                "Analise critica dos artigos",
                "replicabilidade, natureza, nivel, relacao, alinhamento",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                [
                    "replicabilidade_proxy",
                    "natureza_artigo_proxy",
                    "nivel_aluno_proxy",
                    "relacao_disciplina_proxy",
                    "alinhado_plano_proxy",
                ],
                "Campos proxy sao automaticos; use rubric.csv para avaliacao humana.",
            ),
            _audit_row(
                "Rede tematica",
                "Sobreposicao, continuidade e complementacao de temas",
                "temas_ementa e artigos_relacionados",
                str(b.dir / "grupo2_respostas.csv"),
                respostas,
                ["temas_ementa", "artigos_relacionados"],
            ),
            {
                "grupo": "Visualizacoes",
                "pergunta": "Visualizacoes graficas dos dados coletados",
                "dados_necessarios": "graph.json e figuras ACARI",
                "arquivo_fonte": f"{b.graph_path}; {b.dir / 'acari' / 'figs'}",
                "linhas_cobertas": int(b.graph_path.exists()) + figs_count,
                "linhas_total": 2,
                "cobertura_percentual": 100.0 if b.graph_path.exists() and figs_count else 50.0 if b.graph_path.exists() else 0.0,
                "status": "ok" if b.graph_path.exists() and figs_count else "parcial" if b.graph_path.exists() else "ausente",
                "observacao": f"{figs_count} figura(s) ACARI encontradas.",
            },
        ]
    )
    return audit


def run(bundle: str = config.DEFAULT_BUNDLE, write: bool = True) -> list[dict]:
    b = Bundle(bundle)
    artigos = b.load("artigos")
    relacoes = b.load("relacoes")

    acari_data = b.dir / "acari" / "data"
    enriched_path = acari_data / "enriched.csv"
    baseline_path = acari_data / "baseline.csv"
    rubric_path = acari_data / "rubric.csv"
    rubric_template_path = acari_data / "rubric_template.csv"

    enriched_rows = _load_optional_csv(enriched_path)
    rubric_rows = _load_optional_csv(rubric_path if rubric_path.exists() else rubric_template_path)

    enriched_by_id = _by_id(enriched_rows)
    enriched_by_title = _by_title(enriched_rows)
    rubric_by_id = _by_id(rubric_rows)
    rubric_by_title = _by_title(rubric_rows)

    rel_por_artigo: dict[str, list[dict]] = defaultdict(list)
    for rel in relacoes:
        rel_por_artigo[str(rel.get("artigo_id", ""))].append(rel)

    similares = _similar_articles(artigos)

    respostas = []
    for artigo in artigos:
        artigo_id = str(artigo.get("id", ""))
        extra = _merge_extra(artigo, enriched_by_id, enriched_by_title)
        rubric = _merge_extra(artigo, rubric_by_id, rubric_by_title)
        texto = _article_text(artigo)
        temas, qtd_temas, max_score, max_pct = _relation_summary(rel_por_artigo.get(artigo_id, []))
        alignment = extra.get("alignment_score", "")
        alignment_nivel = _alignment_nivel(alignment, max_score)
        relacionados = similares.get(artigo_id, [])

        pendencias = []
        for col in ("cohort", "citations", "alignment_score", "arqi_equal"):
            value = extra.get(col, artigo.get(col, ""))
            if not _has_value(value):
                pendencias.append(col)
        if len(artigos) < EXPECTED_CORPUS_SIZE:
            pendencias.append("corpus_incompleto")

        resposta = {
            "id": artigo_id,
            "title": artigo.get("title", ""),
            "article_authors": artigo.get("article_authors", ""),
            "cohort": extra.get("cohort", artigo.get("cohort", "")),
            "year": extra.get("year_api", artigo.get("year", "")) or artigo.get("year", ""),
            "arquivo": artigo.get("arquivo", ""),
            "areas_pesquisa": artigo.get("areas_pesquisa", ""),
            "metodologia": artigo.get("metodologia", ""),
            "metricas_mencionadas": artigo.get("metricas_mencionadas", ""),
            "metodos_estatisticos": artigo.get("metodos_estatisticos", ""),
            "venue": extra.get("venue", artigo.get("veiculo_publicacao", "")),
            "venue_type": extra.get("venue_type", artigo.get("venue_type", "")),
            "citations": extra.get("citations", ""),
            "num_referencias": artigo.get("num_referencias", ""),
            "n_references": extra.get("n_references", artigo.get("num_referencias", "")),
            "alignment_score": alignment,
            "alignment_nivel": alignment_nivel,
            "temas_ementa": temas,
            "qtd_temas_ementa": qtd_temas,
            "max_score_relevancia": max_score,
            "max_percentual_match": max_pct,
            "relacao_disciplina_proxy": "direta" if max_score >= 3 else "indireta" if max_score else "nao_detectada",
            "alinhado_plano_proxy": "sim" if alignment_nivel in {"alto", "medio"} else "baixo",
            "replicabilidade_proxy": _replicabilidade(texto),
            "natureza_artigo_proxy": _natureza(artigo, texto),
            "nivel_aluno_proxy": _nivel_aluno(artigo, texto),
            "qualidade_proxy": _qualidade(extra, artigo),
            "prestige_score": extra.get("prestige_score", ""),
            "pagerank_centrality": extra.get("pagerank_centrality", ""),
            "community_id": extra.get("community_id", ""),
            "rubric_score": extra.get("rubric_score", ""),
            "arqi_equal": extra.get("arqi_equal", ""),
            "arqi_pca": extra.get("arqi_pca", ""),
            "arqi_no_prestige": extra.get("arqi_no_prestige", ""),
            "replicavel": rubric.get("replicavel", ""),
            "pratico_teorico": rubric.get("pratico_teorico", ""),
            "nivel_aluno": rubric.get("nivel_aluno", ""),
            "agregou": rubric.get("agregou", ""),
            "relacao_disciplina": rubric.get("relacao_disciplina", ""),
            "alinhado_plano": rubric.get("alinhado_plano", ""),
            "artigos_relacionados": "; ".join(label for label, _ in relacionados[:5]),
            "sobreposicao_tematica_qtd": len(relacionados),
            "evidencias_extraidas": clean_text(texto[:350]),
            "pendencias": "; ".join(pendencias),
        }
        respostas.append(resposta)

    figs_dir = b.dir / "acari" / "figs"
    figs_count = len(list(figs_dir.glob("*.png"))) if figs_dir.exists() else 0
    auditoria = _build_audit(
        b=b,
        artigos=artigos,
        respostas=respostas,
        enriched_rows=enriched_rows,
        baseline_exists=baseline_path.exists() and baseline_path.stat().st_size > 0,
        figs_count=figs_count,
    )

    if write:
        write_csv(b.path("grupo2_respostas"), respostas, RESPOSTAS_FIELDS)
        write_csv(b.path("grupo2_auditoria"), auditoria, AUDITORIA_FIELDS)
        resumo = {
            "bundle": bundle,
            "artigos_atual": len(artigos),
            "artigos_esperado": EXPECTED_CORPUS_SIZE,
            "acari_enriched": enriched_path.exists(),
            "baseline": baseline_path.exists(),
            "figuras_acari": figs_count,
            "auditoria_status": {
                row["pergunta"]: row["status"]
                for row in auditoria
            },
        }
        write_json(b.dir / "grupo2_resumo.json", resumo)
        print(f"[grupo2] -> {b.path('grupo2_respostas')} ({len(respostas)} registros)")
        print(f"[grupo2] -> {b.path('grupo2_auditoria')}")

    return respostas
