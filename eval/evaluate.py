"""Measure retrieval quality on the sample papers in eval/papers.

Three rankers are compared on the same chunks and the same questions:

  (a) vector-only  — cosine similarity over MiniLM embeddings, which is what
                     ``match_chunks`` does in Postgres.
  (b) full-text    — BM25 over the chunk text. Postgres would use
                     ``ts_rank_cd`` with the english configuration; BM25 is a
                     local stand-in so the evaluation runs with no database.
                     The numbers below are therefore BM25's, not Postgres'.
  (c) hybrid RRF   — reciprocal rank fusion of (a) and (b) with k=60, the same
                     formula as ``hybrid_search_chunks`` in the migration.

A retrieved chunk counts as a hit only when it comes from the expected page AND
contains the question's key phrase, so a lucky page number with the wrong text
does not score.

Run from the repository root:

    python eval/evaluate.py

Writes eval/RESULTS.md. Exits non-zero if the corpus or the questions are
malformed.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.pdf_rag import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS, chunk_pages  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
PAPERS_DIR = EVAL_DIR / "papers"
RESULTS_PATH = EVAL_DIR / "RESULTS.md"

PAGE_MARKER = re.compile(r"^=== PAGE (\d+) ===$", re.MULTILINE)
TOP_K = 10
RRF_K = 60
#: The same floor the API applies before ranking decides anything.
MATCH_THRESHOLD = 0.05

TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def load_pages(path: Path) -> list[tuple[int, str]]:
    """Split a marked-up paper into ``(page_number, text)`` pairs."""
    raw = path.read_text(encoding="utf-8")
    marks = list(PAGE_MARKER.finditer(raw))
    if not marks:
        raise SystemExit(f"{path.name} has no '=== PAGE n ===' markers")

    pages: list[tuple[int, str]] = []
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(raw)
        body = raw[mark.end() : end].strip()
        if body:
            pages.append((int(mark.group(1)), body))
    return pages


class BM25:
    """Small BM25 implementation, standing in for Postgres full-text search."""

    def __init__(self, documents: Sequence[str], k1: float = 1.5, b: float = 0.75):
        self.docs = [tokens(document) for document in documents]
        self.k1 = k1
        self.b = b
        self.lengths = [len(doc) for doc in self.docs]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.docs else 0.0
        self.frequencies = [Counter(doc) for doc in self.docs]
        self.document_frequency: Counter[str] = Counter()
        for doc in self.docs:
            self.document_frequency.update(set(doc))
        self.total = len(self.docs)

    def idf(self, term: str) -> float:
        df = self.document_frequency.get(term, 0)
        return math.log(1 + (self.total - df + 0.5) / (df + 0.5))

    def scores(self, query: str) -> list[float]:
        query_terms = tokens(query)
        results: list[float] = []
        for index, frequencies in enumerate(self.frequencies):
            length = self.lengths[index] or 1
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / (self.avg_length or 1)
                )
                score += self.idf(term) * frequency * (self.k1 + 1) / denominator
            results.append(score)
        return results


def rank_vector(similarities: np.ndarray) -> list[int]:
    order = np.argsort(-similarities)
    return [int(index) for index in order]


def rank_lexical(scores: Sequence[float]) -> list[int]:
    order = np.argsort([-score for score in scores])
    return [int(index) for index in order]


def fuse_rrf(rankings: Iterable[Sequence[int]], k: int = RRF_K) -> list[int]:
    totals: dict[int, float] = {}
    for ranking in rankings:
        for position, index in enumerate(ranking):
            totals[index] = totals.get(index, 0.0) + 1.0 / (k + position + 1)
    return sorted(totals, key=lambda index: totals[index], reverse=True)


def is_hit(chunk: dict[str, Any], question: dict[str, Any]) -> bool:
    if chunk["page_number"] != int(question["expected_page"]):
        return False
    return str(question["key_phrase"]).lower() in chunk["content"].lower()


def first_hit_rank(ranking: Sequence[int], chunks: Sequence[dict], question: dict) -> int | None:
    for position, index in enumerate(ranking[:TOP_K]):
        if is_hit(chunks[index], question):
            return position + 1
    return None


def score(ranks: Sequence[int | None]) -> dict[str, float]:
    total = len(ranks)
    return {
        "hit@1": sum(1 for rank in ranks if rank == 1) / total,
        "hit@3": sum(1 for rank in ranks if rank is not None and rank <= 3) / total,
        "mrr": sum(1.0 / rank for rank in ranks if rank is not None) / total
    }


def embed(texts: Sequence[str]) -> np.ndarray:
    """Real MiniLM embeddings; the model is cached locally after first use."""
    from backend.pdf_rag import get_embedding_model

    model = get_embedding_model()
    matrix = model.encode(
        list(texts), normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    )
    return np.asarray(matrix, dtype=float)


def evaluate() -> dict[str, Any]:
    questions = json.loads((EVAL_DIR / "questions.json").read_text(encoding="utf-8"))
    by_paper: dict[str, list[dict]] = {}
    corpus: dict[str, list[dict]] = {}

    for paper in questions["papers"]:
        path = PAPERS_DIR / paper
        if not path.exists():
            raise SystemExit(f"missing paper: {path}")
        chunks = chunk_pages(load_pages(path))
        if not chunks:
            raise SystemExit(f"{paper} produced no chunks")
        corpus[paper] = chunks
        by_paper[paper] = [q for q in questions["questions"] if q["paper"] == paper]
        if not by_paper[paper]:
            raise SystemExit(f"no questions for {paper}")

    rankings: dict[str, list[int | None]] = {"vector": [], "full-text": [], "hybrid": []}
    per_paper: dict[str, dict[str, list[int | None]]] = {}

    for paper, chunks in corpus.items():
        vectors = embed([chunk["content"] for chunk in chunks])
        bm25 = BM25([chunk["content"] for chunk in chunks])
        per_paper[paper] = {name: [] for name in rankings}

        for question in by_paper[paper]:
            query = embed([question["question"]])[0]
            vector_order = rank_vector(vectors @ query)
            lexical_order = rank_lexical(bm25.scores(question["question"]))
            hybrid_order = fuse_rrf([vector_order, lexical_order])

            # The vector ranker applies the API's similarity floor before ranking.
            allowed = [
                index
                for index in vector_order
                if float(vectors[index] @ query) >= MATCH_THRESHOLD
            ]
            for name, order in (
                ("vector", allowed),
                ("full-text", lexical_order),
                ("hybrid", hybrid_order),
            ):
                rank = first_hit_rank(order, chunks, question)
                rankings[name].append(rank)
                per_paper[paper][name].append(rank)

    return {
        "questions": len(questions["questions"]),
        "papers": {
            paper: {
                "pages": len(load_pages(PAPERS_DIR / paper)),
                "chunks": len(chunks),
                "questions": len(by_paper[paper])
            }
            for paper, chunks in corpus.items()
        },
        "overall": {name: score(ranks) for name, ranks in rankings.items()},
        "per_paper": {
            paper: {name: score(ranks) for name, ranks in methods.items()}
            for paper, methods in per_paper.items()
        },
        "chunk_size": CHUNK_SIZE_WORDS,
        "overlap": CHUNK_OVERLAP_WORDS,
    }


def render(results: dict[str, Any]) -> str:
    overall = results["overall"]
    rows = "\n".join(
        f"| {label} | {overall[name]['hit@1']:.1%} | {overall[name]['hit@3']:.1%} | "
        f"{overall[name]['mrr']:.3f} |"
        for name, label in (
            ("vector", "(a) vector-only"),
            ("full-text", "(b) full-text (BM25)"),
            ("hybrid", "(c) hybrid RRF"),
        )
    )
    paper_rows = "\n".join(
        f"| {paper} | {stats['pages']} | {stats['chunks']} | {stats['questions']} |"
        for paper, stats in results["papers"].items()
    )
    per_paper = "\n".join(
        f"| {paper} | {methods['vector']['mrr']:.3f} | {methods['full-text']['mrr']:.3f} | "
        f"{methods['hybrid']['mrr']:.3f} |"
        for paper, methods in results["per_paper"].items()
    )
    total_chunks = sum(stats["chunks"] for stats in results["papers"].values())

    return f"""# Retrieval evaluation

