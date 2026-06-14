"""
src/index.py – Pipeline Step 8: ARQI Index

Computes ARQI (Alignment-Rubric Quality Index) for each article in 3 configurations:
  (a) arqi_pca          PCA-derived weights on available dimensions
  (b) arqi_equal        Equal weights on available dimensions
  (c) arqi_no_prestige  Equal weights excluding prestige_score

Graceful NA policy: each article's score is the weighted mean of its AVAILABLE
dimensions. Missing dimensions are excluded from that article's calculation (not
treated as 0). This is explicitly documented here to be clear in the Beamer deck.

Dimensions:
  alignment_score     [0,1]  cosine similarity to course syllabus
  prestige_score      [0,1]  venue prestige (CORE/SJR/OpenAlex h-index)
  log_citations       [0,1]  percentile rank of log(citations+1)
  recency_score       [0,1]  publication year (newer → higher)
  centrality_score    [0,1]  normalised PageRank from bib coupling network
  rubric_score        [0,1]  rubric evaluation (NA until template is filled)

Adds to enriched.csv: log_citations, recency_score, centrality_score,
                       arqi_pca, arqi_equal, arqi_no_prestige
Prints: PCA loadings, Spearman ρ between 3 rankings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .config import ENRICHED_CSV, RANDOM_SEED

_DIMS_ALL = [
    "alignment_score",
    "prestige_score",
    "log_citations",
    "recency_score",
    "centrality_score",
    "rubric_score",
]
_DIMS_NO_PRESTIGE = [d for d in _DIMS_ALL if d != "prestige_score"]


def _add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # log_citations → percentile rank of log(citations+1)
    cit = pd.to_numeric(df.get("citations", pd.NA), errors="coerce")
    df["log_citations"] = np.log1p(cit).rank(pct=True, na_option="keep")

    # recency_score: prefer year_api, fall back to year
    year = pd.to_numeric(df.get("year_api", pd.NA), errors="coerce")
    if year.isna().all():
        year = pd.to_numeric(df.get("year", pd.NA), errors="coerce")
    ymin, ymax = year.min(), year.max()
    df["recency_score"] = (year - ymin) / (ymax - ymin) if ymax > ymin else pd.NA

    # centrality_score = normalised PageRank (already [0,1] from network.py)
    df["centrality_score"] = pd.to_numeric(
        df.get("pagerank_centrality", pd.NA), errors="coerce"
    )

    # ensure all dim columns are numeric
    for col in ["alignment_score", "prestige_score", "rubric_score"]:
        df[col] = pd.to_numeric(df.get(col, pd.NA), errors="coerce")

    return df


def _weighted_mean(row: pd.Series, dims: list[str], weights: dict[str, float]) -> float:
    avail = [(d, weights[d]) for d in dims if d in row.index
             and pd.notna(row[d]) and weights.get(d, 0) > 0]
    if not avail:
        return float("nan")
    total_w = sum(w for _, w in avail)
    return sum(float(row[d]) * w for d, w in avail) / total_w


def _derive_pca_weights(df: pd.DataFrame, dims: list[str]) -> dict[str, float]:
    """Absolute loadings from PC1 on rows where all dims are present."""
    sub = df[dims].dropna()
    if len(sub) < max(5, len(dims)):
        print(f"  [WARN] Only {len(sub)} complete rows for PCA — using equal weights")
        return {d: 1.0 for d in dims}

    X = StandardScaler().fit_transform(sub)
    pca = PCA(n_components=1, random_state=RANDOM_SEED)
    pca.fit(X)
    loadings = np.abs(pca.components_[0])
    weights = {d: float(w) for d, w in zip(dims, loadings)}
    var_exp = pca.explained_variance_ratio_[0]
    print(f"  PC1 explains {var_exp:.1%} of variance")
    for d, w in weights.items():
        print(f"    {d}: {w:.4f}")
    return weights


def _spearman(col1: pd.Series, col2: pd.Series, label: str) -> None:
    common = col1.dropna().index.intersection(col2.dropna().index)
    if len(common) < 3:
        print(f"  {label}: insufficient data")
        return
    rho, pv = stats.spearmanr(col1.loc[common], col2.loc[common])
    print(f"  {label}: ρ = {rho:.3f}  (p = {pv:.4f},  n = {len(common)})")


def main() -> None:
    print("\n=== INDEX ===")
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)

    # ── derived dimensions ────────────────────────────────────────────────
    print("\n[1] Computing derived dimensions ...")
    df = _add_derived(df)
    for col in ["log_citations", "recency_score", "centrality_score"]:
        n = df[col].notna().sum()
        print(f"  {col}: {n}/{len(df)} resolved")

    # ── PCA weights (exclude rubric — likely all NA) ───────────────────────
    print("\n[2] Deriving PCA weights ...")
    pca_dims = [d for d in _DIMS_ALL if d != "rubric_score"]
    pca_w = _derive_pca_weights(df, pca_dims)
    # rubric gets the mean of the other weights
    pca_w["rubric_score"] = float(np.mean(list(pca_w.values())))

    equal_w       = {d: 1.0 for d in _DIMS_ALL}
    no_prestige_w = {d: 1.0 for d in _DIMS_NO_PRESTIGE}

    # ── compute ARQI ──────────────────────────────────────────────────────
    print("\n[3] Computing ARQI scores ...")
    df["arqi_pca"]         = df.apply(lambda r: _weighted_mean(r, _DIMS_ALL, pca_w), axis=1)
    df["arqi_equal"]       = df.apply(lambda r: _weighted_mean(r, _DIMS_ALL, equal_w), axis=1)
    df["arqi_no_prestige"] = df.apply(lambda r: _weighted_mean(r, _DIMS_NO_PRESTIGE, no_prestige_w), axis=1)

    # ── Spearman correlations ─────────────────────────────────────────────
    print("\n[4] Spearman correlations between ARQI rankings:")
    _spearman(df["arqi_pca"], df["arqi_equal"],        "arqi_pca vs arqi_equal      ")
    _spearman(df["arqi_pca"], df["arqi_no_prestige"],  "arqi_pca vs arqi_no_prestige")
    _spearman(df["arqi_equal"], df["arqi_no_prestige"],"arqi_equal vs arqi_no_prestige")

    df.to_csv(ENRICHED_CSV, index=False)
    print("  [ok] enriched.csv updated")

    # ── summary ──────────────────────────────────────────────────────────
    print(f"\n── Index Summary ─────────────────────────────────────")
    for col in ["arqi_pca", "arqi_equal", "arqi_no_prestige"]:
        s = df[col].astype(float, errors="ignore").dropna()
        if len(s):
            print(f"  {col}: n={len(s)}, range=[{s.min():.3f},{s.max():.3f}], median={s.median():.3f}")
    print("─" * 55)


if __name__ == "__main__":
    main()
