"""Persistência de datasets (CSV) e artefatos da visualização (JSON)."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


def read_csv(path: str | os.PathLike) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: str | os.PathLike, rows: list[dict], fieldnames: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: str | os.PathLike):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | os.PathLike, data) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
