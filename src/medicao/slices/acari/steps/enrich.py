"""
src/enrich.py  –  Pipeline Step 2: Enrich via OpenAlex + Crossref

Strategy
--------
  1. OpenAlex by DOI   (if doi column non-empty)
  2. OpenAlex by title search (best match above similarity threshold)
  3. Crossref by title search (fallback when OpenAlex finds nothing)
  4. If all fail → mark enrichment_source=failed, leave metrics NA

Rules (from DESIGN.md)
-----------------------
  * NEVER invent data; NA ≠ 0.
  * Venue_type already set in corpus_seed (book/report/magazine/thesis)
    takes precedence; we still fetch citations for characterization.
  * Add in_statistical_test column (True/False) based on final venue_type.
  * Add enrichment_source column for audit.

Output:  data/enriched.csv
"""

from __future__ import annotations

import re
import time
import warnings
from pathlib import Path

import pandas as pd
import requests
import urllib3
from rapidfuzz import fuzz
from tqdm import tqdm

# SSL cert verification fails on some Windows setups; safe to disable for a
# local research pipeline that only reads public academic APIs (read-only).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_SSL_VERIFY = False

from .config import (
    SEED_CSV, ENRICHED_CSV, LOGS,
    EXCLUDED_VENUE_TYPES, RANDOM_SEED,
)

# ── API config ────────────────────────────────────────────────────────────────
_EMAIL        = "l31azevedo@gmail.com"
_OA_BASE      = "https://api.openalex.org"
_CR_BASE      = "https://api.crossref.org"
_HEADERS      = {"User-Agent": f"corpus-study-metricas/1.0 mailto:{_EMAIL}"}
_SLEEP        = 0.15        # seconds between requests (polite pool)
_TIMEOUT      = 20          # seconds per request
_TITLE_SIM    = 72          # minimum token_set_ratio to accept a title match
_MAX_RETRY    = 2

# Venue types set manually during ingest that must not be overwritten
_MANUAL_VENUE_TYPES = {"book", "report", "magazine", "thesis", "chapter"}

# LNCS / CCIS series are conference proceedings despite work_type='book-chapter'
_PROCEEDINGS_SERIES = {
    "lecture notes in computer science",
    "communications in computer and information science",
    "lecture notes in business information processing",
    "ifip advances in information and communication technology",
    "advances in intelligent systems and computing",
}

# Maximum acceptable year delta when csv year is known (reject matches outside).
# 8 years catches clear mismatches (e.g. 2023 vs 2013) while allowing preprint
# vs published differences and conference year variations.
_MAX_YEAR_DELTA = 8


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None, retry: int = 0) -> dict | None:
    """GET JSON from url. Returns None on any failure."""
    try:
        r = requests.get(
            url, params=params, headers=_HEADERS,
            timeout=_TIMEOUT, verify=_SSL_VERIFY,
        )
        if r.status_code == 429 and retry < _MAX_RETRY:
            time.sleep(5 * (retry + 1))
            return _get(url, params, retry + 1)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _sleep():
    time.sleep(_SLEEP)


# ── Abstract reconstruction ───────────────────────────────────────────────────

def _reconstruct_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos: dict[int, str] = {}
    for word, positions in inv.items():
        for p in positions:
            pos[p] = word
    return " ".join(pos[k] for k in sorted(pos))


# ── Title similarity check ────────────────────────────────────────────────────

def _title_ok(csv_title: str, api_title: str | None) -> bool:
    if not api_title:
        return False
    return fuzz.token_set_ratio(csv_title.lower(), api_title.lower()) >= _TITLE_SIM


# ── Venue-type classification ─────────────────────────────────────────────────

def _classify_venue_type(work_type: str, source_type: str, existing: str,
                          venue_name: str = "") -> str:
    """Derive a canonical venue_type.  Existing manual types always win."""
    if existing and existing.lower() in _MANUAL_VENUE_TYPES:
        return existing.lower()
    wt = (work_type or "").lower()
    st = (source_type or "").lower()
    vn = (venue_name or "").lower()

    # LNCS / CCIS: conference proceedings even though work_type='book-chapter'
    if wt == "book-chapter" and any(s in vn for s in _PROCEEDINGS_SERIES):
        return "conference"

    if wt in ("book", "book-chapter"):
        return "book"
    if wt in ("report", "standard", "editorial"):
        return "report"
    if "journal" in st:
        return "journal"
    if "conference" in st or "proceedings" in st:
        return "conference"
    if "repository" in st:
        return "preprint"
    if "magazine" in st:
        return "magazine"
    if wt == "article":
        return "journal"          # safe default for articles
    if wt == "preprint":
        return "preprint"
    return "other"


