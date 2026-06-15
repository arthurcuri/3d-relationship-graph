"""Config do ACARI portado: deriva os caminhos do bundle do projeto.

Mantem os MESMOS nomes de constantes do ACARI original (SEED_SRC, ENRICHED_CSV,
FIGS, GROUP_COLUMN, ...), de modo que os modulos de etapa continuem usando
``from .config import X`` sem alteracao. Os valores, porem, sao derivados de um
``Bundle`` (datasets/<bundle>/) em vez de um YAML.

O bundle ativo e definido pela env var ``MEDICAO_ACARI_BUNDLE`` (default:
"medicao"), aplicada no import. O orquestrador define essa env var antes de
importar as etapas.
"""

from __future__ import annotations

import os
from pathlib import Path

from medicao.shared.contract import Bundle

# ── constantes de algoritmo (defaults) ──────────────────────────────────────
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RANDOM_SEED = 42
N_PERMUTATIONS = 10_000
BASELINE_N = 200
BASELINE_CONCEPT_ID = "C41008148"  # OpenAlex: Software Engineering
GROUP_COLUMN = None  # coluna de grupo p/ H2/H3 (None desativa)
EXCLUDED_VENUE_TYPES = {"book", "report", "magazine", "thesis", "chapter"}

# ── caminhos (preenchidos por configure) ────────────────────────────────────
ROOT: Path
DATA: Path
PDFS: Path
LOGS: Path
OUTPUTS: Path
FIGS: Path
TABLES: Path
ARTIGOS_SRC = None
PLANO_PDF: Path
SEED_SRC: Path
SEED_CSV: Path
COURSE_TXT: Path
VENUE_RANKS: Path
RUBRIC_CSV: Path
RUBRIC_TMPL: Path
ENRICHED_CSV: Path
BASELINE_CSV: Path
INGEST_LOG: Path
PRE_ENRICHED_CSV = None

ACTIVE_BUNDLE = ""


def configure(bundle_name: str) -> None:
    """Deriva todos os caminhos a partir do bundle e cria os diretorios."""
    global ROOT, DATA, PDFS, LOGS, OUTPUTS, FIGS, TABLES
    global ARTIGOS_SRC, PLANO_PDF, SEED_SRC, SEED_CSV, COURSE_TXT
    global VENUE_RANKS, RUBRIC_CSV, RUBRIC_TMPL, ENRICHED_CSV, BASELINE_CSV
    global INGEST_LOG, PRE_ENRICHED_CSV, ACTIVE_BUNDLE

    b = Bundle(bundle_name)
    ACTIVE_BUNDLE = bundle_name

    ROOT = b.dir
    OUTPUTS = b.dir / "acari"
    DATA = OUTPUTS / "data"
    PDFS = DATA / "pdfs"
    LOGS = OUTPUTS / "logs"
    FIGS = OUTPUTS / "figs"
    TABLES = OUTPUTS / "tables"

    # entradas: o MESMO artigos.csv do bundle e a ementa.txt gerada
    SEED_SRC = b.path("artigos")
    PLANO_PDF = b.dir / "ementa.txt"
    ARTIGOS_SRC = None  # sem diretorio de PDFs (corpus ja em CSV)
    PRE_ENRICHED_CSV = None

    # arquivos derivados
    SEED_CSV = DATA / "corpus_seed.csv"
    COURSE_TXT = DATA / "course_text.txt"
    VENUE_RANKS = DATA / "venue_rankings.csv"
    RUBRIC_CSV = DATA / "rubric.csv"
    RUBRIC_TMPL = DATA / "rubric_template.csv"
    ENRICHED_CSV = DATA / "enriched.csv"
    BASELINE_CSV = DATA / "baseline.csv"
    INGEST_LOG = LOGS / "ingest_log.csv"

    # pdfs/ so faz sentido quando ha um diretorio de PDFs para copiar; com o
    # corpus ja em CSV (ARTIGOS_SRC=None) ela ficaria sempre vazia.
    _dirs = [DATA, LOGS, FIGS, TABLES]
    if ARTIGOS_SRC is not None:
        _dirs.append(PDFS)
    for _d in _dirs:
        _d.mkdir(parents=True, exist_ok=True)


# bootstrap no import (bundle ativo via env var)
configure(os.environ.get("MEDICAO_ACARI_BUNDLE", "medicao"))
