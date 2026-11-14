"""Retrieval: hybrid search degrades gracefully, and the agent refuses to cite
noise below its similarity cut-off."""

from __future__ import annotations

import asyncio

from backend import agent, db, main, pdf_rag

EMBEDDING = [0.01] * 384


def chunk(chunk_id: str, similarity: float, page: int = 3) -> dict:
    return {
        "id": chunk_id,
        "document_id": "doc-1",
        "content": f"passage {chunk_id}",
        "page_number": page,
        "similarity": similarity
    }


def run_retrieval() -> list[dict]:
    return asyncio.run(
        main._retrieve_context(
            question="what contamination was used?",
            query_embedding=EMBEDDING,
            user_id="user-1",
            document_id="doc-1",
            match_count=6
        )
    )


def test_hybrid_search_is_used_when_the_rpc_exists(monkeypatch):
    calls: list[str] = []

    def hybrid(**_kwargs):
        calls.append("hybrid")
        return [{**chunk("h1", 0.41), "rrf_score": 0.032}]

    monkeypatch.setattr(db, "hybrid_search_chunks", hybrid)
    monkeypatch.setattr(db, "search_paper_chunks", lambda **_kwargs: calls.append("vector"))

    matches = run_retrieval()

    assert calls == ["hybrid"]
    assert [match["id"] for match in matches] == ["h1"]


def test_falls_back_to_vector_only_when_the_hybrid_rpc_is_unavailable(monkeypatch):
    attempts: list[str] = []
    vector_kwargs: dict = {}

    def missing_rpc(**_kwargs):
        attempts.append("hybrid")
        # This is what PostgREST returns when the migration has not been applied.
        raise db.DatabaseError("function hybrid_search_chunks does not exist")

    def vector(**kwargs):
        attempts.append("vector")
        vector_kwargs.update(kwargs)
        return [chunk("v1", 0.44, page=7)]

    monkeypatch.setattr(db, "hybrid_search_chunks", missing_rpc)
    monkeypatch.setattr(db, "search_paper_chunks", vector)

    matches = run_retrieval()

    assert attempts == ["hybrid", "vector"]
    assert [match["id"] for match in matches] == ["v1"]
    assert matches[0]["page_number"] == 7
    # The fallback keeps the configured threshold rather than inventing one.
    assert vector_kwargs["match_threshold"] == main.MATCH_THRESHOLD
    assert vector_kwargs["match_count"] == 6


def session() -> agent._ToolSession:
    return agent._ToolSession(user_id="user-1", dataset_df=None, document_id="doc-1")


def test_agent_reports_no_relevant_passages_below_the_cut_off(monkeypatch):
    monkeypatch.setattr(pdf_rag, "embed_query", lambda _query: EMBEDDING)
    monkeypatch.setattr(
        db,
        "search_paper_chunks",
        lambda **_kwargs: [chunk("weak", 0.29), chunk("weaker", 0.05)]
    )

    result = session().search_papers({"query": "does this paper discuss soil pH?"})

    assert result["status"] == "no_relevant_passages"
    assert result["count"] == 0
    assert result["results"] == []
    assert result["best_similarity"] == 0.29
    assert "must not be cited" in result["message"]


def test_agent_cites_a_passage_exactly_at_the_cut_off(monkeypatch):
    monkeypatch.setattr(pdf_rag, "embed_query", lambda _query: EMBEDDING)
    monkeypatch.setattr(db, "search_paper_chunks", lambda **_kwargs: [chunk("ok", 0.30)])

    result = session().search_papers({"query": "what contamination was used?"})

    assert "status" not in result
    assert result["count"] == 1
    assert result["results"][0]["page_number"] == 3
    assert result["results"][0]["similarity"] == 0.3


def test_no_matches_at_all_is_also_no_relevant_passages(monkeypatch):
    monkeypatch.setattr(pdf_rag, "embed_query", lambda _query: EMBEDDING)
    monkeypatch.setattr(db, "search_paper_chunks", lambda **_kwargs: [])

    result = session().search_papers({"query": "anything"})

    assert result["status"] == "no_relevant_passages"
    assert result["best_similarity"] == 0.0