# ── OpenAlex fetchers ─────────────────────────────────────────────────────────

def _oa_by_doi(doi: str) -> dict | None:
    doi = doi.strip().lstrip("https://doi.org/").lstrip("http://doi.org/")
    url = f"{_OA_BASE}/works/doi:{doi}"
    data = _get(url, params={"mailto": _EMAIL})
    _sleep()
    return data


def _oa_by_title(title: str, year_csv: int | None = None) -> dict | None:
    data = _get(
        f"{_OA_BASE}/works",
        params={"filter": f"title.search:{title}", "per-page": "5",
                "mailto": _EMAIL},
    )
    _sleep()
    if not data or not data.get("results"):
        return None
    for candidate in data["results"]:
        if not _title_ok(title, candidate.get("title")):
            continue
        if year_csv:
            api_year = candidate.get("publication_year")
            if api_year and abs(int(api_year) - year_csv) > _MAX_YEAR_DELTA:
                continue        # year too far off — reject
        return candidate
    return None


def _oa_source_stats(source_id: str) -> dict:
    """Fetch source h_index and 2yr_mean_citedness."""
    data = _get(f"{_OA_BASE}/sources/{source_id}", params={"mailto": _EMAIL})
    _sleep()
    if not data:
        return {}
    ss = data.get("summary_stats", {})
    return {
        "venue_h_index":          ss.get("h_index"),
        "venue_2yr_mean_citedness": ss.get("2yr_mean_citedness"),
        "venue_works_count":      ss.get("works_count"),
    }


# ── Crossref fallback ─────────────────────────────────────────────────────────

def _crossref_by_title(title: str, year_csv: int | None = None) -> dict | None:
    data = _get(
        f"{_CR_BASE}/works",
        params={"query.title": title, "rows": "5",
                "mailto": _EMAIL,
                "select": "DOI,title,published,container-title,is-referenced-by-count,type"},
    )
    _sleep()
    if not data:
        return None
    items = data.get("message", {}).get("items", [])
    for item in items:
        api_title = " ".join(item.get("title", []))
        if not _title_ok(title, api_title):
            continue
        if year_csv:
            pub = item.get("published", {}).get("date-parts", [[None]])[0]
            api_year = pub[0] if pub else None
            if api_year and abs(int(api_year) - year_csv) > _MAX_YEAR_DELTA:
                continue        # year too far off — reject (e.g. USP thesis 2013 ≠ 2023)
        return item
    return None


# ── Field extraction ─────────────────────────────────────────────────────────

def _extract_oa(work: dict, existing_venue_type: str) -> dict:
    """Pull relevant fields from an OpenAlex work object."""
    loc    = work.get("primary_location") or {}
    source = loc.get("source") or {}
    refs   = work.get("referenced_works") or []

    work_type   = work.get("type", "")
    source_type = source.get("type", "")
    venue_name  = source.get("display_name", "")
    venue_type  = _classify_venue_type(work_type, source_type, existing_venue_type,
                                       venue_name)

    # Top concepts (up to 3)
    concepts = [
        c["display_name"]
        for c in sorted(work.get("concepts", []), key=lambda x: -x.get("score", 0))[:3]
    ]
    # Top topic
    topics = work.get("topics", [])
    top_topic = topics[0]["display_name"] if topics else ""

    source_id = source.get("id", "").split("/")[-1] if source.get("id") else ""

    return {
        "openalex_id":   work.get("id", "").split("/")[-1],
        "doi_api":       (work.get("doi") or "").lstrip("https://doi.org/"),
        "title_api":     work.get("title", ""),
        "year_api":      work.get("publication_year"),
        "citations":     work.get("cited_by_count"),
        "n_references":  len(refs),
        "venue":         source.get("display_name", ""),
        "venue_id":      source_id,
        "venue_type":    venue_type,
        "venue_issn":    source.get("issn_l", ""),
        "abstract":      _reconstruct_abstract(work.get("abstract_inverted_index")),
        "concepts":      "; ".join(concepts),
        "top_topic":     top_topic,
        "open_access":   (work.get("open_access") or {}).get("is_oa"),
        "language":      work.get("language", ""),
        "enrichment_source": "openalex",
    }


