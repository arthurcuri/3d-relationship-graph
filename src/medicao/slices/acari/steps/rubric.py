"""
src/rubric.py – Pipeline Step 7: Rubric Score

Loads rubric.csv (user-filled) or falls back to rubric_template.csv (all NA).
Computes rubric_score ∈ [0,1] for each article from 6 rubric dimensions.

Dimensions:
  replicavel          0|1|2          → /2
  pratico_teorico     pratico|teorico|misto  → 1.0|0.5|0.75
  nivel_aluno         1–5            → /5
  agregou             1–5            → /5
  relacao_disciplina  direta|indireta|nenhuma → 1.0|0.5|0.0
  alinhado_plano      0|1|2          → /2

rubric_score = mean of available dimensions, or NA if all dimensions are NA.
Running with an unfilled template (all NA) is expected and safe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ENRICHED_CSV, RUBRIC_CSV, RUBRIC_TMPL

_PRATICO_MAP = {"pratico": 1.0, "teorico": 0.5, "misto": 0.75}
_RELACAO_MAP = {"direta": 1.0, "indireta": 0.5, "nenhuma": 0.0}


def _compute_score(row: pd.Series) -> float:
    signals: list[float] = []

    v = row.get("replicavel")
    if pd.notna(v):
        try:
            signals.append(float(v) / 2.0)
        except (ValueError, TypeError):
            pass

    v = row.get("pratico_teorico")
    if pd.notna(v):
        m = _PRATICO_MAP.get(str(v).lower().strip())
        if m is not None:
            signals.append(m)

    v = row.get("nivel_aluno")
    if pd.notna(v):
        try:
            signals.append(float(v) / 5.0)
        except (ValueError, TypeError):
            pass

    v = row.get("agregou")
    if pd.notna(v):
        try:
            signals.append(float(v) / 5.0)
        except (ValueError, TypeError):
            pass

    v = row.get("relacao_disciplina")
    if pd.notna(v):
        m = _RELACAO_MAP.get(str(v).lower().strip())
        if m is not None:
            signals.append(m)

    v = row.get("alinhado_plano")
    if pd.notna(v):
        try:
            signals.append(float(v) / 2.0)
        except (ValueError, TypeError):
            pass

    return float(np.mean(signals)) if signals else float("nan")


def main() -> None:
    print("\n=== RUBRIC ===")

    rubric_path = RUBRIC_CSV if RUBRIC_CSV.exists() else RUBRIC_TMPL
    print(f"\n[1] Loading {rubric_path.name} ...")
    rubric = pd.read_csv(rubric_path, dtype=str, keep_default_na=False).replace("", pd.NA)

    dims = ["replicavel", "pratico_teorico", "nivel_aluno",
            "agregou", "relacao_disciplina", "alinhado_plano"]
    n_filled = rubric[dims].notna().any(axis=1).sum()
    print(f"  {n_filled}/{len(rubric)} articles with ≥1 rubric dimension filled")

    rubric["rubric_score"] = rubric.apply(_compute_score, axis=1)

    # Merge into enriched.csv by presenter
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)
    score_map = rubric.set_index("presenter")["rubric_score"].to_dict()
    df["rubric_score"] = pd.to_numeric(
        df["presenter"].map(score_map), errors="coerce"
    )
    df.to_csv(ENRICHED_CSV, index=False)

    n_score = df["rubric_score"].notna().sum()
    print(f"  [ok] rubric_score: {n_score}/{len(df)} resolved")
    if n_score == 0:
        print("  (Expected: fill data/rubric_template.csv to populate rubric_score)")
    print("─" * 55)


if __name__ == "__main__":
    main()
