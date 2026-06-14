"""
src/venue.py – Pipeline Step 3: Venue Prestige Score

Prestige signals (highest priority first):
  1. CORE rank    → A*=1.00, A=0.75, B=0.50, C=0.25
  2. SJR quartile → Q1=1.00, Q2=0.75, Q3=0.50, Q4=0.25
  3. OpenAlex venue h-index + 2yr-mean-citedness (percentile-normalized within corpus)

prestige_score = mean of available signals ∈ [0,1], or NA if venue=NA.
NA prestige_score does NOT block the pipeline; index.py averages over present dims.
"""
from __future__ import annotations

import io
import re
import unicodedata

import numpy as np
import pandas as pd
import requests
from rapidfuzz import fuzz
from rapidfuzz import process as rfprocess

from .config import ENRICHED_CSV, VENUE_RANKS

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_SSL_VERIFY = False

_CORE_SCORE = {"A*": 1.00, "A": 0.75, "B": 0.50, "C": 0.25}
_SJR_SCORE  = {"Q1": 1.00, "Q2": 0.75, "Q3": 0.50, "Q4": 0.25}
_VENUE_SIM  = 72  # minimum token_set_ratio for venue name matching


# ── helpers ──────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _fetch_core() -> pd.DataFrame | None:
    url = (
        "https://portal.core.edu.au/conf-ranks/export/"
        "?search=&by=all&source=CORE2023&sort=arank&page=1"
    )
    try:
        r = requests.get(url, timeout=20, verify=_SSL_VERIFY,
                         headers={"User-Agent": "Mozilla/5.0 (research pipeline)"})
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        print(f"  [ok] CORE: {len(df)} entries downloaded")
        return df
    except Exception as e:
        print(f"  [WARN] CORE download failed: {str(e)[:80]}")
        return None


def _fetch_sjr() -> pd.DataFrame | None:
    url = "https://www.scimagojr.com/journalrank.php?out=xls"
    try:
        r = requests.get(url, timeout=30, verify=_SSL_VERIFY,
                         headers={"User-Agent": "Mozilla/5.0 (research pipeline)"})
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), sep=";", decimal=",", dtype=str)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        print(f"  [ok] SJR: {len(df)} entries downloaded")
        return df
    except Exception as e:
        print(f"  [WARN] SJR download failed: {str(e)[:80]}")
        return None


