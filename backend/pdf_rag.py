"""PDF ingestion and embedding utilities.

Pipeline: raw PDF bytes -> per-page text (PyMuPDF) -> overlapping word windows
that never cross a page boundary (so every chunk has an exact page citation) ->
384-dimensional MiniLM embeddings.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Iterable, Sequence

import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384

#: MiniLM is trained with a 256-token window. We allow a larger window so that a
#: 500-word chunk is not truncated to roughly 190 words, at some cost in quality.
EMBEDDING_MAX_SEQ_LENGTH = int(os.getenv("EMBEDDING_MAX_SEQ_LENGTH", "512"))

CHUNK_SIZE_WORDS = int(os.getenv("CHUNK_SIZE_WORDS", "500"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "50"))
EMBEDDING_BATCH_SIZE = 32

class PDFPageLimitError(ValueError):
    """Raised when a PDF exceeds the configured page cap (HTTP 422 upstream)."""


class PDFProcessingError(ValueError):
    """Raised when a PDF cannot be parsed or contains no usable text."""


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load the embedding model exactly once per process (singleton)."""
    logger.info("Loading sentence-transformers model '%s'", EMBEDDING_MODEL_NAME)
    try:
        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    except Exception as exc:
        raise RuntimeError(
            f"Could not load embedding model '{EMBEDDING_MODEL_NAME}': {exc}"
        ) from exc
    model.max_seq_length = EMBEDDING_MAX_SEQ_LENGTH
    return model


def extract_pages(
    pdf_bytes: bytes, max_pages: int | None = None
) -> tuple[int, list[tuple[int, str]]]:
    """Extract text per page from raw PDF bytes.

    Returns ``(total_pages, pages)`` where ``pages`` holds ``(page_number, text)``
    pairs with 1-based page numbers. Pages with no extractable text (scans,
    full-page images) are skipped from ``pages`` but still counted in
    ``total_pages``.
    """
    if not pdf_bytes:
        raise PDFProcessingError("The uploaded PDF is empty.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFProcessingError(f"Could not open PDF: {exc}") from exc

    try:
        if document.needs_pass:
            raise PDFProcessingError("The PDF is password protected and cannot be read.")
        if document.page_count == 0:
            raise PDFProcessingError("The PDF has no pages.")
        if max_pages is not None and document.page_count > max_pages:
            raise PDFPageLimitError(
                f"PDF has {document.page_count} pages; the maximum is {max_pages}. "
                "Please upload a shorter document."
            )

        pages: list[tuple[int, str]] = []
        for index in range(document.page_count):
            page = document.load_page(index)
            try:
                text = page.get_text("text") or ""
            except Exception as exc:  # pragma: no cover - corrupt page stream
                logger.warning("Skipping page %s: %s", index + 1, exc)
                continue
            cleaned = _normalise_whitespace(text)
            if cleaned:
                pages.append((index + 1, cleaned))

        if not pages:
            raise PDFProcessingError(
                "No extractable text found in this PDF. Scanned documents need OCR first."
            )
        return document.page_count, pages
    finally:
        document.close()


def _normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace while keeping paragraph breaks meaningful."""
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def chunk_pages(
    pages: Sequence[tuple[int, str]],
    chunk_size: int = CHUNK_SIZE_WORDS,
    overlap: int = CHUNK_OVERLAP_WORDS,
) -> list[dict[str, Any]]:
    """Split page texts into overlapping word windows.

    Windows never span pages, which keeps ``page_number`` exact for citations.
    The final window of a page is emitted once, so no tiny duplicate tail chunk is
    produced.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0:
        raise ValueError("overlap cannot be negative.")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size.")

    stride = chunk_size - overlap
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for page_number, text in pages:
        words = text.split()
        if not words:
            continue

        start = 0
        while start < len(words):
            window = words[start : start + chunk_size]
            content = " ".join(window).strip()
            if content:
                chunks.append(
                    {
                        "content": content,
                        "page_number": int(page_number),
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1

            if start + chunk_size >= len(words):
                break
            start += stride

    return chunks


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed a batch of texts into normalised 384-length float vectors."""
    if not texts:
        return []

    cleaned = [text if isinstance(text, str) else str(text) for text in texts]
    if any(not text.strip() for text in cleaned):
        raise ValueError("Cannot embed empty text.")

    model = get_embedding_model()
    try:
        vectors = model.encode(
            cleaned,
            batch_size=EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Embedding failed: {exc}") from exc

    matrix = vectors.tolist() if hasattr(vectors, "tolist") else list(vectors)
    result: list[list[float]] = []
    for vector in matrix:
        values = [float(value) for value in vector]
        if len(values) != EMBEDDING_DIM:
            raise RuntimeError(
                f"Model '{EMBEDDING_MODEL_NAME}' returned {len(values)} dimensions, expected {EMBEDDING_DIM}."
            )
        result.append(values)
    return result


def embed_query(query: str) -> list[float]:
    """Embed a single search query."""
    if not query or not query.strip():
        raise ValueError("Query text cannot be empty.")
    return embed_texts([query.strip()])[0]


def embed_chunks(chunks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach an ``embedding`` to each chunk dictionary."""
    chunk_list = list(chunks)
    if not chunk_list:
        return []
    embeddings = embed_texts([chunk["content"] for chunk in chunk_list])
    for chunk, embedding in zip(chunk_list, embeddings):
        chunk["embedding"] = embedding
    return chunk_list


def extract_pdf(
    pdf_bytes: bytes, max_pages: int | None = None
) -> tuple[int, list[dict[str, Any]]]:
    """Full ingestion step: page count plus embedded, page-tagged chunks."""
    total_pages, pages = extract_pages(pdf_bytes, max_pages)

    chunks = chunk_pages(pages)
    if not chunks:
        raise PDFProcessingError("The PDF produced no text chunks.")

    embedded = embed_chunks(chunks)
    return total_pages, embedded


__all__ = [
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL_NAME",
    "PDFPageLimitError",
    "PDFProcessingError",
    "chunk_pages",
    "embed_chunks",
    "embed_query",
    "embed_texts",
    "extract_pages",
    "extract_pdf",
    "get_embedding_model",
]
