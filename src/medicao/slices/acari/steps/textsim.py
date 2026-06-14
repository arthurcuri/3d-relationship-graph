"""
src/textsim.py – Pipeline Step 4: Text Similarity / Alignment Score

Computes alignment_score ∈ [0,1] for each corpus article vs the course syllabus.
Model: sentence-transformers/all-MiniLM-L6-v2 (max 256 tokens per segment).

Strategy:
  - Course text is chunked into ~200-word segments, each embedded; mean = course_emb.
  - Each article is embedded from its abstract (preferred) or PDF first-page text.
  - alignment_score = cosine_similarity(article_emb, course_emb), clipped to [0,1].
  - If neither abstract nor PDF is available: alignment_score = NA.
"""
from __future__ import annotations

import os
import re

# Bypass Windows CA-chain gap: must be set before httpx/hf_hub are imported
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFICATION", "1")
import httpx as _httpx
_orig_httpx_init = _httpx.Client.__init__
def _httpx_no_ssl(self, *a, **kw):
    kw.setdefault("verify", False)
    _orig_httpx_init(self, *a, **kw)
_httpx.Client.__init__ = _httpx_no_ssl

import numpy as np
import pandas as pd
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from .config import ENRICHED_CSV, COURSE_TXT, PDFS, EMBEDDING_MODEL

_CHUNK_WORDS      = 200
_MAX_ABSTRACT     = 1500
_MAX_PDF_CHARS    = 2000
_MIN_TEXT_LEN     = 30


def _chunk_text(text: str, n: int = _CHUNK_WORDS) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + n]) for i in range(0, len(words), n)]


def _pdf_text(pdf_name: str, pages: int = 3) -> str:
    if not pdf_name or pd.isna(pdf_name) or str(pdf_name) in ("", "NA"):
        return ""
    try:
        p = PDFS / str(pdf_name)
        if not p.exists():
            return ""
        doc = fitz.open(str(p))
        n = min(pages, len(doc))
        return " ".join(doc[i].get_text() for i in range(n))
    except Exception:
        return ""


def _article_text(row: pd.Series) -> str:
    ab = str(row.get("abstract", "")) if pd.notna(row.get("abstract")) else ""
    if len(ab) >= _MIN_TEXT_LEN:
        return ab[:_MAX_ABSTRACT]
    pdf = str(row.get("pdf_path", "")) if pd.notna(row.get("pdf_path")) else ""
    if pdf and pdf != "NA":
        t = _pdf_text(pdf)
        if len(t) >= _MIN_TEXT_LEN:
            return t[:_MAX_PDF_CHARS]
    return ""


def main() -> None:
    print("\n=== TEXTSIM ===")
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)

    # ── load model ────────────────────────────────────────────────────────
    print(f"\n[1] Loading model: {EMBEDDING_MODEL} ...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("  [ok] model loaded")

    # ── course embedding ──────────────────────────────────────────────────
    print("\n[2] Embedding course text ...")
    course_text = COURSE_TXT.read_text(encoding="utf-8")
    chunks = _chunk_text(course_text, _CHUNK_WORDS)
    print(f"  {len(chunks)} chunks (~{_CHUNK_WORDS} words each)")
    chunk_embs = model.encode(chunks, show_progress_bar=False, normalize_embeddings=True)
    course_emb = chunk_embs.mean(axis=0)
    course_emb = course_emb / np.linalg.norm(course_emb)
    print("  [ok] course_emb ready")

    # ── article embeddings ────────────────────────────────────────────────
    print("\n[3] Embedding articles ...")
    texts = [_article_text(row) for _, row in df.iterrows()]
    n_with   = sum(1 for t in texts if t)
    n_without = len(texts) - n_with
    print(f"  {n_with} articles with text  |  {n_without} without (→ NA)")

    alignment_scores: list = []
    for text in texts:
        if not text:
            alignment_scores.append(pd.NA)
            continue
        emb = model.encode([text], normalize_embeddings=True)[0]
        sim = float(cosine_similarity([emb], [course_emb])[0][0])
        alignment_scores.append(max(0.0, sim))

    df["alignment_score"] = pd.to_numeric(alignment_scores, errors="coerce")
    df.to_csv(ENRICHED_CSV, index=False)

    # ── summary ──────────────────────────────────────────────────────────
    a = df["alignment_score"].dropna().astype(float)
    print(f"\n── TextSim Summary ─────────────────────────────────")
    print(f"  alignment_score resolved: {len(a)}/{len(df)} ({100*len(a)/len(df):.0f}%)")
    print(f"  alignment_score = NA:     {df['alignment_score'].isna().sum()}")
    if len(a) > 0:
        print(f"  Range:  [{a.min():.4f}, {a.max():.4f}]")
        print(f"  Mean:   {a.mean():.4f}   Median: {a.median():.4f}   SD: {a.std():.4f}")
    print("─" * 55)


if __name__ == "__main__":
    main()
