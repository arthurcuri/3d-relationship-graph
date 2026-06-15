"""
src/viz.py – Pipeline Step 10: Figures

8 figures → outputs/figs/ (.pdf + .png)
+ network_bibliographic.gexf (Gephi export)

Interpretations encoded per stats.py checkpoint:
  H1: efeito gigante (δ=+0.922) — corpus fortemente alinhado à ementa
  H2: único par BH-significativo: Coração EC vs Lourdes 2026/1 (p=0.005, δ=+0.599)
  H3: sem drift de venue_type entre turmas (χ²=4.10, p=0.663)
"""
from __future__ import annotations

import json
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
import networkx as nx
import seaborn as sns
from scipy import stats

from .config import ENRICHED_CSV, BASELINE_CSV, FIGS, RANDOM_SEED, GROUP_COLUMN

# ── palette / style ───────────────────────────────────────────────────────────
_TUBLUE = "#009867"
_GRAY   = "#9e9e9e"

_COHORT_ORDER = [
    "Coracao Eucaristico 2025/2",
    "Lourdes 2025/2",
    "Lourdes 2026/1",
]
_COHORT_LABELS = {
    "Coracao Eucaristico 2025/2": "CE 2025/2",
    "Lourdes 2025/2":             "L 2025/2",
    "Lourdes 2026/1":             "L 2026/1",
}
_COHORT_PAL = {
    "Coracao Eucaristico 2025/2": "#ff7f0e",
    "Lourdes 2025/2":             "#1f77b4",
    "Lourdes 2026/1":             "#2ca02c",
}

sns.set_theme(style="whitegrid", font_scale=1.05)
plt.rcParams.update({
    "savefig.dpi": 150,
    "font.family": "DejaVu Sans",
    "axes.unicode_minus": False,
})


# ── helpers ───────────────────────────────────────────────────────────────────

def _save(fig: plt.Figure, name: str) -> None:
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    print(f"  [ok] {name}.pdf + .png")


def _article_label(row: pd.Series) -> str:
    """Short author label for figures: uses article_authors when available."""
    v = row.get("article_authors")
    if pd.notna(v) and str(v).strip() not in ("", "nan"):
        # already formatted as "Lastname, F. et al." — return first token (lastname)
        return str(v).split(",")[0].strip()
    # fallback: strip from title (last word)
    t = str(row.get("title", ""))
    return t.split()[-1] if t else "?"


def _sig_bracket(ax, x1: float, x2: float, y: float, label: str,
                 h: float = 0.01) -> None:
    """Draw a significance bracket between two x positions."""
    ax.plot([x1, x1, x2, x2], [y, y + h, y + h, y], lw=1.4, color="black")
    ax.text((x1 + x2) / 2, y + h + 0.002, label, ha="center", va="bottom",
            fontsize=12, fontweight="bold")


