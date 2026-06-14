"""Conversao do dataset de ementa para o texto consumido pelo ACARI."""

from __future__ import annotations

from medicao.shared.text import clean_text


def to_ementa_text(registros: list[dict], titulo: str = "") -> str:
    """Gera o texto da disciplina (ementa.txt) a partir das linhas da ementa.

    Cada linha vira ``[modulo] topico: descricao``. Esse texto alimenta o
    calculo de alinhamento semantico do ACARI.
    """
    linhas = []
    if titulo:
        linhas.append(f"Ementa: {titulo}")
        linhas.append("")

    for r in registros:
        modulo = clean_text(r.get("modulo", ""))
        topico = clean_text(r.get("topico", ""))
        descricao = clean_text(r.get("descricao", ""))
        partes = []
        if modulo:
            partes.append(f"[{modulo}]")
        if topico:
            partes.append(topico)
        linha = " ".join(partes)
        if descricao:
            linha = f"{linha}: {descricao}" if linha else descricao
        if linha:
            linhas.append(f"- {linha}")

    return "\n".join(linhas) + "\n"
