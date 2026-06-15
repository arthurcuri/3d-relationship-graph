"""Leitura de PDFs, isolada num unico ponto.

Usa PyMuPDF quando disponivel e cai para pypdf quando a instalacao local nao
tem ``fitz``. Assim o pipeline continua reprodutivel em ambientes mais leves.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field

try:  # PyMuPDF
    import fitz
except ImportError:  # pragma: no cover - depende do ambiente local
    fitz = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - depende do ambiente local
    PdfReader = None


def _nfc(name: str) -> str:
    """Normaliza nomes de arquivo para Unicode NFC.

    O macOS lista nomes em NFD (decomposto), enquanto os literais do codigo
    estao em NFC. Padronizar em NFC garante que as juncoes por nome de arquivo
    (relacoes, cronograma) funcionem. O acesso ao arquivo continua valido, pois
    o filesystem do macOS e insensivel a normalizacao.
    """
    return unicodedata.normalize("NFC", name)


@dataclass
class PdfDocument:
    """Conteudo extraido de um PDF."""

    filename: str
    page_count: int
    metadata: dict
    pages: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "".join(page + "\n" for page in self.pages)

    def head_text(self, n_pages: int) -> str:
        """Texto concatenado das primeiras ``n_pages`` paginas."""
        return "".join(page + "\n" for page in self.pages[:n_pages])


def read_pdf(filepath: str | os.PathLike) -> PdfDocument:
    """Abre um PDF e retorna seu conteudo ja extraido por pagina."""
    filename = _nfc(os.path.basename(os.fspath(filepath)))

    if fitz is not None:
        doc = fitz.open(filepath)
        try:
            pages = [page.get_text() for page in doc]
            return PdfDocument(
                filename=filename,
                page_count=doc.page_count,
                metadata=doc.metadata or {},
                pages=pages,
            )
        finally:
            doc.close()

    if PdfReader is not None:
        reader = PdfReader(os.fspath(filepath))
        pages = [page.extract_text() or "" for page in reader.pages]
        raw_meta = reader.metadata or {}
        metadata = {
            str(k).lstrip("/").lower(): str(v)
            for k, v in raw_meta.items()
            if v is not None
        }
        return PdfDocument(
            filename=filename,
            page_count=len(reader.pages),
            metadata=metadata,
            pages=pages,
        )

    raise ImportError("Instale PyMuPDF ou pypdf para ler PDFs.")


def list_pdfs(directory: str | os.PathLike) -> list[str]:
    """Lista, em ordem, os nomes de arquivos PDF de um diretorio."""
    return sorted(
        _nfc(f) for f in os.listdir(directory) if f.lower().endswith(".pdf")
    )
