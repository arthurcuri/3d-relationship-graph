"""CLI do pacote: ``python -m medicao [comando]``."""

from __future__ import annotations

import argparse

from medicao import pipeline
from medicao.shared import config
from medicao.slices import artigos, aulas, cronograma, grafo, relacoes, web

COMANDOS = {
    "all": lambda: pipeline.run_all(),
    "artigos": lambda: artigos.run(),
    "aulas": lambda: aulas.run(),
    "cronograma": lambda: cronograma.run(),
    "relacoes": lambda: relacoes.run(),
    "web": lambda: web.run(),
    "grafo": lambda: grafo.run(),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="medicao",
        description="Pipeline de extração e visualização da disciplina de Medição de Software.",
    )
    parser.add_argument(
        "comando",
        nargs="?",
        default="all",
        choices=sorted(COMANDOS),
        help="Slice a executar (default: all).",
    )
    args = parser.parse_args()

    if args.comando != "all":
        config.ensure_dirs()
    COMANDOS[args.comando]()


if __name__ == "__main__":
    main()