def _load(enriched: str, baseline: str | None = None):
    df = pd.read_csv(enriched, dtype=str, keep_default_na=False).replace("", pd.NA)
    for col in ["alignment_score", "prestige_score", "citations", "n_references",
                "log_citations", "recency_score", "pagerank_centrality",
                "arqi_pca", "arqi_equal", "arqi_no_prestige"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["in_statistical_test"] = df["in_statistical_test"].map(
        {"True": True, "False": False}
    )
    bdf = None
    if baseline:
        bdf = pd.read_csv(baseline)
        bdf["alignment_score"] = pd.to_numeric(bdf["alignment_score"], errors="coerce")
    return df, bdf


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1 — alignment_proxy
# ─────────────────────────────────────────────────────────────────────────────
def fig_alignment_proxy(df: pd.DataFrame, bdf: pd.DataFrame) -> None:
    corpus   = df[df["in_statistical_test"] == True]["alignment_score"].dropna().values
    baseline = bdf["alignment_score"].dropna().values

    # recompute key stats
    u_stat, mwu_p = stats.mannwhitneyu(corpus, baseline, alternative="greater")
    cd_mat = np.sign(corpus[:, None] - baseline[None, :])
    cd = float(cd_mat.mean())

    fig, ax = plt.subplots(figsize=(6, 5))
    parts = ax.violinplot(
        [corpus, baseline], positions=[1, 2],
        showmedians=True, showextrema=True, widths=0.7,
    )
    colors = [_TUBLUE, _GRAY]
    for body, c in zip(parts["bodies"], colors):
        body.set_facecolor(c)
        body.set_alpha(0.75)
        body.set_edgecolor("black")
    for part in ("cmedians", "cbars", "cmins", "cmaxes"):
        parts[part].set_color("black")

    # overlay strip
    rng = np.random.default_rng(RANDOM_SEED)
    for pos, data in [(1, corpus), (2, baseline)]:
        jitter = rng.uniform(-0.06, 0.06, size=len(data))
        ax.scatter(pos + jitter, data, s=8, alpha=0.4, color="black", zorder=3)

    ax.set_xticks([1, 2])
    ax.set_xticklabels([
        f"Corpus\n(n={len(corpus)})",
        f"Baseline SE\n(n={len(baseline)})",
    ], fontsize=11)
    ax.set_ylabel("Alignment Score (similaridade à ementa)")
    ax.set_title("H1 — Alinhamento do corpus vs. baseline aleatório")

    footer = (
        f"Mann-Whitney U={u_stat:.0f}, p<0.001 (one-sided)  |  "
        f"Cliff's δ={cd:+.3f} (grande)  |  Permutação p<0.001  (n={N_PERM:,} resamples)"
    )
    ax.text(0.5, -0.13, footer, ha="center", va="top", transform=ax.transAxes,
            fontsize=7.5, style="italic", color="#444")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "alignment_proxy")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2 — alignment_by_cohort
# ─────────────────────────────────────────────────────────────────────────────
def fig_alignment_by_cohort(df: pd.DataFrame) -> None:
    if not GROUP_COLUMN or GROUP_COLUMN not in df.columns:
        print(f"  [SKIP] group_column='{GROUP_COLUMN}' absent — skipping alignment_by_cohort")
        return
    sub = df[df["in_statistical_test"] == True].copy()
    sub = sub[sub[GROUP_COLUMN].isin(_COHORT_ORDER)]
    sub["turma"] = sub[GROUP_COLUMN].map(_COHORT_LABELS)

    order_labels = [_COHORT_LABELS[c] for c in _COHORT_ORDER if c in sub["cohort"].values]
    counts = sub.groupby("turma")["alignment_score"].count()
    tick_labels = [f"{lbl}\n(n={counts.get(lbl, 0)})" for lbl in order_labels]

    palette_mapped = {_COHORT_LABELS[k]: v for k, v in _COHORT_PAL.items()}

    fig, ax = plt.subplots(figsize=(7, 5))
    sns.boxplot(data=sub.dropna(subset=["alignment_score"]),
                x="turma", y="alignment_score", hue="turma",
                order=order_labels, palette=palette_mapped,
                width=0.45, linewidth=1.2, fliersize=0, ax=ax, legend=False)
    sns.stripplot(data=sub.dropna(subset=["alignment_score"]),
                  x="turma", y="alignment_score", hue="turma",
                  order=order_labels, palette=palette_mapped,
                  size=5, alpha=0.6, jitter=True, ax=ax, legend=False)

    ax.set_xticks(range(len(order_labels)))
    ax.set_xticklabels(tick_labels, fontsize=10)
    ax.set_xlabel("")
    ax.set_ylabel("Alignment Score")
    ax.set_title("H2 — Alinhamento por turma (KW p=0.005)")

    # significance bracket: CE (pos 0) vs Lourdes 2026/1 (pos 2)
    y_top = sub["alignment_score"].dropna().max()
    _sig_bracket(ax, 0, 2, y_top + 0.04, "** (p=0.005)", h=0.025)

    ax.text(0.5, -0.14,
            "Dunn (BH): CE vs L 2026/1 p=0.005, δ=+0.599 (grande) | "
            "L 2025/2 vs L 2026/1 p=0.079 (ns)",
            ha="center", va="top", transform=ax.transAxes,
            fontsize=7.5, style="italic", color="#444")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "alignment_by_cohort")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3 — network_bibliographic
