"""Shared fixtures for the backend suite.

Every test runs offline. Supabase, Groq and the sentence-transformer model are
three separate ways a unit test could accidentally touch the network, so the
guard below makes each of them fail loudly instead of hanging on a DNS lookup.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The embedding stack (torch) is a 2 GB import that several CI machines refuse to
# load at all, and no test here needs a real vector. A stand-in module keeps the
# suite offline and fast: `embed_query` is patched per test, and an accidental
# real encode fails through the model guard below.
if "sentence_transformers" not in sys.modules:
    stub = types.ModuleType("sentence_transformers")

    class SentenceTransformer:  # pragma: no cover - never instantiated
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("the embedding model was constructed; tests must stay offline")

    stub.SentenceTransformer = SentenceTransformer
    sys.modules["sentence_transformers"] = stub

from backend import agent, db, pdf_rag  # noqa: E402  (after sys.path setup)


def _forbidden(what: str):
    def explode(*_args, **_kwargs):
        raise AssertionError(f"{what} was called; this test must stay offline")

    return explode


@pytest.fixture(autouse=True)
def offline_guard(monkeypatch):
    """Fail fast on any un-stubbed outbound dependency."""
    monkeypatch.setattr(db, "get_client", _forbidden("Supabase"))
    monkeypatch.setattr(agent, "get_groq_client", _forbidden("Groq"))
    monkeypatch.setattr(pdf_rag, "get_embedding_model", _forbidden("the embedding model"))
    monkeypatch.setenv("GROQ_API_KEY", "offline-test-key")
    yield
