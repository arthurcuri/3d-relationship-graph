"""Orquestrador do ACARI portado para dentro do vertical slice.

Substitui o antigo ``run_pipeline.py`` (que rodava por subprocess): aqui as
etapas vivem em ``medicao.slices.acari.steps`` e sao executadas no processo,
sempre sobre o mesmo bundle (mesmo ``artigos.csv`` + ``ementa.txt``).
"""

from __future__ import annotations

import importlib
import os
import time

from medicao.shared import config
from medicao.shared.contract import Bundle
from medicao.slices.ementa import run as ementa_run

STEPS = [
    "ingest",
    "enrich",
    "venue",
    "textsim",
    "baseline",
    "network",
    "rubric",
    "index",
    "stats",
    "viz",
    "export_latex",
]


def _patch_ssl() -> None:
    """Replica os ajustes de SSL do ACARI para as chamadas de API (best-effort)."""
    os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFICATION", "1")
    try:
        import httpx  # type: ignore

        _orig = httpx.Client.__init__

        def _no_ssl(self, *a, **kw):
            kw.setdefault("verify", False)
            _orig(self, *a, **kw)

        httpx.Client.__init__ = _no_ssl
    except ImportError:
        pass
    try:
        import urllib3  # type: ignore

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:  # noqa: BLE001
        pass


def _configure(bundle: str) -> None:
    """Define o bundle ativo do ACARI antes de importar as etapas."""
    os.environ["MEDICAO_ACARI_BUNDLE"] = bundle
    from medicao.slices.acari.steps import config as acari_config

    acari_config.configure(bundle)


def _run_step(name: str) -> None:
    t0 = time.time()
    print(f"\n{'=' * 60}\nETAPA: {name.upper()}\n{'=' * 60}")
    mod = importlib.import_module(f"medicao.slices.acari.steps.{name}")
    mod.main()
    print(f"  [ok] {name} em {time.time() - t0:.1f}s")


def run(
    bundle: str = config.DEFAULT_BUNDLE,
    run_pipeline: bool = False,
    start: str = "ingest",
    only: str | None = None,
):
    """Prepara (e opcionalmente executa) o pipeline do ACARI sobre o bundle.

    Args:
        run_pipeline: se False, apenas gera o ``ementa.txt`` e valida o bundle.
        start: etapa inicial (quando ``only`` e None).
        only: roda apenas esta etapa.
    """
    b = Bundle(bundle)
    problemas = b.validate()
    if problemas:
        raise ValueError("bundle invalido: " + "; ".join(problemas))

    # Gera/atualiza a ementa.txt (entrada da disciplina para o ACARI).
    ementa_run(bundle)
    _configure(bundle)

    print(f"[acari] corpus = {b.path('artigos')}")
    print(f"[acari] ementa = {b.dir / 'ementa.txt'}")

    if not run_pipeline:
        print("[acari] preparado. Para executar o pipeline completo:")
        print(f"        python -m medicao acari --run-acari --bundle {bundle}")
        return None

    _patch_ssl()
    steps = [only] if only else STEPS[STEPS.index(start):]
    print(f"[acari] etapas: {steps}")
    t0 = time.time()
    for step in steps:
        _run_step(step)
    print(f"\n[acari] PIPELINE COMPLETO em {time.time() - t0:.1f}s -> {b.dir / 'acari'}")
    return b.dir / "acari"


if __name__ == "__main__":
    run()
