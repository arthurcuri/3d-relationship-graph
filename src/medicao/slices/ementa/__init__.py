"""Slice de ementa (disciplina): dataset obrigatorio compartilhado.

Consome ``ementa.csv`` (preenchido pelo usuario a partir do template) e produz
``ementa.txt`` (consumido pelo ACARI como texto da disciplina). Tambem fornece
os nos de ementa para a visualizacao 3D.
"""

from medicao.slices.ementa.pipeline import run

__all__ = ["run"]
