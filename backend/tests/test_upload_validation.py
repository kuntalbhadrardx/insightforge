"""Upload validation answers with a message the user can act on."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from backend import main


class FakeUpload:
    """The slice of Starlette's UploadFile that `_read_upload` touches."""

    def __init__(self, filename: str | None, content_type: str | None, data: bytes):
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self, size: int = -1) -> bytes:
        return self._data if size < 0 else self._data[:size]


def read_paper(file, *, max_bytes: int = 2 * 1024 * 1024) -> bytes:
    return asyncio.run(
        main._read_upload(
            file,
            max_bytes=max_bytes,
            allowed_types=main.PDF_CONTENT_TYPES,
            allowed_extensions=main.PDF_EXTENSIONS,
            label="paper"
        )
    )


def status_and_detail(excinfo) -> tuple[int, str]:
    return excinfo.value.status_code, excinfo.value.detail


def test_wrong_extension_names_what_it_got_and_what_it_wanted():
    with pytest.raises(HTTPException) as excinfo:
        read_paper(FakeUpload("notes.txt", "text/plain", b"hello"))

    status, detail = status_and_detail(excinfo)
    assert status == 400
    assert detail == "Unsupported file type '.txt'; expected .pdf."


def test_wrong_content_type_is_rejected_even_with_a_pdf_extension():
    with pytest.raises(HTTPException) as excinfo:
        read_paper(FakeUpload("paper.pdf", "text/plain", b"%PDF-1.4"))

    status, detail = status_and_detail(excinfo)
    assert status == 415
    assert detail == "Unsupported content type 'text/plain' for a paper upload."


def test_an_empty_file_says_it_is_empty():
    with pytest.raises(HTTPException) as excinfo:
        read_paper(FakeUpload("paper.pdf", "application/pdf", b""))

    status, detail = status_and_detail(excinfo)
    assert status == 400
    assert detail == "The uploaded paper file is empty."


def test_oversize_file_reports_the_limit_in_megabytes():
    oversize = b"x" * (2 * 1024 * 1024 + 1)

    with pytest.raises(HTTPException) as excinfo:
        read_paper(FakeUpload("paper.pdf", "application/pdf", oversize))

    status, detail = status_and_detail(excinfo)
    assert status == 413
    assert detail == "paper is too large. The maximum upload size is 2 MB."


def test_a_missing_file_is_rejected_before_anything_is_read():
    with pytest.raises(HTTPException) as excinfo:
        read_paper(FakeUpload(None, None, b""))

    status, detail = status_and_detail(excinfo)
    assert status == 400
    assert detail == "A paper file is required."


def test_a_valid_pdf_returns_its_bytes():
    assert read_paper(FakeUpload("paper.pdf", "application/pdf", b"%PDF-1.4 ok")) == b"%PDF-1.4 ok"