# ─────────────────────────────────────────────────────────────────────────────
def fig_network(df: pd.DataFrame) -> None:
    n = len(df)

    # parse referenced_works
    ref_lists: list[set[str]] = []
    for val in df.get("referenced_works", pd.Series(dtype=str)):
        if pd.notna(val) and str(val).startswith("["):
            try:
                ref_lists.append(set(json.loads(str(val))))
            except Exception:
                ref_lists.append(set())
        else:
            ref_lists.append(set())

    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            shared = len(ref_lists[i] & ref_lists[j])
            if shared > 0:
                G.add_edge(i, j, weight=shared)

    # layout
    pos = nx.spring_layout(G, seed=RANDOM_SEED, k=2.2, iterations=80)

    # community colors
    comm = df["community_id"].astype("Int64").tolist()
    unique_comms = sorted(set(c for c in comm if pd.notna(c)))
    # size of each community
    comm_sizes = Counter(c for c in comm if pd.notna(c))
    # top-8 by size get distinct colors; rest → gray
    top_comms = {c for c, _ in comm_sizes.most_common(8)}
    palette = plt.get_cmap("tab10").colors
    comm_to_color = {c: palette[i % len(palette)]
                     for i, c in enumerate(sorted(top_comms))}

    node_colors = [comm_to_color.get(c, _GRAY) for c in comm]

    # node sizes proportional to pagerank (already [0,1])
    pr_vals = df["pagerank_centrality"].fillna(0).values
    node_sizes = 80 + pr_vals * 400

    fig, ax = plt.subplots(figsize=(12, 9))
    ax.set_facecolor("#f8f8f8")

    # edges
    weights = [G[u][v]["weight"] for u, v in G.edges()]
    max_w = max(weights) if weights else 1
    nx.draw_networkx_edges(G, pos, ax=ax,
                           width=[0.5 + 1.5 * (w / max_w) for w in weights],
                           alpha=0.35, edge_color="#aaaaaa")

    # nodes
    nx.draw_networkx_nodes(G, pos, ax=ax,
                           node_color=node_colors,
                           node_size=node_sizes,
                           alpha=0.88, linewidths=0.5,
                           edgecolors="white")

    # labels: top-10 by pagerank
    top10_idx = df["pagerank_centrality"].nlargest(10).index.tolist()
    labels = {i: _article_label(df.loc[i]) for i in top10_idx}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                            font_size=7.5, font_color="black",
                            font_weight="bold")

    # legend
    patches = [mpatches.Patch(color=comm_to_color[c], label=f"Comunidade {c}")
               for c in sorted(top_comms)]
    patches.append(mpatches.Patch(color=_GRAY, label="Outras comunidades"))
    ax.legend(handles=patches, fontsize=8, loc="upper left",
              title="Comunidade Louvain", title_fontsize=8,
              framealpha=0.8)
    ax.set_title(
        f"Rede de Acoplamento Bibliográfico (n={n} artigos, {G.number_of_edges()} arestas)\n"
        "Tamanho ∝ PageRank · Cor = comunidade Louvain · Labels: top-10 PageRank"
    )
    ax.axis("off")
    fig.tight_layout()
    _save(fig, "network_bibliographic")

    # GEXF export
    G_out = G.copy()
    for i, (_, row) in enumerate(df.iterrows()):
        aa = row.get("article_authors")
        G_out.nodes[i]["label"]      = str(aa) if pd.notna(aa) and str(aa).strip() not in ("", "nan") else str(row.get("title", ""))[:40]
        G_out.nodes[i]["alignment"]  = float(row["alignment_score"]) if pd.notna(row.get("alignment_score")) else 0.0
        G_out.nodes[i]["community"]  = int(row["community_id"]) if pd.notna(row.get("community_id")) else -1
        G_out.nodes[i]["pagerank"]   = float(row["pagerank_centrality"]) if pd.notna(row.get("pagerank_centrality")) else 0.0
        G_out.nodes[i]["cohort"]     = str(row.get("cohort", ""))
    gexf_path = FIGS / "network_bibliographic.gexf"
    nx.write_gexf(G_out, str(gexf_path))
    print(f"  [ok] network_bibliographic.gexf (Gephi)")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4 — arqi_ranking