def _build_core_lookup(core_df: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    title_col = next((c for c in core_df.columns if "title" in c), None)
    rank_col  = next((c for c in core_df.columns if c == "rank" or c.endswith("_rank")), None)
    if not title_col or not rank_col:
        print(f"  [WARN] CORE columns not recognised: {list(core_df.columns)[:8]}")
        return lookup
    for _, row in core_df.iterrows():
        if pd.notna(row[title_col]) and pd.notna(row[rank_col]):
            rank = str(row[rank_col]).strip()
            if rank in _CORE_SCORE:
                lookup[_norm(str(row[title_col]))] = rank
    return lookup


def _build_sjr_lookup(sjr_df: pd.DataFrame) -> dict[str, str]:
    lookup: dict[str, str] = {}
    title_col = next((c for c in sjr_df.columns if c == "title" or "journal" in c), None)
    q_col     = next(
        (c for c in sjr_df.columns if "quartile" in c or "sjr_best" in c or "best_quartile" in c),
        None,
    )
    if not title_col or not q_col:
        print(f"  [WARN] SJR columns not recognised: {list(sjr_df.columns)[:8]}")
        return lookup
    for _, row in sjr_df.iterrows():
        if pd.notna(row[title_col]) and pd.notna(row[q_col]):
            q = str(row[q_col]).strip()
            if q in _SJR_SCORE:
                lookup[_norm(str(row[title_col]))] = q
    return lookup


def _fuzzy_match(norm_venue: str, lookup: dict[str, str]) -> str | None:
    if not lookup:
        return None
    best = rfprocess.extractOne(
        norm_venue,
        list(lookup.keys()),
        scorer=fuzz.token_set_ratio,
        score_cutoff=_VENUE_SIM,
    )
    return lookup[best[0]] if best else None


def _oa_prestige(df: pd.DataFrame) -> pd.Series:
    """
    Percentile-rank-based prestige from OpenAlex h-index and 2yr-mean-citedness.
    Returns a Series ∈ [0,1] aligned to df.index (NA where both signals absent).
    """
    h   = pd.to_numeric(df.get("venue_h_index", pd.NA), errors="coerce")
    c2y = pd.to_numeric(df.get("venue_2yr_mean_citedness", pd.NA), errors="coerce")

    h_pct  = h.rank(pct=True, na_option="keep")
    c_pct  = c2y.rank(pct=True, na_option="keep")

    score = pd.Series(index=df.index, dtype=float)
    both   = h_pct.notna() & c_pct.notna()
    only_h = h_pct.notna() & c_pct.isna()
    only_c = c_pct.notna() & h_pct.isna()
    score[both]   = 0.5 * h_pct[both]   + 0.5 * c_pct[both]
    score[only_h] = h_pct[only_h]
    score[only_c] = c_pct[only_c]
    return score


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n=== VENUE ===")
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)

    # ── download rankings ─────────────────────────────────────────────────
    print("\n[1] Downloading CORE conference rankings ...")
    core_df = _fetch_core()

    print("\n[2] Downloading SJR journal rankings ...")
    sjr_df = _fetch_sjr()

    # Save venue_rankings.csv (merged or empty)
    if core_df is not None or sjr_df is not None:
        parts = []
        if core_df is not None:
            parts.append(core_df.assign(source="CORE"))
        if sjr_df is not None:
            parts.append(sjr_df.assign(source="SJR"))
        pd.concat(parts, ignore_index=True).to_csv(VENUE_RANKS, index=False)
        print(f"  [ok] venue_rankings.csv saved")
    else:
        pd.DataFrame(columns=["title", "acronym", "rank", "quartile", "source"]
                     ).to_csv(VENUE_RANKS, index=False)
        print("  [WARN] venue_rankings.csv created empty (downloads blocked)")

    # ── build lookups ─────────────────────────────────────────────────────
    core_lookup = _build_core_lookup(core_df) if core_df is not None else {}
    sjr_lookup  = _build_sjr_lookup(sjr_df)   if sjr_df  is not None else {}
    print(f"  CORE lookup: {len(core_lookup)} ranked venues")
    print(f"  SJR  lookup: {len(sjr_lookup)} ranked journals")

    # ── OpenAlex baseline prestige ────────────────────────────────────────
    oa_score = _oa_prestige(df)

    # ── compute per-article prestige_score ────────────────────────────────
    print("\n[3] Computing prestige_score ...")
    core_ranks:   list = []
    sjr_quarts:   list = []
    final_scores: list = []

    for idx, row in df.iterrows():
        venue = row.get("venue")
        if pd.isna(venue) or str(venue).strip() in ("", "NA"):
            core_ranks.append(pd.NA)
            sjr_quarts.append(pd.NA)
            final_scores.append(pd.NA)
            continue

        nv = _norm(str(venue))
        cr = core_lookup.get(nv) or _fuzzy_match(nv, core_lookup)
        sq = sjr_lookup.get(nv)  or _fuzzy_match(nv, sjr_lookup)

        signals = []
        if cr and cr in _CORE_SCORE:
            signals.append(_CORE_SCORE[cr])
        if sq and sq in _SJR_SCORE:
            signals.append(_SJR_SCORE[sq])
        oa = oa_score.get(idx)
        if pd.notna(oa):
            signals.append(float(oa))

        core_ranks.append(cr if cr else pd.NA)
        sjr_quarts.append(sq if sq else pd.NA)
        final_scores.append(float(np.mean(signals)) if signals else pd.NA)

    df["prestige_score"] = pd.to_numeric(final_scores, errors="coerce")
    df["core_rank"]      = core_ranks
    df["sjr_quartile"]   = sjr_quarts

    df.to_csv(ENRICHED_CSV, index=False)
    print("  [ok] enriched.csv updated (prestige_score, core_rank, sjr_quartile)")

    # ── summary ──────────────────────────────────────────────────────────
    n_score = df["prestige_score"].notna().sum()
    n_core  = pd.Series(core_ranks).notna().sum()
    n_sjr   = pd.Series(sjr_quarts).notna().sum()
    p = df["prestige_score"].dropna().astype(float)
    print(f"\n── Venue Summary ────────────────────────────────────")
    print(f"  prestige_score resolved: {n_score}/{len(df)} ({100*n_score/len(df):.0f}%)")
    print(f"  via CORE rank:           {n_core}")
    print(f"  via SJR quartile:        {n_sjr}")
    print(f"  via OpenAlex only:       {n_score - n_core - n_sjr}")
    if len(p) > 0:
        print(f"  Score range: [{p.min():.3f}, {p.max():.3f}], median={p.median():.3f}")
    print("─" * 55)


if __name__ == "__main__":
    main()
