"""
src/stats.py – Pipeline Step 9: Statistical Tests  (CHECKPOINT)

H1 — Proxy: corpus alignment_score > baseline alignment_score
  Mann-Whitney U (one-sided), Cliff's delta, 10k permutation (two-sided)

H2 — Cohort: alignment_score differs across the 3 cohorts
  Kruskal-Wallis; if significant → Dunn post-hoc with Benjamini-Hochberg;
  Cliff's delta for each pair

H3 — Venue-type drift across cohorts
  Chi-squared + Cramér's V

Scope: in_statistical_test == True articles only.
All p-values reported exact; no threshold-based binary conclusions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests
import scikit_posthocs as sp

from .config import ENRICHED_CSV, BASELINE_CSV, RANDOM_SEED, N_PERMUTATIONS, GROUP_COLUMN


# ── effect-size helpers ───────────────────────────────────────────────────────

def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    mat = np.sign(a[:, None].astype(float) - b[None, :].astype(float))
    return float(mat.mean())


def interpret_cliff(d: float) -> str:
    ad = abs(d)
    if ad < 0.147:
        return "negligível"
    if ad < 0.330:
        return "pequeno"
    if ad < 0.474:
        return "médio"
    return "grande"


def perm_mwu(a: np.ndarray, b: np.ndarray,
             n_perm: int, rng: np.random.Generator) -> float:
    """Two-sided permutation test using Mann-Whitney U statistic."""
    obs_u, _ = stats.mannwhitneyu(a, b, alternative="two-sided")
    combined = np.concatenate([a, b])
    na = len(a)
    nb = len(b)
    center = na * nb / 2
    obs = abs(obs_u - center)
    count = sum(
        1 for _ in range(n_perm)
        if abs(
            stats.mannwhitneyu(
                (perm := rng.permutation(combined))[:na],
                perm[na:],
                alternative="two-sided",
            )[0]
            - center
        )
        >= obs
    )
    return count / n_perm


def _to_bool(value) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "sim"}:
        return True
    if text in {"false", "0", "no", "nao", "não"}:
        return False
    return None


def main() -> None:
    print("\n=== STATS ===")
    rng = np.random.default_rng(RANDOM_SEED)

    # ── load corpus ───────────────────────────────────────────────────────
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)
    df["alignment_score"] = pd.to_numeric(df["alignment_score"], errors="coerce")
    df["in_statistical_test"] = df["in_statistical_test"].apply(_to_bool)
    corpus_df = df[df["in_statistical_test"] == True].copy()
    corpus    = corpus_df["alignment_score"].dropna().values
    print(f"\n  Corpus (in_stat_test=True, alignment_score present): n={len(corpus)}")

    # ── load baseline ─────────────────────────────────────────────────────
    if BASELINE_CSV.exists() and BASELINE_CSV.stat().st_size > 0:
        bdf      = pd.read_csv(BASELINE_CSV)
        baseline = bdf["alignment_score"].dropna().values
        print(f"  Baseline:                                           n={len(baseline)}")
    else:
        baseline = np.array([])
        print("  [WARN] baseline.csv not found — H1 tests skipped")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("H1 — PROXY: corpus alignment > baseline (random SE articles)")
    print("═" * 65)

    if len(corpus) < 3 or len(baseline) < 3:
        print("  [SKIP] insufficient data")
    else:
        c_mean, c_med = corpus.mean(),   float(np.median(corpus))
        b_mean, b_med = baseline.mean(), float(np.median(baseline))
        print(f"\n  Corpus   n={len(corpus):3d}  mean={c_mean:.4f}  median={c_med:.4f}  SD={corpus.std():.4f}")
        print(f"  Baseline n={len(baseline):3d}  mean={b_mean:.4f}  median={b_med:.4f}  SD={baseline.std():.4f}")

        u_stat, mwu_p = stats.mannwhitneyu(corpus, baseline, alternative="greater")
        print(f"\n  Mann-Whitney U = {u_stat:.1f},  p = {mwu_p:.5f}  (H1: corpus > baseline, one-sided)")

        cd = cliffs_delta(corpus, baseline)
        print(f"  Cliff's delta  = {cd:+.4f}  ({interpret_cliff(cd)})")

        print(f"\n  Permutation test ({N_PERMUTATIONS:,} resamples, two-sided) ...")
        perm_p = perm_mwu(corpus, baseline, N_PERMUTATIONS, rng)
        print(f"  Permutation p  = {perm_p:.5f}")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("H2 — COHORT COMPARISON: alignment_score across turmas")
    print("═" * 65)

    if not GROUP_COLUMN or GROUP_COLUMN not in corpus_df.columns:
        print(f"  [SKIP H2] group_column='{GROUP_COLUMN}' not configured or absent in data")
        groups: dict[str, np.ndarray] = {}
    else:
        groups = {}
        for name, grp in corpus_df.groupby(GROUP_COLUMN)["alignment_score"]:
            arr = grp.dropna().values
            if len(arr) >= 3:
                groups[name] = arr

        print(f"\n  Groups with ≥3 articles: {list(groups.keys())}")
        for name, arr in groups.items():
            print(f"    {name}: n={len(arr)}, mean={arr.mean():.4f}, "
                  f"median={float(np.median(arr)):.4f}, SD={arr.std():.4f}")

        if len(groups) < 2:
            print("  [SKIP] fewer than 2 groups available")
        else:
            kw_stat, kw_p = stats.kruskal(*groups.values())
            print(f"\n  Kruskal-Wallis H = {kw_stat:.4f},  p = {kw_p:.5f}")

            if len(groups) >= 3:
                long = pd.concat(
                    [pd.DataFrame({"alignment_score": arr, GROUP_COLUMN: name})
                     for name, arr in groups.items()],
                    ignore_index=True,
                )
                dunn = sp.posthoc_dunn(
                    long, val_col="alignment_score",
                    group_col=GROUP_COLUMN, p_adjust="fdr_bh",
                )
                print("\n  Dunn post-hoc (BH-corrected p-values):")
                print(dunn.round(4).to_string())

            print("\n  Cliff's delta (pairwise):")
            names_list = list(groups.keys())
            for i in range(len(names_list)):
                for j in range(i + 1, len(names_list)):
                    cd = cliffs_delta(groups[names_list[i]], groups[names_list[j]])
                    print(f"    {names_list[i]} vs {names_list[j]}: δ={cd:+.4f} ({interpret_cliff(cd)})")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("H3 — VENUE TYPE DISTRIBUTION across cohorts (χ²)")
    print("═" * 65)

    if not GROUP_COLUMN or GROUP_COLUMN not in corpus_df.columns:
        print(f"  [SKIP H3] group_column='{GROUP_COLUMN}' not configured or absent in data")
    else:
        df_test = corpus_df.copy()
        df_test["venue_type_clean"] = df_test["venue_type"].fillna("unknown")
        ct = pd.crosstab(df_test[GROUP_COLUMN], df_test["venue_type_clean"])
        print(f"\n  Contingency table ({GROUP_COLUMN} × venue_type):")
        print(ct.to_string())

        if ct.shape[0] >= 2 and ct.shape[1] >= 2:
            chi2, chi2_p, dof, _ = stats.chi2_contingency(ct)
            n_total = ct.values.sum()
            cramers_v = np.sqrt(chi2 / (n_total * (min(ct.shape) - 1)))
            print(f"\n  χ² = {chi2:.4f},  dof = {dof},  p = {chi2_p:.5f}")
            print(f"  Cramér's V = {cramers_v:.4f}  ({interpret_cliff(cramers_v)})")
        else:
            print("  [SKIP] insufficient categories")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "═" * 65)
    print("CHECKPOINT — STATS DONE")
    print("Aguardando OK para prosseguir para viz.py")
    print("═" * 65)


if __name__ == "__main__":
    main()