# ─────────────────────────────────────────────────────────────────────────────
def fig_arqi_ranking(df: pd.DataFrame) -> None:
    sub = df[df["in_statistical_test"] == True].copy()
    sub = sub.dropna(subset=["arqi_equal"])
    sub = sub.nlargest(20, "arqi_equal")
    sub = sub.sort_values("arqi_equal", ascending=True)

    labels = sub.apply(_article_label, axis=1)
    if GROUP_COLUMN and GROUP_COLUMN in sub.columns:
        colors = [_COHORT_PAL.get(c, _GRAY) for c in sub[GROUP_COLUMN]]
    else:
        colors = [_TUBLUE] * len(sub)
    is_preprint = sub["venue_type"].str.lower().eq("preprint") if "venue_type" in sub.columns else pd.Series([False]*len(sub))

    fig, ax = plt.subplots(figsize=(8, 7))
    bars = ax.barh(range(len(sub)), sub["arqi_equal"], color=colors,
                   height=0.65, alpha=0.85)

    # dashed border for preprints
    for i, (bar, pre) in enumerate(zip(bars, is_preprint)):
        if pre:
            bar.set_edgecolor("black")
            bar.set_linewidth(1.5)
            bar.set_linestyle("--")

    ax.set_yticks(range(len(sub)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("ARQI (pesos iguais)")
    ax.set_title("Top-20 artigos por ARQI — corpus em estudo")

    # legend cohorts (only when groups are available)
    legend_handles = []
    if GROUP_COLUMN and GROUP_COLUMN in sub.columns:
        legend_handles = [
            mpatches.Patch(color=v, label=_COHORT_LABELS.get(k, k))
            for k, v in _COHORT_PAL.items()
            if k in sub[GROUP_COLUMN].values
        ]
    legend_handles.append(
        mpatches.Patch(facecolor="white", edgecolor="black",
                       linewidth=1.5, linestyle="--", label="Preprint")
    )
    ax.legend(handles=legend_handles, fontsize=8, loc="lower right")
    ax.set_xlim(0, sub["arqi_equal"].max() * 1.12)
    fig.tight_layout()
    _save(fig, "arqi_ranking")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 5 — quadrant_relevance_quality
# ─────────────────────────────────────────────────────────────────────────────
def fig_quadrant(df: pd.DataFrame) -> None:
    sub = df[df["in_statistical_test"] == True].copy()

    # y-axis: prestige_score; fallback = log_citations normalized
    lc_raw = np.log1p(sub["citations"].fillna(0))
    lc_min, lc_max = lc_raw.min(), lc_raw.max()
    lc_norm = (lc_raw - lc_min) / (lc_max - lc_min) if lc_max > lc_min else lc_raw

    sub["y_val"] = sub["prestige_score"]
    sub["y_proxy"] = sub["prestige_score"].isna()
    sub.loc[sub["y_proxy"], "y_val"] = lc_norm[sub["y_proxy"]]

    sub = sub.dropna(subset=["alignment_score", "y_val"])

    # bubble size
    sub["bubble"] = np.log1p(sub["citations"].fillna(0)) * 25 + 20

    x_mid = sub["alignment_score"].median()
    y_mid = sub["y_val"].median()

    fig, ax = plt.subplots(figsize=(9, 6))
    if GROUP_COLUMN and GROUP_COLUMN in sub.columns:
        group_iter = [(cohort, sub[GROUP_COLUMN] == cohort) for cohort in _COHORT_ORDER]
    else:
        group_iter = [("all", pd.Series([True] * len(sub), index=sub.index))]
    for cohort, mask in group_iter:
        if not mask.any():
            continue
        grp = sub[mask]
        color = _COHORT_PAL.get(cohort, _TUBLUE)
        label = _COHORT_LABELS.get(cohort, "Corpus")
        ax.scatter(grp.loc[~grp["y_proxy"], "alignment_score"],
                   grp.loc[~grp["y_proxy"], "y_val"],
                   s=grp.loc[~grp["y_proxy"], "bubble"],
                   c=color, alpha=0.75, label=label,
                   edgecolors="white", linewidths=0.5)
        # preprint proxy points (different marker)
        proxy_mask = mask & sub["y_proxy"]
        if proxy_mask.any():
            ax.scatter(sub.loc[proxy_mask, "alignment_score"],
                       sub.loc[proxy_mask, "y_val"],
                       s=sub.loc[proxy_mask, "bubble"],
                       c=color, alpha=0.50, marker="D",
                       edgecolors="black", linewidths=0.8)

    ax.axvline(x_mid, color="#888", lw=1, ls="--", alpha=0.6)
    ax.axhline(y_mid, color="#888", lw=1, ls="--", alpha=0.6)

    # quadrant labels
    xr, xl = ax.get_xlim() if ax.get_xlim()[1] > 0 else (0, 1)
    xr, xl = sub["alignment_score"].max(), sub["alignment_score"].min()
    yr, yl = sub["y_val"].max(),           sub["y_val"].min()
    off_x, off_y = (xr - xl) * 0.03, (yr - yl) * 0.03
    for (qx, qy, qlab) in [
        (xr - off_x, yr - off_y, "Alta relevância\nAlto prestígio"),
        (xl + off_x, yr - off_y, "Baixa relevância\nAlto prestígio"),
        (xl + off_x, yl + off_y, "Baixa relevância\nBaixo prestígio"),
        (xr - off_x, yl + off_y, "Alta relevância\nBaixo prestígio"),
    ]:
        ax.text(qx, qy, qlab, ha="right" if qx > x_mid else "left",
                va="top" if qy > y_mid else "bottom",
                fontsize=7.5, color="#555",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6))

    ax.set_xlabel("Alignment Score (similaridade à ementa)")
    ax.set_ylabel("Prestige Score (or log-cit. norm. se prestige=NA  ◆)")
    ax.set_title("Relevância vs. Qualidade — corpus em estudo (in_stat_test=True)")

    handles, labs = ax.get_legend_handles_labels()
    handles.append(plt.scatter([], [], marker="D", s=40, c="gray",
                               edgecolors="black", label="y=log-cit. proxy"))
    ax.legend(handles=handles + [handles[-1]], fontsize=8)
    fig.tight_layout()
    _save(fig, "quadrant_relevance_quality")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 6 — correlation_heatmap
# ─────────────────────────────────────────────────────────────────────────────
def fig_correlation_heatmap(df: pd.DataFrame) -> None:
    cols_raw = {
        "alignment": "alignment_score",
        "prestige":  "prestige_score",
        "log(cit.)": None,   # computed below
        "recency":   "recency_score",
        "pagerank":  "pagerank_centrality",
        "n_refs":    "n_references",
    }
    data: dict[str, pd.Series] = {}

    for label, col in cols_raw.items():
        if col and col in df.columns:
            data[label] = pd.to_numeric(df[col], errors="coerce")
        elif label == "log(cit.)":
            lc = np.log1p(pd.to_numeric(df.get("citations", pd.NA), errors="coerce"))
            mx = lc.max()
            data[label] = lc / mx if mx > 0 else lc
        elif label == "n_refs":
            nr = pd.to_numeric(df.get("n_references", pd.NA), errors="coerce")
            mx = nr.max()
            data[label] = nr / mx if mx > 0 else nr

    mat_df = pd.DataFrame(data).dropna(how="all")
    labels = list(mat_df.columns)
    n = len(labels)
    corr = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(n):
            xi, xj = mat_df.iloc[:, i], mat_df.iloc[:, j]
            common = xi.notna() & xj.notna()
            if common.sum() >= 5:
                r, _ = stats.spearmanr(xi[common], xj[common])
                corr[i, j] = r

    fig, ax = plt.subplots(figsize=(7, 6))
    mask = np.zeros_like(corr, dtype=bool)
    mask[np.triu_indices_from(mask, k=1)] = True
    sns.heatmap(corr, ax=ax, mask=mask,
                cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                annot=False, linewidths=0.5, linecolor="#ddd",
                xticklabels=labels, yticklabels=labels,
                cbar_kws={"shrink": 0.8, "label": "Spearman ρ"})

    # annotate |r| >= 0.3
    for i in range(n):
        for j in range(i + 1):  # lower triangle
            v = corr[i, j]
            if np.isnan(v) or abs(v) < 0.3:
                continue
            ax.text(j + 0.5, i + 0.5, f"{v:.2f}", ha="center", va="center",
                    fontsize=9, fontweight="bold",
                    color="white" if abs(v) > 0.6 else "black")

    ax.set_title("Correlações de Spearman entre dimensões do corpus\n(anotadas |ρ| ≥ 0.30)")
    ax.tick_params(axis="both", labelsize=9)
    fig.tight_layout()
    _save(fig, "correlation_heatmap")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 7 — theme_distribution
# ─────────────────────────────────────────────────────────────────────────────
def fig_theme_distribution(df: pd.DataFrame) -> None:
    if not GROUP_COLUMN or GROUP_COLUMN not in df.columns:
        print(f"  [SKIP] group_column='{GROUP_COLUMN}' absent — skipping theme_distribution")
        return
    if "community_id" not in df.columns or df["community_id"].isna().all():
        print("  [SKIP] community_id absent — skipping theme_distribution")
        return
    sub = df[df["in_statistical_test"] == True].copy()

    # derive theme label from top_topic + community_id
    # group small communities (< 3 articles) as "Outros"
    comm_sizes = sub["community_id"].value_counts()
    large_comms = comm_sizes[comm_sizes >= 3].index.tolist()

    # label each community from its most common top_topic
    def _comm_label(cid, grp):
        if cid not in large_comms:
            return "Outros"
        topics = grp["top_topic"].dropna()
        if topics.empty:
            return f"C{int(cid)}"
        return topics.value_counts().index[0][:25]  # truncate

    sub["theme"] = sub.apply(
        lambda row: _comm_label(
            row.get("community_id"),
            sub[sub["community_id"] == row.get("community_id")]
        ), axis=1
    )

    # pivot: theme × turma
    sub["turma"] = sub[GROUP_COLUMN].map(_COHORT_LABELS).fillna(sub[GROUP_COLUMN])
    # if all turmas are NA/empty, skip
    if sub["turma"].isna().all() or (sub["turma"].astype(str).str.strip() == "").all():
        print(f"  [SKIP] all '{GROUP_COLUMN}' values empty — skipping theme_distribution")
        return
    sub = sub[sub["turma"].notna() & (sub["turma"].astype(str).str.strip() != "")]
    if sub.empty:
        print(f"  [SKIP] no rows with valid '{GROUP_COLUMN}' — skipping theme_distribution")
        return
    pivot = (
        sub.groupby(["turma", "theme"])
        .size()
        .unstack(fill_value=0)
    )
    reindex_order = [_COHORT_LABELS.get(c, c) for c in _COHORT_ORDER
                     if _COHORT_LABELS.get(c, c) in pivot.index]
    if reindex_order:
        pivot = pivot.reindex(reindex_order)
    if pivot.empty:
        print("  [SKIP] pivot empty after reindex — skipping theme_distribution")
        return
    # proportional
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100

    # put "Outros" last
    cols = [c for c in pivot_pct.columns if c != "Outros"] + \
           (["Outros"] if "Outros" in pivot_pct.columns else [])
    pivot_pct = pivot_pct[cols]

    colors = plt.get_cmap("Set2").colors
    fig, ax = plt.subplots(figsize=(9, 4))
    pivot_pct.plot(kind="bar", stacked=True, ax=ax,
                   color=[colors[i % len(colors)] for i in range(len(cols))],
                   edgecolor="white", linewidth=0.5)
    ax.set_ylabel("% artigos")
    ax.set_xlabel("")
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0, fontsize=10)
    ax.set_title("Distribuição de temas (comunidades Louvain) por turma")
    ax.legend(title="Tema / Comunidade", bbox_to_anchor=(1.01, 1),
              loc="upper left", fontsize=8, title_fontsize=8)
    ax.set_ylim(0, 110)
    fig.tight_layout()
    _save(fig, "theme_distribution")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 8 — venue_type_dist
