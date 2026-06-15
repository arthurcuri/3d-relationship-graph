"""
src/ingest.py  –  Pipeline Step 1: Ingest & Validate

Tasks
-----
1. Extract data/course_text.txt from plano_de_ensino.pdf
2. Copy PDFs from Artigos/ → data/pdfs/
3. Match each corpus entry to a PDF via fuzzy title matching + manual overrides
4. Validate title/year by extracting text from the matched PDF
5. Add columns: pdf_path, venue_type (known cases), in_statistical_test
6. Create rubric_template.csv (empty, N rows × 6 rubric columns)

Outputs
-------
data/corpus_seed.csv        (updated with pdf_path, in_statistical_test)
data/course_text.txt
data/rubric_template.csv
logs/ingest_log.csv
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz import process as rfprocess

from medicao.shared.pdf import read_pdf

from .config import (
    ARTIGOS_SRC, PLANO_PDF, SEED_SRC,
    SEED_CSV, COURSE_TXT, RUBRIC_TMPL,
    PDFS, LOGS, INGEST_LOG,
    EXCLUDED_VENUE_TYPES, GROUP_COLUMN,
    PRE_ENRICHED_CSV, ENRICHED_CSV,
)

# ── manual PDF assignments (presenter name → pdf filename or None) ──────────
# Priority over fuzzy matching; covers disambiguation and known no-PDF cases.
MANUAL = {
    # Source Code Metrics: one PDF, two different papers.
    # The PDF is SAC'23 (DOI 10.1145/3555776.3577809) → Guilherme.
    # Renato's arXiv 2301.08022 has NO matching PDF.
    "Renato Matos Alves Penna":
        None,
    "Guilherme Gomes de Brites":
        "Source Code Metrics for Software Defects Prediction.pdf",

    # Same paper presented in two cohorts (duplicate entries)
    "Arthur Ferreira Costa":
        "Towards Improving Experimentation in Software Engineering.pdf",
    "Filipe Faria Melo":
        "Towards Improving Experimentation in Software Engineering.pdf",
    "Lucio Alves Almeida Neto":
        "Kitchenham, B. Guidelines for performing Systematic Literature Reviews"
        " in software engineering. EBSE Technical Report EBSE-2007-01.pdf",
    "Rodrigo Diniz Carvalho":
        "Kitchenham, B. Guidelines for performing Systematic Literature Reviews"
        " in software engineering. EBSE Technical Report EBSE-2007-01.pdf",

    # Language mismatch: corpus title in English, PDF filename in Portuguese
    "Gabriel Ferreira Amaral":
        "Medição e Análise no CMMI com Metodologia Seis Sigma eISOIECIEEE1593.pdf",
    "Ana Luiza Santos Gomes":
        "ARTIGO_Definição de um processo de medição de software baseado em"
        " Seis Sigma e CMMI.pdf",

    # Confirmed no PDF in Artigos/
    "Ryan Cristian Oliveira Rezende": None,
    "Ian dos Reis Novais":            None,
    "Lucas Flor Vilela":              None,
    "Lucas Cerqueira Azevedo":        None,
}

# venue_type / in_statistical_test for items we can determine at ingest time
# (venue_type already in CSV or derivable from notes)
KNOWN_VENUE_TYPES: dict[str, str] = {
    # pre-filled in corpus_seed.csv
    "Marina Ferreira Sansao Cabalzar": "book",      # Wohlin
    "Kayler de Freitas Moura":         "magazine",  # ACM Queue / SPACE
    "Lucas Cerqueira Azevedo":         "magazine",  # IEEE Potentials / Wei Li
    "Andre Xavier Lazarini":           "report",    # Basili GQM
    # from notes / our analysis
    "Andre Teiichi Santos Hyodo":      "report",    # Basili 1993 chapter
    "Lucio Alves Almeida Neto":        "report",    # Kitchenham tech report
    "Rodrigo Diniz Carvalho":          "report",    # same Kitchenham report
    "Gabriel Augusto Souza Borges":    "thesis",    # TCC PUC Minas
}

FUZZY_THRESHOLD = 55  # minimum token_set_ratio score


# ── helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Lowercase, strip accents, replace underscores and punctuation with spaces."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # keep only letters, digits, and spaces (underscores → space too)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _pdf_text(path: Path, pages: int = 2) -> str:
    try:
        return read_pdf(path).head_text(pages)
    except Exception:
        return ""


def _year_from_text(text: str) -> str:
    """Return most common plausible publication year found in text."""
    hits = re.findall(r"\b(199\d|20[012]\d)\b", text)
    if not hits:
        return ""
    return Counter(hits[:30]).most_common(1)[0][0]


def _title_overlap(csv_title: str, pdf_text: str) -> float:
    """Fraction of significant words from csv_title found in pdf_text."""
    words = [w for w in _norm(csv_title).split() if len(w) > 4]
    if not words:
        return 1.0
    norm_text = _norm(pdf_text[:3000])
    return sum(1 for w in words if w in norm_text) / len(words)


# ── Step 1: extract course_text.txt ──────────────────────────────────────────

def extract_course_text() -> None:
    """Extract ementa text from PDF or copy directly from a .txt file."""
    if PLANO_PDF is None:
        print("  [WARN] ementa_path not set — course_text.txt not generated")
        return
    suffix = Path(str(PLANO_PDF)).suffix.lower()
    if suffix == ".txt":
        text = Path(str(PLANO_PDF)).read_text(encoding="utf-8")
        COURSE_TXT.write_text(text, encoding="utf-8")
        print(f"  [ok] course_text.txt  ({len(text):,} chars, from .txt)")
    else:
        doc = read_pdf(PLANO_PDF)
        text = doc.full_text
        COURSE_TXT.write_text(text, encoding="utf-8")
        print(f"  [ok] course_text.txt  ({len(text):,} chars, {doc.page_count} pages)")


# ── Step 2: copy PDFs ─────────────────────────────────────────────────────────

def _unc(path: Path) -> str:
    """Return \\?\\-prefixed absolute path string to bypass MAX_PATH on Windows."""
    s = str(path.resolve())
    if len(s) > 200 and not s.startswith("\\\\?\\"):
        s = "\\\\?\\" + s
    return s


def copy_pdfs() -> dict[str, Path]:
    """Copy every *.pdf from Artigos/ to data/pdfs/. Return fname→dest map.
    Returns empty dict if artigos_dir is not configured."""
    if ARTIGOS_SRC is None:
        print("  [SKIP] artigos_dir not configured — PDF copy skipped")
        return {}
    if not Path(str(ARTIGOS_SRC)).exists():
        print(f"  [SKIP] artigos_dir not found: {ARTIGOS_SRC}")
        return {}
    copied: dict[str, Path] = {}
    skipped: list[str] = []
    for src in sorted(ARTIGOS_SRC.glob("*.pdf")):
        dest = PDFS / src.name
        if not dest.exists():
            try:
                shutil.copy2(_unc(src), _unc(dest))
            except Exception as e:
                skipped.append(f"{src.name}: {e}")
                continue
        copied[src.name] = dest
    if skipped:
        for s in skipped:
            print(f"  [WARN] copy skipped: {s[:100]}")
    print(f"  [ok] {len(copied)} PDFs in data/pdfs/")
    return copied


# ── Step 3 & 4: match PDFs and validate ──────────────────────────────────────

def match_and_validate(df: pd.DataFrame, pdf_map: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Add pdf_path column. Validate title/year against PDF text.
    Returns (updated_df, log_df).
    If pdf_map is empty (no artigos_dir configured), all pdf_paths = NA.
    """
    norm_stems: dict[str, str] = {
        fname: _norm(Path(fname).stem) for fname in pdf_map
    }

    rows_log = []
    pdf_paths: list[str] = []

    has_presenter = "presenter" in df.columns

    for _, row in df.iterrows():
        presenter = str(row["presenter"]) if has_presenter else ""
        title_csv = str(row["title"])
        year_csv  = str(row.get("year", "")) if pd.notna(row.get("year", "")) else ""

        # ── resolve PDF path ──────────────────────────────────────────────
        if not pdf_map:
            resolved: Path | None = None
            method = "no_artigos_dir"
        elif presenter in MANUAL:
            fname = MANUAL[presenter]
            if fname is None:
                resolved: Path | None = None
                method = "manual:no_pdf"
            else:
                resolved = PDFS / fname
                method = "manual:override"
        else:
            norm_title = _norm(title_csv)
            best = rfprocess.extractOne(
                norm_title,
                list(norm_stems.values()),
                scorer=fuzz.token_set_ratio,
                score_cutoff=FUZZY_THRESHOLD,
            )
            if best:
                matched_norm = best[0]
                matched_fname = next(
                    f for f, n in norm_stems.items() if n == matched_norm
                )
                resolved = PDFS / matched_fname
                method = f"fuzzy:{best[1]:.0f}"
            else:
                resolved = None
                method = "no_match"

        # ── validate via PDF text ─────────────────────────────────────────
        title_zone, year_pdf = "", ""
        title_div = year_div = False

        if resolved and resolved.exists():
            text = _pdf_text(resolved)
            title_zone = text[:150].replace("\n", " ")
            year_pdf   = _year_from_text(text)
            overlap    = _title_overlap(title_csv, text)
            title_div  = overlap < 0.45
            if year_csv and year_pdf and year_csv != year_pdf:
                year_div = True

        pdf_fname = resolved.name if resolved else "NA"
        pdf_paths.append(pdf_fname)

        rows_log.append({
            "cohort":         row.get("cohort", ""),
            "presenter":      presenter,
            "title_csv":      title_csv,
            "year_csv":       year_csv,
            "pdf_filename":   pdf_fname,
            "title_zone_pdf": title_zone[:120],
            "year_pdf":       year_pdf,
            "match_method":   method,
            "title_div":      title_div,
            "year_div":       year_div,
            "notes":          str(row.get("notes", "")),
        })

    df = df.copy()
    df["pdf_path"] = pdf_paths
    log_df = pd.DataFrame(rows_log)
    return df, log_df


