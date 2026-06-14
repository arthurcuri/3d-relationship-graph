"""Pipeline do slice web: registro de bundles em datasets/index.json."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.contract import Bundle, list_bundles
from medicao.shared.storage import read_json, write_json


def run(write: bool = True) -> dict:
    """Varre os bundles disponiveis e escreve o indice consumido pela visualizacao."""
    bundles = []
    for name in list_bundles():
        b = Bundle(name)
        manifest = b.load_manifest()
        counts = {}
        if b.graph_path.exists():
            try:
                counts = read_json(b.graph_path).get("meta", {}).get("counts", {})
            except Exception:  # noqa: BLE001
                counts = {}
        bundles.append(
            {
                "name": name,
                "titulo": manifest.get("titulo", name),
                "graph": f"{name}/graph.json",
                "counts": counts,
            }
        )

    index = {"bundles": bundles}
    if write:
        write_json(config.BUNDLES_INDEX, index)
        print(f"[web] -> {config.BUNDLES_INDEX} ({len(bundles)} bundles)")
    return index


if __name__ == "__main__":
    run()
