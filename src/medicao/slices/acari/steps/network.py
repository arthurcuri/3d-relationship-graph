"""
src/network.py – Pipeline Step 6: Bibliographic Coupling Network

1. Fetches referenced_works from OpenAlex for each article (using openalex_id).
2. Builds bibliographic coupling graph: edge weight = number of shared references.
3. Computes PageRank centrality (normalized to [0,1]).
4. Detects communities via Louvain.

Adds to enriched.csv: referenced_works (JSON), pagerank_centrality, community_id.
Articles without openalex_id or with empty reference lists are isolated nodes.
"""
from __future__ import annotations

import json
import time

import networkx as nx
import numpy as np
import pandas as pd
import requests

from .config import ENRICHED_CSV, RANDOM_SEED

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_SSL_VERIFY = False

_OA_BASE = "https://api.openalex.org"
_MAILTO  = "l31azevedo@gmail.com"

try:
    import community as community_louvain
    _HAS_LOUVAIN = True
except ImportError:
    _HAS_LOUVAIN = False


def _fetch_refs(openalex_id: str) -> list[str]:
    """Return list of referenced OpenAlex work IDs for a given work ID."""
    if not openalex_id or pd.isna(openalex_id):
        return []
    work_id = str(openalex_id).split("/")[-1]  # strip URL prefix if present
    try:
        r = requests.get(
            f"{_OA_BASE}/works/{work_id}",
            params={
                "select": "referenced_works",
                "mailto": _MAILTO,
            },
            timeout=20,
            verify=_SSL_VERIFY,
        )
        r.raise_for_status()
        data = r.json()
        refs = data.get("referenced_works", [])
        return [str(x) for x in refs] if isinstance(refs, list) else []
    except Exception:
        return []


def main() -> None:
    print("\n=== NETWORK ===")
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)
    n = len(df)

    # ── fetch referenced_works ────────────────────────────────────────────
    # Only fetch if column not already populated (allows re-run idempotency)
    has_refs = "referenced_works" in df.columns and df["referenced_works"].notna().sum() > 0

    if has_refs:
        print(f"\n[1] referenced_works already in enriched.csv — skipping API fetch")
        ref_lists = [
            set(json.loads(v)) if pd.notna(v) and str(v).startswith("[") else set()
            for v in df["referenced_works"]
        ]
    else:
        print(f"\n[1] Fetching referenced_works for {n} articles from OpenAlex ...")
        ref_lists: list[set[str]] = []
        raw_refs:  list[str]      = []

        for i, (_, row) in enumerate(df.iterrows()):
            oa_id = row.get("openalex_id")
            if pd.notna(oa_id) and str(oa_id).strip():
                refs = _fetch_refs(str(oa_id))
                time.sleep(0.08)  # polite pool
            else:
                refs = []

            ref_lists.append(set(refs))
            raw_refs.append(json.dumps(refs))

            if (i + 1) % 10 == 0:
                n_with = sum(1 for r in ref_lists if r)
                print(f"    {i+1}/{n} — {n_with} with references")

        df["referenced_works"] = raw_refs
        df.to_csv(ENRICHED_CSV, index=False)  # save early so re-runs skip fetch
        n_with = sum(1 for r in ref_lists if r)
        print(f"  [ok] {n_with}/{n} articles have referenced_works")

    # ── bibliographic coupling graph ──────────────────────────────────────
    print(f"\n[2] Building bibliographic coupling graph ({n} nodes) ...")
    G = nx.Graph()
    G.add_nodes_from(range(n))

    n_edges = 0
    for i in range(n):
        for j in range(i + 1, n):
            shared = len(ref_lists[i] & ref_lists[j])
            if shared > 0:
                G.add_edge(i, j, weight=shared)
                n_edges += 1

    n_comp = nx.number_connected_components(G)
    print(f"  [ok] {n_edges} edges, {n_comp} connected components")

    # ── PageRank ──────────────────────────────────────────────────────────
    print("\n[3] Computing PageRank ...")
    pr = nx.pagerank(G, weight="weight")
    pr_vals = pd.Series([pr[i] for i in range(n)])
    vmin, vmax = pr_vals.min(), pr_vals.max()
    pr_norm = (pr_vals - vmin) / (vmax - vmin) if vmax > vmin else pr_vals
    print(f"  [ok] PageRank ∈ [{pr_norm.min():.4f}, {pr_norm.max():.4f}]")

    # ── Louvain community detection ───────────────────────────────────────
    community_ids: list = [pd.NA] * n
    if _HAS_LOUVAIN:
        print("\n[4] Louvain community detection ...")
        partition = community_louvain.best_partition(G, random_state=RANDOM_SEED)
        for node, comm in partition.items():
            community_ids[node] = comm
        n_comm = len(set(partition.values()))
        print(f"  [ok] {n_comm} communities")
    else:
        print("\n[4] python-louvain not installed — community_id = NA")

    # ── write back ────────────────────────────────────────────────────────
    df["pagerank_centrality"] = pr_norm.values
    df["community_id"]        = community_ids
    df.to_csv(ENRICHED_CSV, index=False)
    print("  [ok] enriched.csv updated (referenced_works, pagerank_centrality, community_id)")

    # ── summary ──────────────────────────────────────────────────────────
    print(f"\n── Network Summary ─────────────────────────────────")
    print(f"  Nodes:  {n}")
    print(f"  Edges:  {n_edges}  (bib coupling, shared refs ≥1)")
    print(f"  Components: {n_comp}")
    pr_s = df["pagerank_centrality"].astype(float)
    label_col = next(
        (c for c in ("presenter", "article_authors", "title") if c in df.columns), None
    )
    cols = [c for c in (label_col, "pagerank_centrality") if c]
    top5 = df.nlargest(5, "pagerank_centrality")[cols]
    print(f"  Top-5 PageRank:\n{top5.to_string(index=False)}")
    print("─" * 55)


if __name__ == "__main__":
    main()
