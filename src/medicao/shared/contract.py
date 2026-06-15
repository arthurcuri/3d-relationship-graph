"""Contrato de dados padronizado entre a visualizacao 3D e o ACARI.

Define os esquemas canonicos dos datasets de um *bundle* e a estrutura do
``manifest.json`` que descreve o bundle. O esquema de ``artigos`` e a *fusao*
do dataset rico do extrator de medicao com as colunas que o ACARI consome
(``title``, ``year``, ``doi``, ``abstract``, ``venue_type``, ``cohort``,
``in_statistical_test``, ``article_authors``), de modo que o MESMO CSV alimente
os dois sistemas.

Datasets:
- ``artigos``  -> OBRIGATORIO (corpus, compartilhado com o ACARI)
- ``ementa``   -> OBRIGATORIO (disciplina; vira ementa.txt para o ACARI)
- ``aulas``    -> OPCIONAL
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from medicao.shared import config
from medicao.shared.storage import read_csv, read_json, write_json

# ---------------------------------------------------------------------------
# Esquemas canonicos (ordem das colunas dos CSVs)
# ---------------------------------------------------------------------------

# Nucleo compativel com o ACARI primeiro, depois os campos ricos de medicao.
ARTIGOS_FIELDS = [
    "id",
    "title",
    "article_authors",
    "year",
    "doi",
    "abstract",
    "keywords",
    "venue_type",
    "in_statistical_test",
    "cohort",
    # --- campos ricos (medicao) ---
    "arquivo",
    "num_paginas",
    "num_referencias",
    "tamanho_amostra",
    "metodologia",
    "areas_pesquisa",
    "metricas_mencionadas",
    "metodos_estatisticos",
    "ferramentas_tecnologias",
    "padroes_normas",
    "contexto_dominio",
    "idioma",
    "veiculo_publicacao",
    "caminho_pdf",
]

EMENTA_FIELDS = [
    "id",
    "modulo",
    "topico",
    "descricao",
    "data",
    "aula_relacionada",
]

AULAS_FIELDS = [
    "id",
    "arquivo",
    "numero_aula",
    "titulo",
    "subtitulo",
    "professor",
    "disciplina",
    "num_slides",
    "topicos",
    "conceitos",
    "referencias",
    "objetivos",
    "resumo",
    "caminho_pdf",
]

RELACOES_FIELDS = [
    "artigo_id",
    "artigo_titulo",
    "artigo_arquivo",
    "ementa_id",
    "ementa_topico",
    "score_relevancia",
    "total_temas",
    "percentual_match",
]

# Nome do arquivo de cada dataset dentro do bundle.
DATASET_FILES = {
    "artigos": "artigos.csv",
    "ementa": "ementa.csv",
    "aulas": "aulas.csv",
    "relacoes": "relacoes.csv",
    "grupo2_respostas": "grupo2_respostas.csv",
    "grupo2_auditoria": "grupo2_auditoria.csv",
}

REQUIRED_DATASETS = ("artigos", "ementa")
OPTIONAL_DATASETS = ("aulas", "relacoes", "grupo2_respostas", "grupo2_auditoria")


# ---------------------------------------------------------------------------
# Bundle
# ---------------------------------------------------------------------------

@dataclass
class Bundle:
    """Um conjunto padronizado de datasets em ``datasets/<name>/``."""

    name: str

    @property
    def dir(self) -> Path:
        return config.bundle_dir(self.name)

    def path(self, dataset: str) -> Path:
        return self.dir / DATASET_FILES[dataset]

    @property
    def manifest_path(self) -> Path:
        return self.dir / "manifest.json"

    @property
    def graph_path(self) -> Path:
        return self.dir / "graph.json"

    def has(self, dataset: str) -> bool:
        return self.path(dataset).exists()

    def load(self, dataset: str) -> list[dict]:
        return read_csv(self.path(dataset)) if self.has(dataset) else []

    def load_manifest(self) -> dict:
        if self.manifest_path.exists():
            return read_json(self.manifest_path)
        return default_manifest(self.name)

    def write_manifest(self, titulo: str | None = None) -> dict:
        manifest = default_manifest(self.name, titulo)
        manifest["datasets"] = {
            ds: {
                "file": DATASET_FILES[ds],
                "required": ds in REQUIRED_DATASETS,
                "present": self.has(ds),
            }
            for ds in (*REQUIRED_DATASETS, *OPTIONAL_DATASETS)
        }
        write_json(self.manifest_path, manifest)
        return manifest

    def validate(self) -> list[str]:
        """Retorna a lista de problemas (datasets obrigatorios ausentes)."""
        problemas = []
        for ds in REQUIRED_DATASETS:
            if not self.has(ds):
                problemas.append(f"dataset obrigatorio ausente: {ds} ({DATASET_FILES[ds]})")
        return problemas


def default_manifest(name: str, titulo: str | None = None) -> dict:
    return {
        "name": name,
        "titulo": titulo or name,
        "datasets": {},
        "node_types": {
            "artigo": {"label": "Artigos", "color": "#B85450", "label_field": "title"},
            "ementa": {"label": "Ementa", "color": "#4A90D9", "label_field": "topico"},
            "aula": {"label": "Aulas", "color": "#C4A96A", "label_field": "titulo"},
        },
    }


def list_bundles() -> list[str]:
    if not config.BUNDLES_DIR.exists():
        return []
    return sorted(
        p.name
        for p in config.BUNDLES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "manifest.json").exists()
    )
