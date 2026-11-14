"""Chunking is the layer every citation depends on: a window that drifts across
a page boundary makes the answer's page number a lie."""

from __future__ import annotations

from backend.pdf_rag import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS, chunk_pages


def page_text(count: int, prefix: str = "w") -> str:
    """`count` distinct words, so overlap can be checked by identity."""
    return " ".join(f"{prefix}{index}" for index in range(count))


def test_defaults_are_500_words_with_50_overlap():
    assert CHUNK_SIZE_WORDS == 500
    assert CHUNK_OVERLAP_WORDS == 50


def test_600_word_page_makes_two_windows_of_500_and_150_with_50_shared():
    chunks = chunk_pages([(1, page_text(600))])

    assert len(chunks) == 2
    first, second = (chunk["content"].split() for chunk in chunks)
    assert len(first) == 500
    assert len(second) == 150
    assert first[-50:] == second[:50]
    assert chunks[0]["page_number"] == chunks[1]["page_number"] == 1
    assert [chunk["chunk_index"] for chunk in chunks] == [0, 1]


def test_a_page_of_exactly_one_window_is_not_duplicated():
    chunks = chunk_pages([(1, page_text(500))])

    assert len(chunks) == 1
    assert len(chunks[0]["content"].split()) == 500


def test_no_window_ever_crosses_a_page_boundary():
    pages = [(1, page_text(500, "a")), (2, page_text(500, "b"))]
    chunks = chunk_pages(pages)

    assert [chunk["page_number"] for chunk in chunks] == [1, 2]
    for chunk in chunks:
        words = chunk["content"].split()
        prefix = "a" if chunk["page_number"] == 1 else "b"
        assert all(word.startswith(prefix) for word in words), chunk["page_number"]


def test_short_pages_keep_their_own_page_number():
    chunks = chunk_pages([(3, page_text(10, "c")), (4, page_text(20, "d"))])

    assert [(chunk["page_number"], len(chunk["content"].split())) for chunk in chunks] == [
        (3, 10),
        (4, 20)
    ]


def test_empty_pages_are_skipped_rather_than_emitted_as_blank_chunks():
    chunks = chunk_pages([(1, "   "), (2, page_text(5, "e"))])

    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 2
