"""
src/export_latex.py – Pipeline Step 11: LaTeX Tables

Generates 5 .tex files in outputs/tables/:
  tab_corpus_summary.tex   (2 parts if >30 rows)
  tab_stats_proxy.tex
  tab_stats_cohort.tex
  tab_arqi_top10.tex
  tab_sensitivity.tex
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy import stats

from .config import ENRICHED_CSV, BASELINE_CSV, TABLES, RANDOM_SEED, N_PERMUTATIONS, GROUP_COLUMN


# ── helpers ───────────────────────────────────────────────────────────────────

def _tex(s: str, maxlen: int | None = None) -> str:
    """Escape special LaTeX characters and optionally truncate."""
    s = unicodedata.normalize("NFC", str(s))
    s = s.replace("\\", r"\textbackslash{}")
    for ch, esc in [
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
        ("#", r"\#"), ("_", r"\_"), ("^", r"\^{}"),
        ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
    ]:
        s = s.replace(ch, esc)
    if maxlen and len(s) > maxlen:
        s = s[: maxlen - 1] + "…"
    return s


def _article_author(row: pd.Series) -> str:
    """Return article_authors if available, else NA marker."""
    v = row.get("article_authors")
    if pd.notna(v) and str(v).strip() not in ("", "nan"):
        return str(v).strip()
    return "—"


_COHORT_ABBR = {
    "Lourdes 2025/2":               "L 25/2",
    "Coracao Eucaristico 2025/2":   "CE 25/2",
    "Lourdes 2026/1":               "L 26/1",
}


def _save(content: str, name: str) -> None:
    path = TABLES / f"{name}.tex"
    path.write_text(content, encoding="utf-8")
    print(f"  [ok] {name}.tex  ({len(content.splitlines())} lines)")


def _booktabs_table(header: str, rows: list[str], footer: str = "",
                    size: str = r"\scriptsize", label: str = "",
                    caption: str = "") -> str:
    col_spec = "l" * header.count("&") + "l"
    n_cols = header.count("&") + 1
    col_spec = "|".join(["l"] * n_cols)
    lines = [
        size,
        r"\begin{tabular}{" + col_spec + "}",
        r"\toprule",
        header + r" \\",
        r"\midrule",
    ]
    lines += [r + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    if footer:
        lines += [r"\vspace{1ex}", r"\newline", r"{\tiny " + footer + "}"]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Table 1 — Corpus Summary
# ─────────────────────────────────────────────────────────────────────────────
def tab_corpus_summary(df: pd.DataFrame) -> None:
    sub = df[df["in_statistical_test"] == True].copy()
    sub = sub.dropna(subset=["arqi_equal"]).sort_values("arqi_equal", ascending=False)

    def _year(row):
        y = row.get("year_api")
        if pd.isna(y) or str(y) in ("", "nan"):
            y = row.get("year")
        return str(int(float(y))) if pd.notna(y) and str(y) not in ("", "nan") else "NA"

    def _venue_abbr(v):
        if pd.isna(v) or str(v).strip() in ("", "nan"):
            return "—"
        words = str(v).split()
        # Take first 3 words, max 18 chars
        abbr = " ".join(words[:3])
        return abbr[:18]

    show_group = bool(GROUP_COLUMN and GROUP_COLUMN in sub.columns)
    if show_group:
        header = (
            r"\textbf{Autor} & \textbf{Título} & \textbf{Turma} & \textbf{Ano} & "
            r"\textbf{Veículo} & \textbf{Cit.} & \textbf{Align.} & \textbf{ARQI}"
        )
    else:
        header = (
            r"\textbf{Autor} & \textbf{Título} & \textbf{Ano} & "
            r"\textbf{Veículo} & \textbf{Cit.} & \textbf{Align.} & \textbf{ARQI}"
        )

    rows = []
    for _, row in sub.iterrows():
        autor  = _tex(_article_author(row))
        title  = _tex(str(row.get("title", "")), 45)
        year   = _year(row)
        venue  = _tex(_venue_abbr(row.get("venue")))
        cit    = str(int(row["citations"])) if pd.notna(row.get("citations")) else "NA"
        aln    = f"{float(row['alignment_score']):.2f}" if pd.notna(row.get("alignment_score")) else "NA"
        arqi   = f"{float(row['arqi_equal']):.2f}"
        if show_group:
            turma = _tex(_COHORT_ABBR.get(row.get(GROUP_COLUMN, ""), row.get(GROUP_COLUMN, "")))
            rows.append(f"{autor} & {title} & {turma} & {year} & {venue} & {cit} & {aln} & {arqi}")
        else:
            rows.append(f"{autor} & {title} & {year} & {venue} & {cit} & {aln} & {arqi}")

    # Split at 32 rows
    for part_idx, chunk in enumerate([rows[:32], rows[32:]], start=1):
        if not chunk:
            break
        content = _booktabs_table(
            header, chunk,
            footer=(
                r"Ordenado por ARQI decrescente. "
                r"Apenas artigos com in\_stat\_test=True. "
                r"Turmas: L=Lourdes, CE=Coração Eucarístico."
            ),
            size=r"\scriptsize",
        )
        suffix = f"_part{part_idx}" if len(rows) > 32 else ""
        _save(content, f"tab_corpus_summary{suffix}")


# ─────────────────────────────────────────────────────────────────────────────
# Table 2 — Stats Proxy
# ─────────────────────────────────────────────────────────────────────────────
def tab_stats_proxy(df: pd.DataFrame, bdf: pd.DataFrame | None) -> None:
    if bdf is None:
        _save("% baseline.csv not found", "tab_stats_proxy")
        return

    corpus   = df[df["in_statistical_test"] == True]["alignment_score"].dropna().values
    baseline = bdf["alignment_score"].dropna().values

    if len(corpus) < 2 or len(baseline) < 2:
        _save("% tab_stats_proxy skipped: insufficient data (corpus or baseline < 2 samples)", "tab_stats_proxy")
        print(f"  [SKIP] tab_stats_proxy — corpus={len(corpus)}, baseline={len(baseline)} (min 2)")
        return

    u_stat, mwu_p = stats.mannwhitneyu(corpus, baseline, alternative="greater")
    cd_mat = np.sign(corpus[:, None] - baseline[None, :])
    cd = float(cd_mat.mean())

    rng = np.random.default_rng(RANDOM_SEED)
    obs_u, _ = stats.mannwhitneyu(corpus, baseline, alternative="two-sided")
    combined = np.concatenate([corpus, baseline])
    count = sum(
        1 for _ in range(N_PERMUTATIONS)
        if stats.mannwhitneyu(
            rng.permutation(combined)[:len(corpus)],
            rng.permutation(combined)[len(corpus):],
            alternative="two-sided",
        )[0] >= obs_u
    )
    perm_p = count / N_PERMUTATIONS

    header = (
        r"\textbf{n corpus} & \textbf{n baseline} & "
        r"\textbf{U} & \textbf{p (one-sided)} & "
        r"\textbf{Cliff's $\delta$} & \textbf{Perm. p}"
    )
    row = (
        f"{len(corpus)} & {len(baseline)} & "
        f"{u_stat:.0f} & {mwu_p:.5f} & "
        f"{cd:+.3f} & {perm_p:.5f}"
    )
    content = _booktabs_table(
        header, [row],
        footer=(
            r"Mann-Whitney U (one-sided: corpus $>$ baseline). "
            r"Cliff's $\delta$: $|$d$|$$\geq$0.474 = grande. "
            rf"Permutação: {N_PERMUTATIONS:,} resamples, two-sided."
        ),
        size=r"\footnotesize",
    )
    _save(content, "tab_stats_proxy")


# ─────────────────────────────────────────────────────────────────────────────
# Table 3 — Stats Cohort
# ─────────────────────────────────────────────────────────────────────────────
def tab_stats_cohort(df: pd.DataFrame) -> None:
    if not GROUP_COLUMN or GROUP_COLUMN not in df.columns:
        _save("% tab_stats_cohort skipped: group_column not configured", "tab_stats_cohort")
        print("  [SKIP] tab_stats_cohort — group_column absent")
        return
    sub = df[df["in_statistical_test"] == True].copy()
    groups: dict[str, np.ndarray] = {}
    for name, grp in sub.groupby(GROUP_COLUMN)["alignment_score"]:
        arr = grp.dropna().values
        if len(arr) >= 3:
            groups[name] = arr

    if len(groups) < 2:
        _save("% tab_stats_cohort skipped: need at least 2 cohort groups with >= 3 samples", "tab_stats_cohort")
        print(f"  [SKIP] tab_stats_cohort — apenas {len(groups)} grupo(s) com dados suficientes")
        return

    kw_h, kw_p = stats.kruskal(*groups.values())

    long = pd.concat(
        [pd.DataFrame({"alignment_score": arr, "cohort": name})
         for name, arr in groups.items()],
        ignore_index=True,
    )
    dunn = sp.posthoc_dunn(
        long, val_col="alignment_score", group_col="cohort", p_adjust="fdr_bh"
    )

    def _cliff(a, b):
        return float(np.sign(a[:, None] - b[None, :]).mean())

    def _interp(d):
        ad = abs(d)
        if ad < 0.147: return "neg."
        if ad < 0.330: return "peq."
        if ad < 0.474: return "méd."
        return "grande"

    header = (
        r"\textbf{Teste} & \textbf{H / Estatística} & "
        r"\textbf{p (BH-corr.)} & \textbf{Cliff's $\delta$} & \textbf{Magnitude}"
    )

    names = list(groups.keys())
    abbr  = {n: _COHORT_ABBR.get(n, n) for n in names}
    rows  = [
        rf"Kruskal-Wallis (global) & H={kw_h:.3f} & {kw_p:.5f} & — & —",
    ]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            n1, n2 = names[i], names[j]
            p_val = dunn.loc[n1, n2]
            cd    = _cliff(groups[n1], groups[n2])
            sig   = r"*" if p_val < 0.05 else ""
            a1, a2 = abbr.get(n1, n1), abbr.get(n2, n2)
            rows.append(
                rf"Dunn: {_tex(a1)} vs {_tex(a2)} {sig}"
                rf" & — & {p_val:.4f} & {cd:+.3f} & {_interp(cd)}"
            )

    content = _booktabs_table(
        header, rows,
        footer=(
            r"p-valores Dunn corrigidos por Benjamini-Hochberg. "
            r"* par significativo (p$<$0.05). "
            r"Cliff's $\delta$: peq.=$<$0.330, méd.=$<$0.474, grande=$\geq$0.474."
        ),
        size=r"\footnotesize",
    )
    _save(content, "tab_stats_cohort")


# ─────────────────────────────────────────────────────────────────────────────
# Table 4 — ARQI Top-10
# ─────────────────────────────────────────────────────────────────────────────
def tab_arqi_top10(df: pd.DataFrame) -> None:
    sub = df[df["in_statistical_test"] == True].copy()
    sub = sub.dropna(subset=["arqi_equal"]).nlargest(10, "arqi_equal")

    dim_cols = [
        ("Align.", "alignment_score"),
        ("Prest.", "prestige_score"),
        ("log(Cit.)", "log_citations"),
        ("Rec.",  "recency_score"),
        ("Centr.", "pagerank_centrality"),
        ("Rubric", "rubric_score"),
    ]

    def _fmt(v, col=None):
        if pd.isna(v):
            return "—"
        return f"{float(v):.3f}"

    header = (
        r"\textbf{Autor} & "
        + " & ".join(rf"\textbf{{{lbl}}}" for lbl, _ in dim_cols)
        + r" & \textbf{ARQI}"
    )

    rows = []
    for _, row in sub.iterrows():
        vals = [_fmt(row.get(col)) for _, col in dim_cols]
        arqi = f"{float(row['arqi_equal']):.3f}"
        rows.append(_tex(_article_author(row)) + " & " + " & ".join(vals) + " & " + arqi)

    content = _booktabs_table(
        header, rows,
        footer=(
            r"ARQI = média ponderada por pesos iguais das dimensões disponíveis. "
            r"Rubric = NA (template não preenchido). "
            r"log(Cit.) = rank percentil de $\log(\text{cit.}+1)$."
        ),
        size=r"\footnotesize",
    )
    _save(content, "tab_arqi_top10")


# ─────────────────────────────────────────────────────────────────────────────
# Table 5 — Sensitivity (Spearman between ARQI rankings)
# ─────────────────────────────────────────────────────────────────────────────
def tab_sensitivity(df: pd.DataFrame) -> None:
    pairs = [
        ("ARQI PCA", "arqi_pca",         "ARQI Igual",        "arqi_equal"),
        ("ARQI PCA", "arqi_pca",         "ARQI s/ Prestígio", "arqi_no_prestige"),
        ("ARQI Igual","arqi_equal",      "ARQI s/ Prestígio", "arqi_no_prestige"),
    ]

    header = (
        r"\textbf{Comparação} & \textbf{Spearman $\rho$} & "
        r"\textbf{p-valor} & \textbf{n}"
    )
    rows = []
    for n1, c1, n2, c2 in pairs:
        x1 = pd.to_numeric(df[c1], errors="coerce").dropna()
        x2 = pd.to_numeric(df[c2], errors="coerce").dropna()
        idx = x1.index.intersection(x2.index)
        if len(idx) < 3:
            continue
        rho, pv = stats.spearmanr(x1.loc[idx], x2.loc[idx])
        rows.append(
            rf"{_tex(n1)} vs {_tex(n2)} & {rho:.3f} & {pv:.4f} & {len(idx)}"
        )

    content = _booktabs_table(
        header, rows,
        footer=(
            r"Estabilidade do ranking ARQI entre as três configurações de peso. "
            r"$\rho\geq0.917$ indica alta consistência."
        ),
        size=r"\footnotesize",
    )
    _save(content, "tab_sensitivity")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print("\n=== EXPORT LATEX ===")
    TABLES.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)
    # article_authors stays as str; numeric columns converted below
    for col in ["alignment_score", "prestige_score", "citations", "log_citations",
                "recency_score", "pagerank_centrality", "arqi_pca", "arqi_equal",
                "arqi_no_prestige", "rubric_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["in_statistical_test"] = df["in_statistical_test"].map(
        {"True": True, "False": False}
    )

    bdf = None
    if BASELINE_CSV.exists():
        bdf = pd.read_csv(BASELINE_CSV)
        bdf["alignment_score"] = pd.to_numeric(bdf["alignment_score"], errors="coerce")

    print("\n[1] tab_corpus_summary ...")
    tab_corpus_summary(df)

    print("\n[2] tab_stats_proxy ...")
    tab_stats_proxy(df, bdf)

    print("\n[3] tab_stats_cohort ...")
    tab_stats_cohort(df)

    print("\n[4] tab_arqi_top10 ...")
    tab_arqi_top10(df)

    print("\n[5] tab_sensitivity ...")
    tab_sensitivity(df)

    print(f"\n── Export LaTeX Summary ─────────────────────────────")
    for f in sorted(TABLES.glob("*.tex")):
        print(f"  {f.name}")
    print("─" * 55)


if __name__ == "__main__":
    main()
