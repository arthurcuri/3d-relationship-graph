"""Configuracao central de caminhos, ciente de bundles de dataset.

Tudo e resolvido a partir da raiz do repositorio. Um *bundle* e uma pasta em
``datasets/<nome>/`` que reune os datasets padronizados (artigos, ementa e,
opcionalmente, aulas) consumidos tanto pela visualizacao 3D quanto pelo ACARI.

A pasta ``data/`` agora tambem e organizada por bundle::

    data/
    ├── <bundle>/
    │   ├── raw/artigos/   (PDFs de artigos)
    │   ├── raw/aulas/     (PDFs de aulas, opcional)
    │   └── ementa/        (ementa.pdf, ementa.csv, cronograma)

Variaveis de ambiente para override:

- ``MEDICAO_BUNDLES_DIR`` -> raiz dos bundles (default: ``<repo>/datasets``)
- ``MEDICAO_DATA_DIR``    -> raiz dos dados brutos (default: ``<repo>/data``)
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

DATA_DIR = _dir("MEDICAO_DATA_DIR", ROOT_DIR / "data")
WEB_DIR = _dir("MEDICAO_WEB_DIR", ROOT_DIR / "visualizacao")

# Bundle default (gerado a partir dos PDFs em data/<bundle>).
DEFAULT_BUNDLE = os.environ.get("MEDICAO_BUNDLE", "medicao")

# Indice global de bundles (consumido pela visualizacao).
BUNDLES_INDEX = BUNDLES_DIR / "index.json"


# ---------------------------------------------------------------------------
# Caminhos por bundle (data/<bundle>/...)
# ---------------------------------------------------------------------------

def data_dir(bundle: str = DEFAULT_BUNDLE) -> Path:
    """Raiz dos dados brutos de um bundle: data/<bundle>/."""
    return DATA_DIR / bundle


def raw_dir(bundle: str = DEFAULT_BUNDLE) -> Path:
    """Pasta de PDFs brutos: data/<bundle>/raw/."""
    return data_dir(bundle) / "raw"


def artigos_dir(bundle: str = DEFAULT_BUNDLE) -> Path:
    """PDFs de artigos: data/<bundle>/raw/artigos/."""
    return raw_dir(bundle) / "artigos"


def aulas_dir(bundle: str = DEFAULT_BUNDLE) -> Path:
    """PDFs de aulas: data/<bundle>/raw/aulas/."""
    return raw_dir(bundle) / "aulas"


def ementa_dir(bundle: str = DEFAULT_BUNDLE) -> Path:
    """Fonte da ementa: data/<bundle>/ementa/."""
    return data_dir(bundle) / "ementa"


def ementa_src(bundle: str = DEFAULT_BUNDLE) -> Path:
    """ementa.csv (fonte editavel): data/<bundle>/ementa/ementa.csv."""
    return ementa_dir(bundle) / "ementa.csv"


def ementa_pdf(bundle: str = DEFAULT_BUNDLE) -> Path:
    """ementa.pdf (plano de ensino): data/<bundle>/ementa/ementa.pdf."""
    return ementa_dir(bundle) / "ementa.pdf"


def cronograma_csv(bundle: str = DEFAULT_BUNDLE) -> Path:
    """cronograma_atividades.csv: data/<bundle>/ementa/cronograma_atividades.csv."""
    return ementa_dir(bundle) / "cronograma_atividades.csv"


# ---------------------------------------------------------------------------
# Compatibilidade: constantes globais apontam para o bundle default.
# Uso desencorajado em codigo novo; prefira as funcoes acima.
# ---------------------------------------------------------------------------

RAW_DIR = raw_dir(DEFAULT_BUNDLE)
ARTIGOS_DIR = artigos_dir(DEFAULT_BUNDLE)
AULAS_DIR = aulas_dir(DEFAULT_BUNDLE)
EMENTA_DIR = ementa_dir(DEFAULT_BUNDLE)
EMENTA_SRC = ementa_src(DEFAULT_BUNDLE)
EMENTA_PDF = ementa_pdf(DEFAULT_BUNDLE)
CRONOGRAMA_CSV = cronograma_csv(DEFAULT_BUNDLE)


# ---------------------------------------------------------------------------
# Web paths (relativos ao index.html em visualizacao/)
# ---------------------------------------------------------------------------

def artigo_web_prefix(bundle: str = DEFAULT_BUNDLE) -> str:
    return f"../data/{bundle}/raw/artigos"


def aula_web_prefix(bundle: str = DEFAULT_BUNDLE) -> str:
    return f"../data/{bundle}/raw/aulas"


def artigo_web_path(filename: str, bundle: str = DEFAULT_BUNDLE) -> str:
    return f"{artigo_web_prefix(bundle)}/{filename}"


def aula_web_path(filename: str, bundle: str = DEFAULT_BUNDLE) -> str:
    return f"{aula_web_prefix(bundle)}/{filename}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def bundle_dir(name: str) -> Path:
    return BUNDLES_DIR / name


def ensure_dirs(name: str = DEFAULT_BUNDLE) -> Path:
    """Garante que o diretorio do bundle e a pasta web existam."""
    bdir = bundle_dir(name)
    bdir.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    # Garante a estrutura de data/<bundle>/ tambem.
    artigos_dir(name).mkdir(parents=True, exist_ok=True)
    ementa_dir(name).mkdir(parents=True, exist_ok=True)
    return bdir