def _extract_crossref(item: dict, existing_venue_type: str) -> dict:
    """Pull fields from a Crossref works item."""
    work_type  = item.get("type", "")
    container  = " ".join(item.get("container-title", []))
    pub        = item.get("published", {}).get("date-parts", [[None]])[0]
    year       = pub[0] if pub else None
    doi        = item.get("DOI", "")

    # Crude venue-type from Crossref type
    cr_to_vt = {
        "journal-article": "journal",
        "proceedings-article": "conference",
        "book": "book",
        "book-chapter": "book",
        "report": "report",
        "monograph": "book",
        "posted-content": "preprint",
    }
    vt_guess  = cr_to_vt.get(work_type, "other")
    venue_type = _classify_venue_type(work_type, "", existing_venue_type) \
                 if existing_venue_type.lower() in _MANUAL_VENUE_TYPES \
                 else (existing_venue_type or vt_guess)

    return {
        "openalex_id":   "",
        "doi_api":       doi,
        "title_api":     " ".join(item.get("title", [])),
        "year_api":      year,
        "citations":     item.get("is-referenced-by-count"),
        "n_references":  None,
        "venue":         container,
        "venue_id":      "",
        "venue_type":    venue_type,
        "venue_issn":    "",
        "abstract":      "",
        "concepts":      "",
        "top_topic":     "",
        "open_access":   None,
        "language":      "",
        "enrichment_source": "crossref",
    }


def _empty_enrichment(existing_venue_type: str) -> dict:
    return {
        "openalex_id":   "",
        "doi_api":       "",
        "title_api":     "",
        "year_api":      None,
        "citations":     None,
        "n_references":  None,
        "venue":         "",
        "venue_id":      "",
        "venue_type":    existing_venue_type or "",
        "venue_issn":    "",
        "abstract":      "",
        "concepts":      "",
        "top_topic":     "",
        "open_access":   None,
        "language":      "",
        "enrichment_source": "failed",
    }


# ── Main enrichment loop ──────────────────────────────────────────────────────

def enrich_row(row: pd.Series) -> dict:
    doi_csv = str(row.get("doi", "")).strip() if pd.notna(row.get("doi")) else ""
    title   = str(row["title"]).strip()
    existing_vt = str(row.get("venue_type", "")) if pd.notna(row.get("venue_type")) else ""

    # Parse year_csv for validation
    year_csv: int | None = None
    raw_year = row.get("year")
    if pd.notna(raw_year):
        try:
            year_csv = int(float(str(raw_year)))
        except (ValueError, TypeError):
            pass

    enriched = None

    # 1. OpenAlex by DOI
    if doi_csv:
        work = _oa_by_doi(doi_csv)
        if work and "id" in work:
            enriched = _extract_oa(work, existing_vt)
            enriched["enrichment_source"] = "openalex_doi"

    # 2. OpenAlex by title (with year validation when year_csv known)
    if enriched is None:
        work = _oa_by_title(title, year_csv)
        if work:
            enriched = _extract_oa(work, existing_vt)
            enriched["enrichment_source"] = "openalex_title"

    # 3. Crossref fallback (with year validation)
    if enriched is None:
        item = _crossref_by_title(title, year_csv)
        if item:
            enriched = _extract_crossref(item, existing_vt)

    # 4. All failed
    if enriched is None:
        enriched = _empty_enrichment(existing_vt)

    # Preserve manual venue_type (highest priority)
    if existing_vt.lower() in _MANUAL_VENUE_TYPES:
        enriched["venue_type"] = existing_vt.lower()

    return enriched


# ── Source stats (second pass for OpenAlex rows) ──────────────────────────────

def _fetch_source_stats(df: pd.DataFrame) -> pd.DataFrame:
    """For rows with a venue_id, fetch h_index and 2yr_mean_citedness."""
    cache: dict[str, dict] = {}
    h_idx, mean_cite, works_cnt = [], [], []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="  source stats", leave=False):
        vid = str(row.get("venue_id", "")) if pd.notna(row.get("venue_id")) else ""
        if not vid:
            h_idx.append(None); mean_cite.append(None); works_cnt.append(None)
            continue
        if vid not in cache:
            cache[vid] = _oa_source_stats(vid)
        s = cache[vid]
        h_idx.append(s.get("venue_h_index"))
        mean_cite.append(s.get("venue_2yr_mean_citedness"))
        works_cnt.append(s.get("venue_works_count"))

    df = df.copy()
    df["venue_h_index"]           = h_idx
    df["venue_2yr_mean_citedness"] = mean_cite
    df["venue_works_count"]        = works_cnt
    return df