# ─────────────────────────────────────────────────────────────────────────────
def fig_venue_type_dist(df: pd.DataFrame) -> None:
    df2 = df.copy()
    df2["venue_type_clean"] = df2["venue_type"].fillna("unknown")
    df2["in_test"] = df2["in_statistical_test"].map(
        {True: "Incluído (in_stat_test)", False: "Excluído"}
    ).fillna("Excluído")

    order = (df2["venue_type_clean"].value_counts().index.tolist())
    counts = df2.groupby(["venue_type_clean", "in_test"]).size().unstack(fill_value=0)
    counts = counts.reindex(order)

    fig, ax = plt.subplots(figsize=(8, 4))
    bottom = np.zeros(len(counts))
    for col, color in [
        ("Incluído (in_stat_test)", _TUBLUE),
        ("Excluído",               _GRAY),
    ]:
        if col in counts.columns:
            vals = counts[col].values
            ax.bar(range(len(counts)), vals, bottom=bottom,
                   color=color, label=col, edgecolor="white", linewidth=0.5)
            bottom += vals

    ax.set_xticks(range(len(counts)))
    ax.set_xticklabels(counts.index, rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("N artigos")
    ax.set_title(f"Distribuição de venue_type no corpus (n={len(df)})")
    ax.legend(fontsize=9)
    ax.text(0.99, 0.97,
            "H3: sem drift de tipo entre turmas\n(χ²=4.10, dof=6, p=0.663)",
            ha="right", va="top", transform=ax.transAxes, fontsize=8,
            style="italic", color="#444")
    fig.tight_layout()
    _save(fig, "venue_type_dist")


# ─────────────────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────────────────
N_PERM = 10_000  # for annotation in fig 1


def main() -> None:
    print("\n=== VIZ ===")
    FIGS.mkdir(parents=True, exist_ok=True)

    print("\n[load] Reading data ...")
    df, bdf = _load(str(ENRICHED_CSV), str(BASELINE_CSV) if BASELINE_CSV.exists() else None)
    print(f"  corpus: {len(df)} rows | baseline: {len(bdf) if bdf is not None else 0}")

    print("\n[1] alignment_proxy ...")
    if bdf is not None:
        fig_alignment_proxy(df, bdf)
    else:
        print("  [SKIP] baseline.csv not found")

    print("\n[2] alignment_by_cohort ...")
    fig_alignment_by_cohort(df)

    print("\n[3] network_bibliographic ...")
    fig_network(df)

    print("\n[4] arqi_ranking ...")
    fig_arqi_ranking(df)

    print("\n[5] quadrant_relevance_quality ...")
    fig_quadrant(df)

    print("\n[6] correlation_heatmap ...")
    fig_correlation_heatmap(df)

    print("\n[7] theme_distribution ...")
    fig_theme_distribution(df)

    print("\n[8] venue_type_dist ...")
    fig_venue_type_dist(df)

    print(f"\n── Viz Summary ──────────────────────────────────────")
    figs = list(FIGS.glob("*.pdf"))
    print(f"  {len(figs)} PDFs in outputs/figs/")
    print("─" * 55)


if __name__ == "__main__":
    main()