# ── Step 5: add venue_type and in_statistical_test ───────────────────────────

def add_known_venue_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Fill venue_type from KNOWN_VENUE_TYPES dict (only when presenter column exists)
    if "presenter" in df.columns:
        for presenter, vtype in KNOWN_VENUE_TYPES.items():
            mask = df["presenter"] == presenter
            if mask.any():
                df.loc[mask, "venue_type"] = vtype

    # Compute in_statistical_test: False for known excluded types, NA otherwise
    def _ist(vtype) -> object:
        if pd.isna(vtype) or str(vtype).strip() == "":
            return pd.NA        # will be decided during enrich
        return str(vtype).lower() not in EXCLUDED_VENUE_TYPES

    if "venue_type" not in df.columns:
        df["venue_type"] = pd.NA
    df["in_statistical_test"] = df["venue_type"].apply(_ist)
    return df


# ── Step 6: rubric template ───────────────────────────────────────────────────

def make_rubric_template(df: pd.DataFrame) -> None:
    cols = [c for c in ["id", "cohort", "presenter", "title"] if c in df.columns]
    tmpl = df[cols].copy()
    tmpl["replicavel"]        = pd.NA   # 0 | 1 | 2
    tmpl["pratico_teorico"]   = pd.NA   # pratico | teorico | misto
    tmpl["nivel_aluno"]       = pd.NA   # 1–5
    tmpl["agregou"]           = pd.NA   # 1–5
    tmpl["relacao_disciplina"] = pd.NA  # direta | indireta | nenhuma
    tmpl["alinhado_plano"]    = pd.NA   # 0 | 1 | 2
    tmpl.to_csv(RUBRIC_TMPL, index=False)
    print(f"  [ok] rubric_template.csv  ({len(tmpl)} rows, fill manually)")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n=== INGEST ===")

    # 1. course text
    print("\n[1] Extracting course_text.txt ...")
    extract_course_text()

    # 2. copy PDFs
    print("\n[2] Copying PDFs to data/pdfs/ ...")
    pdf_map = copy_pdfs()

    # 3. load seed — always read from the bundle's artigos.csv (source of truth)
    print("\n[3] Loading corpus from bundle ...")
    df = pd.read_csv(SEED_SRC, dtype=str, keep_default_na=False)
    df = df.replace("", pd.NA)
    print(f"  [ok] {len(df)} articles, {len(df.columns)} columns")

    # Warn if group_column is expected but absent
    if GROUP_COLUMN and GROUP_COLUMN not in df.columns:
        print(f"  [WARN] group_column='{GROUP_COLUMN}' not found in CSV — H2/H3 will be skipped")

    # Ensure minimum required columns exist
    if "title" not in df.columns:
        raise ValueError("corpus CSV must have at least a 'title' column")
    if "in_statistical_test" not in df.columns:
        df["in_statistical_test"] = True
        print("  [INFO] 'in_statistical_test' not in CSV — defaulting to True for all rows")

    # 4. match PDFs
    print("\n[4] Matching PDFs ...")
    df, log = match_and_validate(df, pdf_map)

    # 5. venue_type + in_statistical_test
    print("\n[5] Setting known venue_types ...")
    df = add_known_venue_types(df)

    # 6. save seed to data/
    df.to_csv(SEED_CSV, index=False)
    print(f"\n  [ok] data/corpus_seed.csv saved")

    # 7. save log
    LOGS.mkdir(parents=True, exist_ok=True)
    log.to_csv(INGEST_LOG, index=False)
    print(f"  [ok] logs/ingest_log.csv saved")

    # 7. copy pre-enriched CSV if specified (demo / fast-forward mode)
    if PRE_ENRICHED_CSV is not None and PRE_ENRICHED_CSV.exists():
        import shutil as _shutil
        _shutil.copy2(str(PRE_ENRICHED_CSV), str(ENRICHED_CSV))
        print(f"\n  [ok] pre_enriched_csv copied → {ENRICHED_CSV.name}")

    # 8. rubric template
    print("\n[6] Creating rubric_template.csv ...")
    make_rubric_template(df)

    # ── summary ──────────────────────────────────────────────────────────
    n_matched  = (log["pdf_filename"] != "NA").sum()
    n_missing  = (log["pdf_filename"] == "NA").sum()
    n_tdiv     = log["title_div"].sum()
    n_ydiv     = log["year_div"].sum()

    print("\n── Ingest Summary ──────────────────────────────────────")
    print(f"  Total articles:       {len(df)}")
    print(f"  PDFs matched:         {n_matched}")
    print(f"  No PDF (NA):          {n_missing}")
    print(f"  Title divergences:    {n_tdiv}  (check ingest_log.csv)")
    print(f"  Year divergences:     {n_ydiv}  (check ingest_log.csv)")

    no_pdf = log[log["pdf_filename"] == "NA"][["cohort", "presenter", "title_csv"]]
    if not no_pdf.empty:
        print("\n  Articles with no PDF:")
        for _, r in no_pdf.iterrows():
            print(f"    [{r['cohort']}] {r['presenter']}: {r['title_csv'][:60]}")

    divs = log[(log["title_div"] == True) | (log["year_div"] == True)]
    if not divs.empty:
        print("\n  Divergences (title or year):")
        for _, r in divs.iterrows():
            flags = []
            if r["title_div"]:
                flags.append("TITLE")
            if r["year_div"]:
                flags.append(f"YEAR csv={r['year_csv']} pdf={r['year_pdf']}")
            print(f"    [{','.join(flags)}] {r['presenter']}: {r['title_csv'][:55]}")

    print("─" * 55)


if __name__ == "__main__":
    main()
