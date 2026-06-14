"""Pipeline do slice de cronograma: CSV bruto -> dataset_cronograma.csv."""

from __future__ import annotations

from medicao.shared import config
from medicao.shared.storage import read_csv, write_csv
from medicao.slices.cronograma import classifier
from medicao.slices.cronograma.schema import FIELDS


def run(write: bool = True) -> list[dict]:
    linhas = read_csv(config.CRONOGRAMA_CSV)
    print(f"[cronograma] {len(linhas)} linhas no CSV bruto")

    registros = []
    seq = 0
    for linha in linhas:
        data = (linha.get("Dia") or "").strip()
        atividade = (linha.get("Atividade") or "").strip()
        if not data and not atividade:
            continue
        seq += 1

        aula_pdf = classifier.aula_vinculada(atividade)
        registros.append(
            {
                "id": seq,
                "data": data,
                "atividade": atividade,
                "tipo_atividade": classifier.classify_tipo(atividade),
                "modulo_tematico": classifier.classify_modulo(atividade),
                "aula_pdf": aula_pdf,
                "caminho_pdf_aula": config.aula_web_path(aula_pdf) if aula_pdf else "",
            }
        )

    vinculadas = sum(1 for r in registros if r["aula_pdf"])
    print(f"[cronograma] {len(registros)} atividades, {vinculadas} com aula vinculada")

    if write:
        write_csv(config.DATASET_CRONOGRAMA, registros, FIELDS)
        print(f"[cronograma] -> {config.DATASET_CRONOGRAMA}")

    return registros


if __name__ == "__main__":
    run()