Generated by `python eval/evaluate.py` on the sample papers in `eval/papers`.
Every number here is produced by that script; nothing is estimated by hand.

## Method

A question counts as answered only when the retrieved chunk comes from the
expected page **and** contains the question's key phrase, so a chunk that merely
mentions the right page does not score. Metrics are over the top {TOP_K} results:

- **hit@1** — the first result is the right passage
- **hit@3** — a correct passage appears in the first three
- **MRR** — mean of `1 / rank` of the first correct passage, 0 when absent

Chunks are made by the production chunker (`backend.pdf_rag.chunk_pages`) at
{results['chunk_size']} words with {results['overlap']} words of overlap, and each paper is
searched on its own — the console scopes a conversation to one paper.

| Ranker | hit@1 | hit@3 | MRR |
|---|---|---|---|
{rows}

## Corpus

| Paper | Pages | Chunks | Questions |
|---|---|---|---|
{paper_rows}

{total_chunks} chunks in total across {len(results['papers'])} papers and {results['questions']} questions.
This is a small corpus: a single correct chunk in a field of three or four makes
hit@1 easy, so treat these as a regression baseline rather than a benchmark.

## Per paper (MRR)

| Paper | vector | full-text | hybrid |
|---|---|---|---|
{per_paper}

## What is and is not the production system

- **(a) vector-only** uses the same MiniLM model and the same cosine similarity
  and {MATCH_THRESHOLD} floor as `match_chunks`.
- **(c) hybrid** uses the same reciprocal-rank-fusion formula (k={RRF_K}) as
  `hybrid_search_chunks`.
- **(b) full-text** is BM25 computed locally. Postgres would use
  `ts_rank_cd` with the `english` configuration, and its stemming and phrase
  handling differ. The full-text column is therefore a lexical baseline, not a
  measurement of the deployed RPC.

## Reproduce

```bash
pip install -r requirements.txt
python eval/evaluate.py
```
"""


def main() -> None:
    results = evaluate()
    RESULTS_PATH.write_text(render(results), encoding="utf-8")

    overall = results["overall"]
    print(f"{results['questions']} questions over {len(results['papers'])} papers")
    for name in ("vector", "full-text", "hybrid"):
        stats = overall[name]
        print(
            f"  {name:10s} hit@1 {stats['hit@1']:.1%}  "
            f"hit@3 {stats['hit@3']:.1%}  MRR {stats['mrr']:.3f}"
        )
    print(f"wrote {RESULTS_PATH.relative_to(EVAL_DIR.parent)}")


if __name__ == "__main__":
    main()
