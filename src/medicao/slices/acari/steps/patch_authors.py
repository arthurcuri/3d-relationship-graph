"""
patch_authors.py – Fetch real article authors from OpenAlex and add
'article_authors' column to enriched.csv.

Format: "LastName, F." for single author; "LastName, F. et al." for 2+.
Falls back to title_api author extraction if OpenAlex API fails.
Run once: python -m src.patch_authors
"""
from __future__ import annotations

import time
import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from .config import ENRICHED_CSV

_OA_BASE  = "https://api.openalex.org"
_CR_BASE  = "https://api.crossref.org"
_EMAIL    = "l31azevedo@gmail.com"
_HEADERS  = {"User-Agent": f"corpus-study-patch/1.0 mailto:{_EMAIL}"}
_SSL      = False
_SLEEP    = 0.12


def _get(url: str, params: dict | None = None) -> dict | None:
    try:
        r = requests.get(url, params=params, headers=_HEADERS,
                         timeout=20, verify=_SSL)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _format_authors(names: list[str]) -> str:
    """'Smith, J.' or 'Smith, J. et al.'"""
    if not names:
        return ""
    def _short(full: str) -> str:
        parts = full.strip().split()
        if len(parts) == 1:
            return parts[0]
        # last name + first initial
        last = parts[-1]
        first_init = parts[0][0] + "."
        return f"{last}, {first_init}"
    first = _short(names[0])
    return first if len(names) == 1 else f"{first} et al."


def _oa_authors(openalex_id: str) -> list[str]:
    work_id = str(openalex_id).split("/")[-1]
    data = _get(f"{_OA_BASE}/works/{work_id}",
                params={"select": "authorships", "mailto": _EMAIL})
    time.sleep(_SLEEP)
    if not data:
        return []
    ships = data.get("authorships", [])
    return [s["author"]["display_name"] for s in ships if s.get("author")]


def _cr_authors(doi: str) -> list[str]:
    doi = doi.strip().lstrip("https://doi.org/")
    data = _get(f"{_CR_BASE}/works/{doi}",
                params={"mailto": _EMAIL,
                        "select": "author"})
    time.sleep(_SLEEP)
    if not data:
        return []
    items = data.get("message", {}).get("author", [])
    names = []
    for a in items:
        family = a.get("family", "")
        given  = a.get("given", "")
        if family:
            names.append(f"{given} {family}".strip())
    return names


def main() -> None:
    print("\n=== PATCH AUTHORS ===")
    df = pd.read_csv(ENRICHED_CSV, dtype=str, keep_default_na=False).replace("", pd.NA)
    n = len(df)

    authors_col: list[str] = []

    for i, (_, row) in enumerate(df.iterrows()):
        oa_id  = row.get("openalex_id")
        doi    = row.get("doi_api") or row.get("doi")

        names: list[str] = []

        # 1. OpenAlex (preferred)
        if pd.notna(oa_id) and str(oa_id).strip():
            names = _oa_authors(str(oa_id).strip())

        # 2. Crossref fallback using DOI
        if not names and pd.notna(doi) and str(doi).strip():
            names = _cr_authors(str(doi).strip())

        result = _format_authors(names)
        authors_col.append(result)

        status = result if result else "NA"
        print(f"  [{i+1:02d}/{n}] {str(row.get('title',''))[:55]:<55}  →  {status}")

    df["article_authors"] = authors_col
    df.to_csv(ENRICHED_CSV, index=False)

    resolved = sum(1 for v in authors_col if v)
    print(f"\n  [ok] article_authors adicionado: {resolved}/{n} resolvidos")
    print(f"       enriched.csv atualizado.")


if __name__ == "__main__":
    main()
