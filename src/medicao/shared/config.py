"""Configuracao central de caminhos, ciente de bundles de dataset.

Tudo e resolvido a partir da raiz do repositorio. Um *bundle* e uma pasta em
``datasets/<nome>/`` que reune os datasets padronizados (artigos, ementa e,
opcionalmente, aulas) consumidos tanto pela visualizacao 3D quanto pelo ACARI.

Variaveis de ambiente para override:

- ``MEDICAO_BUNDLES_DIR`` -> raiz dos bundles (default: ``<repo>/datasets``)
- ``MEDICAO_RAW_DIR``     -> raiz dos PDFs brutos (default: ``<repo>/data/raw``)
- ``MEDICAO_WEB_DIR``     -> pasta da visualizacao (default: ``<repo>/visualizacao``)
"""

from __future__ import annotations

import os
from pathlib import Path

# src/medicao/shared/config.py -> parents[3] == raiz do repositorio
ROOT_DIR = Path(__file__).resolve().parents[3]


def _dir(env_var: str, default: Path) -> Path:
    value = os.environ.get(env_var)
    return Path(value).expanduser().resolve() if value else default


BUNDLES_DIR = _dir("MEDICAO_BUNDLES_DIR", ROOT_DIR / "datasets")
TEMPLATES_DIR = BUNDLES_DIR / "_templates"

RAW_DIR = _dir("MEDICAO_RAW_DIR", ROOT_DIR / "data" / "raw")
WEB_DIR = _dir("MEDICAO_WEB_DIR", ROOT_DIR / "visualizacao")

# Fonte raiz da disciplina (ementa). A ementa.csv aqui e a fonte editavel,
# sincronizada para o bundle pelo slice de ementa.
EMENTA_DIR = _dir("MEDICAO_EMENTA_DIR", ROOT_DIR / "data" / "ementa")
EMENTA_SRC = EMENTA_DIR / "ementa.csv"
EMENTA_PDF = EMENTA_DIR / "ementa.pdf"
CRONOGRAMA_CSV = EMENTA_DIR / "cronograma_atividades.csv"

# Bundle default (gerado a partir dos PDFs em data/raw).
DEFAULT_BUNDLE = os.environ.get("MEDICAO_BUNDLE", "medicao")

# PDFs brutos do bundle medicao (entrada do extrator de artigos/aulas).
ARTIGOS_DIR = RAW_DIR / "artigos"
AULAS_DIR = RAW_DIR / "aulas"

# Indice global de bundles (consumido pela visualizacao).
BUNDLES_INDEX = BUNDLES_DIR / "index.json"

# Prefixos de caminho dos PDFs RELATIVOS ao index.html (em WEB_DIR).
ARTIGOS_WEB_PREFIX = "../data/raw/artigos"
AULAS_WEB_PREFIX = "../data/raw/aulas"


def artigo_web_path(filename: str) -> str:
    return f"{ARTIGOS_WEB_PREFIX}/{filename}"


def aula_web_path(filename: str) -> str:
    return f"{AULAS_WEB_PREFIX}/{filename}"


def bundle_dir(name: str) -> Path:
    return BUNDLES_DIR / name


def ensure_dirs(name: str = DEFAULT_BUNDLE) -> Path:
    """Garante que o diretorio do bundle e a pasta web existam."""
    bdir = bundle_dir(name)
    bdir.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    return bdir
