"""Configuração central de caminhos.

Tudo é resolvido a partir da raiz do repositório, eliminando os caminhos
absolutos que existiam nos scripts originais. É possível sobrescrever os
diretórios via variáveis de ambiente (útil para testes ou outra máquina):

- ``MEDICAO_DATA_DIR``  -> raiz dos dados (default: ``<repo>/data``)
- ``MEDICAO_WEB_DIR``   -> pasta da visualização (default: ``<repo>/visualizacao``)
"""

from __future__ import annotations

import os
from pathlib import Path

# src/medicao/shared/config.py -> parents[3] == raiz do repositório
ROOT_DIR = Path(__file__).resolve().parents[3]


def _dir(env_var: str, default: Path) -> Path:
    value = os.environ.get(env_var)
    return Path(value).expanduser().resolve() if value else default


DATA_DIR = _dir("MEDICAO_DATA_DIR", ROOT_DIR / "data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

ARTIGOS_DIR = RAW_DIR / "artigos"
AULAS_DIR = RAW_DIR / "aulas"
CRONOGRAMA_CSV = AULAS_DIR / "cronograma_atividades.csv"

WEB_DIR = _dir("MEDICAO_WEB_DIR", ROOT_DIR / "visualizacao")

# Datasets processados
DATASET_ARTIGOS = PROCESSED_DIR / "dataset_artigos.csv"
DATASET_AULAS = PROCESSED_DIR / "dataset_aulas.csv"
DATASET_CRONOGRAMA = PROCESSED_DIR / "dataset_cronograma.csv"
DATASET_RELACOES = PROCESSED_DIR / "dataset_relacoes_artigo_aula.csv"

# Saídas para a visualização web
WEB_DATA_JSON = WEB_DIR / "data.json"
WEB_GRAPH_JSON = WEB_DIR / "graph_data.json"

# Prefixos de caminho dos PDFs RELATIVOS ao index.html (que vive em WEB_DIR).
# index.html usa esses valores diretamente como ``src`` de um iframe.
ARTIGOS_WEB_PREFIX = "../data/raw/artigos"
AULAS_WEB_PREFIX = "../data/raw/aulas"


def artigo_web_path(filename: str) -> str:
    return f"{ARTIGOS_WEB_PREFIX}/{filename}"


def aula_web_path(filename: str) -> str:
    return f"{AULAS_WEB_PREFIX}/{filename}"


def ensure_dirs() -> None:
    """Garante que os diretórios de saída existam."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)
