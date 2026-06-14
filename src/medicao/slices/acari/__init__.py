"""Slice de integracao com o ACARI.

Faz a ponte entre o contrato de bundle e o pipeline do ACARI: usa o mesmo
``artigos.csv`` como corpus, gera o ``ementa.txt`` a partir do dataset de
ementa e escreve um YAML de configuracao do ACARI apontando para o bundle.
"""

from medicao.slices.acari.pipeline import run

__all__ = ["run"]
