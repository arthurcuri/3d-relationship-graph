"""CLI do pacote: ``python -m medicao [comando] [--bundle NOME]``."""

from __future__ import annotations

import argparse

from medicao import pipeline
from medicao.shared import config
from medicao.slices import acari, artigos, aulas, grafo, relacoes, web
from medicao.slices.ementa import run as ementa_run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="medicao",
        description="Pipeline de bundles (artigos + ementa + aulas) e integracao com o ACARI.",
    )
    parser.add_argument(
        "comando",
        nargs="?",
        default="all",
        choices=["all", "artigos", "aulas", "ementa", "relacoes", "grafo", "web", "acari"],
        help="Etapa a executar (default: all).",
    )
    parser.add_argument(
        "--bundle", default=config.DEFAULT_BUNDLE, help="Nome do bundle (default: medicao)."
    )
    parser.add_argument(
        "--run-acari",
        action="store_true",
        help="No comando 'acari', executa o pipeline do ACARI (requer dependencias).",
    )
    parser.add_argument("--acari-from", default="ingest", help="ACARI: etapa inicial.")
    parser.add_argument("--acari-only", default=None, help="ACARI: roda apenas esta etapa.")
    args = parser.parse_args()

    if args.comando == "all":
        pipeline.run_all(args.bundle)
        return

    config.ensure_dirs(args.bundle)
    if args.comando == "artigos":
        artigos.run(args.bundle)
    elif args.comando == "aulas":
        aulas.run(args.bundle)
    elif args.comando == "ementa":
        ementa_run(args.bundle)
    elif args.comando == "relacoes":
        relacoes.run(args.bundle)
    elif args.comando == "grafo":
        grafo.run(args.bundle)
    elif args.comando == "web":
        web.run()
    elif args.comando == "acari":
        acari.run(
            args.bundle,
            run_pipeline=args.run_acari,
            start=args.acari_from,
            only=args.acari_only,
        )


if __name__ == "__main__":
    main()