# ── in_statistical_test column ────────────────────────────────────────────────

def _in_stat_test(vt: str) -> bool | None:
    if not vt or vt == "nan":
        return None
    return vt.lower() not in EXCLUDED_VENUE_TYPES


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n=== ENRICH ===")

    df = pd.read_csv(SEED_CSV, dtype=str, keep_default_na=False)
    df = df.replace("", pd.NA)
    print(f"  Loaded {len(df)} articles from corpus_seed.csv")

    # ── first pass: OpenAlex / Crossref ──────────────────────────────────────
    results: list[dict] = []
    print(f"\n  Fetching metadata (OpenAlex primary, Crossref fallback) ...")

    for _, row in tqdm(df.iterrows(), total=len(df), desc="  enriching"):
        results.append(enrich_row(row))

    enriched_cols = pd.DataFrame(results)

    # Merge into df
    for col in enriched_cols.columns:
        df[col] = enriched_cols[col].values

    # ── second pass: source stats ─────────────────────────────────────────────
    print("\n  Fetching source stats (h-index, mean citedness) ...")
    df = _fetch_source_stats(df)

    # ── final in_statistical_test ────────────────────────────────────────────
    df["in_statistical_test"] = df["venue_type"].apply(
        lambda vt: _in_stat_test(str(vt) if pd.notna(vt) else "")
    )

    # ── save ──────────────────────────────────────────────────────────────────
    df.to_csv(ENRICHED_CSV, index=False)
    print(f"\n  [ok] enriched.csv saved ({len(df)} rows, {len(df.columns)} cols)")

    # ── CHECKPOINT REPORT ─────────────────────────────────────────────────────
    _checkpoint(df)


def _checkpoint(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("CHECKPOINT: ENRICH RESULTS")
    print("=" * 60)

    n = len(df)

    def _resolved(col: str) -> int:
        return int(df[col].notna().sum()
                   - df[col].astype(str).isin(["", "nan", "None", "NA"]).sum())

    cite_resolved = _resolved("citations")
    venue_resolved = _resolved("venue")
    abs_resolved   = _resolved("abstract")

    # Enrichment source breakdown
    esrc = df["enrichment_source"].value_counts().to_dict()

    print(f"\nTotal articles: {n}")
    print(f"\nEnrichment source:")
    for src, cnt in sorted(esrc.items(), key=lambda x: -x[1]):
        print(f"  {src:<22} {cnt:>3}  ({100*cnt/n:.0f}%)")

    print(f"\nResolution:")
    print(f"  Citations resolved:    {cite_resolved}/{n} ({100*cite_resolved/n:.0f}%)")
    print(f"  Venue resolved:        {venue_resolved}/{n} ({100*venue_resolved/n:.0f}%)")
    print(f"  Abstract available:    {abs_resolved}/{n}  ({100*abs_resolved/n:.0f}%)")

    # venue_type distribution
    print(f"\nVenue types:")
    vt_counts = df["venue_type"].value_counts(dropna=False).to_dict()
    for vt, cnt in sorted(vt_counts.items(), key=lambda x: -x[1]):
        in_test = str(vt).lower() not in EXCLUDED_VENUE_TYPES if pd.notna(vt) else "?"
        print(f"  {str(vt):<18} {cnt:>3}  in_stat_test={in_test}")

    # Articles with NA citations
    no_cite = df[df["citations"].isna()][["cohort", "presenter", "title", "enrichment_source", "venue_type"]]
    if not no_cite.empty:
        print(f"\nNA citations ({len(no_cite)} articles):")
        for _, r in no_cite.iterrows():
            print(f"  [{r['cohort']}] {r['presenter']}: {str(r['title'])[:50]}"
                  f"  [src={r['enrichment_source']} vt={r['venue_type']}]")

    # Articles with NA venue
    no_venue = df[df["venue"].isna() | df["venue"].astype(str).isin(["", "nan", "None"])][
        ["cohort", "presenter", "title", "enrichment_source"]]
    if not no_venue.empty:
        print(f"\nNA venue ({len(no_venue)} articles):")
        for _, r in no_venue.iterrows():
            print(f"  [{r['cohort']}] {r['presenter']}: {str(r['title'])[:50]}")

    print("=" * 60)


if __name__ == "__main__":
    main()
