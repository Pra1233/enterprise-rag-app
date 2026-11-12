import asyncio
import logging

import fitz  # PyMuPDF
import pdfplumber
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class DocumentParsingError(Exception):
    """Raised when a document cannot be parsed into structured text."""


class ParsedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(..., ge=0)
    text: str
    tables: list[list[list[str | None]]] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_count: int = Field(..., ge=0)
    pages: list[ParsedPage]


def _extract_tables_sync(file_path: str) -> dict[int, list[list[list[str | None]]]]:
    tables_by_page: dict[int, list[list[list[str | None]]]] = {}
    with pdfplumber.open(file_path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            if page_tables:
                tables_by_page[page_index] = page_tables
    return tables_by_page


def _parse_pdf_sync(file_path: str) -> ParsedDocument:
    try:
        tables_by_page = _extract_tables_sync(file_path)
    except Exception:
        logger.warning(
            "pdfplumber table extraction failed for '%s'; continuing with text only", file_path, exc_info=True
        )
        tables_by_page = {}

    doc = fitz.open(file_path)
    try:
        pages = [
            ParsedPage(
                page_number=page_index,
                text=(page.get_text("text") or "").strip(),
                tables=tables_by_page.get(page_index, []),
            )
            for page_index, page in enumerate(doc)
        ]
        page_count = doc.page_count
    finally:
        doc.close()

    return ParsedDocument(page_count=page_count, pages=pages)


async def parse_pdf(file_path: str) -> ParsedDocument:
    """Extract text + tables from a PDF, preserving per-page structure.

    PyMuPDF and pdfplumber are blocking, so the actual parsing runs in a
    worker thread (via asyncio.to_thread) and never blocks the event loop.
    """
    try:
        return await asyncio.to_thread(_parse_pdf_sync, file_path)
    except Exception as exc:
        logger.error("Failed to parse PDF '%s': %s", file_path, exc, exc_info=True)
        raise DocumentParsingError(f"Could not parse PDF at {file_path}") from exc
