"""
src/baseline.py – Pipeline Step 5: Random Baseline

Samples BASELINE_N=200 random software-engineering articles from OpenAlex
(filtered: has_abstract=true, concept=Software Engineering) and computes
alignment_score against course_text.txt using the same model as textsim.py.

The baseline distribution serves as H0 for the proxy hypothesis test in stats.py.
"""
from __future__ import annotations

import os
import time

os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFICATION", "1")
import httpx as _httpx
_orig_httpx_init = _httpx.Client.__init__
def _httpx_no_ssl(self, *a, **kw):
    kw.setdefault("verify", False)
    _orig_httpx_init(self, *a, **kw)
_httpx.Client.__init__ = _httpx_no_ssl

import numpy as np
import pandas as pd
import requests
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .config import (
    BASELINE_CSV, COURSE_TXT, EMBEDDING_MODEL,
    BASELINE_N, RANDOM_SEED, BASELINE_CONCEPT_ID,
)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_SSL_VERIFY = False

_OA_BASE     = "https://api.openalex.org"
_MAILTO      = "l31azevedo@gmail.com"
_CHUNK_WORDS = 200


def _chunk_text(text: str, n: int = _CHUNK_WORDS) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + n]) for i in range(0, len(words), n)]


def _reconstruct_abstract(inv_idx: dict | None) -> str:
    if not inv_idx or not isinstance(inv_idx, dict):
        return ""
    pos_word: dict[int, str] = {}
    for word, positions in inv_idx.items():
        for pos in positions:
            pos_word[pos] = word
    return " ".join(pos_word[p] for p in sorted(pos_word))


def _fetch_one_page(seed: int, per_page: int = 50) -> list[dict]:
    """Fetch one page of random articles using a given seed."""
    try:
        r = requests.get(
            f"{_OA_BASE}/works",
            params={
                "filter": f"concepts.id:{BASELINE_CONCEPT_ID},has_abstract:true",
                "sample": per_page,
                "seed": seed,
                "select": "id,title,abstract_inverted_index,publication_year,cited_by_count",
                "mailto": _MAILTO,
                "per-page": per_page,
            },
            timeout=30,
            verify=_SSL_VERIFY,
        )
        r.raise_for_status()
        items = r.json().get("results", [])
    except Exception as e:
        print(f"  [WARN] OpenAlex request (seed={seed}) failed: {str(e)[:80]}")
        return []

    out = []
    for item in items:
        abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))
        if abstract:
            out.append({
                "openalex_id": item.get("id", ""),
                "title":       item.get("title", ""),
                "abstract":    abstract,
                "year":        item.get("publication_year"),
                "citations":   item.get("cited_by_count", 0),
            })
    return out


def _fetch_baseline(n: int, seed: int) -> list[dict]:
    """Fetch n unique random SE articles by making multiple seeded page requests."""
    seen: set[str] = set()
    collected: list[dict] = []
    page_seed = seed
    per_page = 50
    needed_pages = (n // per_page) + 4  # extra buffer for deduplication

    for _ in range(needed_pages):
        if len(collected) >= n:
            break
        items = _fetch_one_page(page_seed, per_page)
        for item in items:
            oa_id = item["openalex_id"]
            if oa_id not in seen:
                seen.add(oa_id)
                collected.append(item)
        page_seed += 1
        time.sleep(0.15)

    return collected[:n]


def main() -> None:
    print("\n=== BASELINE ===")

    # ── load model ────────────────────────────────────────────────────────
    print(f"\n[1] Loading model: {EMBEDDING_MODEL} ...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("  [ok] model loaded")

    # ── course embedding ──────────────────────────────────────────────────
    print("\n[2] Embedding course text ...")
    course_text = COURSE_TXT.read_text(encoding="utf-8")
    chunks = _chunk_text(course_text)
    chunk_embs = model.encode(chunks, show_progress_bar=False, normalize_embeddings=True)
    course_emb = chunk_embs.mean(axis=0)
    course_emb = course_emb / np.linalg.norm(course_emb)
    print("  [ok] course_emb ready")

    # ── fetch articles ────────────────────────────────────────────────────
    print(f"\n[3] Fetching {BASELINE_N} random SE articles from OpenAlex ...")
    articles = _fetch_baseline(BASELINE_N, RANDOM_SEED)
    print(f"  [ok] {len(articles)} articles fetched with abstracts")

    if not articles:
        print("  [WARN] No articles fetched. Creating empty baseline.csv.")
        pd.DataFrame(columns=[
            "openalex_id", "title", "abstract", "year", "citations", "alignment_score"
        ]).to_csv(BASELINE_CSV, index=False)
        return

    # ── compute alignment_score ───────────────────────────────────────────
    print(f"\n[4] Computing alignment scores ({len(articles)} articles) ...")
    texts = [a["abstract"][:1500] for a in articles]
    embs  = model.encode(texts, show_progress_bar=True, normalize_embeddings=True, batch_size=32)
    sims  = np.maximum(cosine_similarity(embs, [course_emb]).flatten(), 0.0)

    for i, a in enumerate(articles):
        a["alignment_score"] = float(sims[i])

    df = pd.DataFrame(articles)
    df.to_csv(BASELINE_CSV, index=False)
    print(f"  [ok] baseline.csv saved ({len(df)} rows)")

    # ── summary ──────────────────────────────────────────────────────────
    print(f"\n── Baseline Summary ─────────────────────────────────")
    print(f"  n = {len(df)}")
    print(f"  alignment_score range:  [{sims.min():.4f}, {sims.max():.4f}]")
    print(f"  mean={sims.mean():.4f}   median={float(np.median(sims)):.4f}   SD={sims.std():.4f}")
    print("─" * 55)


if __name__ == "__main__":
    main()
