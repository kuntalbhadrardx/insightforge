"""FastAPI application for InsightForge.

Run from the ``insightforge`` directory (single worker -- the dataset cache is
per-process):

    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 1

Interactive docs are served at ``/docs`` on whatever origin hosts this app.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from . import agent as agent_module
from . import analytics, db, pdf_rag

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("insightforge.api")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def _env_number(name: str, default: float, cast: type = float) -> float:
    """Read a numeric setting, tolerating an unset or blank value."""
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return cast(float(raw)) if cast is int else cast(raw)
    except (TypeError, ValueError):
        logger.warning("Ignoring invalid %s=%r; using %s", name, raw, default)
        return default


MAX_UPLOAD_MB = int(_env_number("MAX_UPLOAD_MB", 15))
MAX_DATASET_MB = int(_env_number("MAX_DATASET_MB", 10))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_DATASET_BYTES = MAX_DATASET_MB * 1024 * 1024
#: Tabular ingest caps. Bigger files are rejected rather than silently sampled.
MAX_CSV_ROWS = int(_env_number("MAX_CSV_ROWS", 100_000))
MAX_CSV_COLUMNS = int(_env_number("MAX_CSV_COLUMNS", 50))
#: PDFs above this page count would take too long to embed on a small instance.
MAX_PDF_PAGES = int(_env_number("MAX_PDF_PAGES", 50))
MAX_CACHED_DATAFRAMES = int(_env_number("MAX_CACHED_DATAFRAMES", 50))
#: MiniLM cosine similarities are compressed: a strongly relevant 500-word chunk
#: usually scores 0.25-0.45, while a vague question ("what is in this paper?")
#: peaks around 0.15-0.20 against *any* chunk. The cut-off therefore has to stay
#: low; ranking, not filtering, decides which excerpts reach the LLM.
MATCH_THRESHOLD = _env_number("MATCH_THRESHOLD", 0.05)
MATCH_COUNT = int(_env_number("MATCH_COUNT", 6))

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://localhost:5173,http://localhost:8501"
PDF_CONTENT_TYPES = {"application/pdf", "application/octet-stream"}
PDF_EXTENSIONS = {".pdf"}
CSV_EXTENSIONS = {".csv"}

#: Per-user request budgets (falling back to client IP for anonymous calls).
RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "5/minute")
RATE_LIMIT_QA = os.getenv("RATE_LIMIT_QA", "10/minute")
RATE_LIMIT_ANOMALIES = os.getenv("RATE_LIMIT_ANOMALIES", "10/minute")
RATE_LIMIT_AGENT = os.getenv("RATE_LIMIT_AGENT", "10/minute")
RATE_LIMIT_MESSAGE = (
    "You've made too many requests in a short period. Please wait a minute and try again."
)
CSV_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}

#: In-process cache of active dataframes, keyed by dataset_id. This is deliberately
#: simple: it is lost on restart and not shared between workers, so the dataset
#: id is only usable against the worker that ingested it.
ACTIVE_DATAFRAMES: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class UploadPaperResponse(BaseModel):
    document_id: str
    filename: str
    total_pages: int
    chunk_count: int
    file_size_bytes: int


class PaperQARequest(BaseModel):
    document_id: uuid.UUID
    question: str = Field(min_length=1, max_length=2000)
    match_count: int = Field(default=MATCH_COUNT, ge=1, le=20)


class PageCitation(BaseModel):
    document_id: str
    page_number: int
    similarity: float


class PaperQAResponse(BaseModel):
    question: str
    answer: str
    citations: list[PageCitation]


class DatasetUploadResponse(BaseModel):
    dataset_id: str
    filename: str
    row_count: int
    col_count: int
    summary: dict[str, Any]


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=4000)
    dataset_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    report_id: str
    status: str
    title: str
    iterations: int
    steps: list[dict[str, Any]]
    report: str


class HealthResponse(BaseModel):
    status: str
    cached_datasets: int
    model: str


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        raw = DEFAULT_CORS_ORIGINS
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


#: Comma-separated browser origins allowed to call this API. ``CORS_ORIGINS``
#: is still honoured so existing .env files keep working.
_origins = _parse_origins(os.getenv("ALLOWED_ORIGINS") or os.getenv("CORS_ORIGINS"))

app = FastAPI(
    title="InsightForge API",
    version="1.0.0",
    description=(
        "AI research and data-analysis backend: PDF retrieval-augmented Q&A, "
        "tabular EDA, IsolationForest anomaly detection, and a Groq tool-calling agent."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Wildcard origins cannot be combined with credentialed requests.
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
def _rate_limit_key(request: Request) -> str:
    """Budget per authenticated user, falling back to the client IP."""
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_rate_limit_key, default_limits=[])
app.state.limiter = limiter


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Answer 429 with a friendly message instead of a slowapi traceback."""
    logger.warning("Rate limit hit for %s on %s", _rate_limit_key(request), request.url.path)
    return JSONResponse(
        status_code=429,
        content={"detail": RATE_LIMIT_MESSAGE},
        headers={"Retry-After": "60"},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_filename(filename: str | None, default: str) -> str:
    name = os.path.basename(filename or "").strip() or default
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return name[:120] or default


async def _read_upload(
    file: UploadFile | None,
    *,
    max_bytes: int,
    allowed_types: set[str],
    allowed_extensions: set[str],
    label: str,
) -> bytes:
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail=f"A {label} file is required.")

    # Extension first: rejecting a 15 MB "file.exe" should not require reading it.
    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in allowed_extensions:
        expected = " or ".join(sorted(allowed_extensions))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{extension or 'unknown'}'; expected {expected}.",
        )

    data = await file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail=f"The uploaded {label} file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"{label} is too large. The maximum upload size is "
                f"{max_bytes // (1024 * 1024)} MB."
            ),
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type and content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type '{content_type}' for a {label} upload.",
        )
    return data


def _cache_dataframe(dataset_id: str, entry: dict[str, Any]) -> None:
    if len(ACTIVE_DATAFRAMES) >= MAX_CACHED_DATAFRAMES:
        oldest = next(iter(ACTIVE_DATAFRAMES), None)
        if oldest is not None:
            ACTIVE_DATAFRAMES.pop(oldest, None)
    ACTIVE_DATAFRAMES[dataset_id] = entry


def _cached_dataset(dataset_id: uuid.UUID, user_id: str) -> dict[str, Any]:
    entry = ACTIVE_DATAFRAMES.get(str(dataset_id))
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Dataset is not loaded in this server process. Re-upload the CSV "
                "(dataset analysis is session-based)."
            ),
        )
    if entry["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Dataset does not belong to this user.")
    return entry


def _require_owned_document(document_id: str, user_id: str) -> dict[str, Any]:
    document = db.get_document(document_id=document_id, user_id=user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found for this user.")
    return document


def _build_qa_prompt(question: str, contexts: list[dict[str, Any]]) -> str:
    blocks = [
        f"[page {match['page_number']}] {match['content']}" for match in contexts
    ]
    return (
        "You are a research assistant answering questions about a PDF paper.\n"
        "Use ONLY the numbered context excerpts below. If the answer is not present, "
        "say that the paper does not appear to cover it. Cite the page for every claim "
        "using the format [page N].\n\n"
        "CONTEXT:\n"
        + "\n\n".join(blocks)
        + f"\n\nQUESTION: {question.strip()}\n\nANSWER (Markdown, concise):"
    )


def _groq_answer(prompt: str) -> str:
    client = agent_module.get_groq_client()
    try:
        completion = client.chat.completions.create(
            model=agent_module.MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": "You answer strictly from provided document excerpts.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=900,
        )
    except Exception as exc:
        raise agent_module.AgentError(f"Groq request failed: {exc}") from exc
    return (completion.choices[0].message.content or "").strip()


async def _db_call(action: str, func: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a blocking Supabase call in the threadpool with a clean 502 on failure."""
    try:
        return await run_in_threadpool(func, *args, **kwargs)
    except db.DatabaseError as exc:
        logger.error("Database operation failed (%s): %s", action, exc)
        raise HTTPException(status_code=502, detail=f"Database error during {action}.") from exc


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
#: ``auto_error=False`` so a missing header produces our own 401 with a
#: ``WWW-Authenticate`` challenge instead of FastAPI's generic 403.
_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="SupabaseAuth",
    description="Supabase access token (JWT) from ``supabase.auth`` sign-in.",
)

UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> str:
    """Resolve the caller's Supabase user id from the ``Authorization`` header.

    Declared as a sync dependency on purpose: FastAPI runs it in the threadpool,
    so the blocking ``auth.get_user`` network call never stalls the event loop.

    The resolved id is also stored on ``request.state`` so the rate limiter can
    budget requests per user (dependencies run before the limiter wrapper).
    """
    if credentials is None or not (credentials.credentials or "").strip():
        raise HTTPException(
            status_code=401,
            detail="Not authenticated: provide 'Authorization: Bearer <access_token>'.",
            headers=UNAUTHORIZED_HEADERS,
        )
    if (credentials.scheme or "").lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Unsupported authentication scheme; expected 'Bearer'.",
            headers=UNAUTHORIZED_HEADERS,
        )

    try:
        user = db.get_user_from_token(credentials.credentials)
    except db.AuthError as exc:
        logger.warning("Rejected access token: %s", exc)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token.",
            headers=UNAUTHORIZED_HEADERS,
        ) from exc
    except db.DatabaseError as exc:
        logger.error("Could not verify access token: %s", exc)
        raise HTTPException(
            status_code=503, detail="Authentication service is unavailable."
        ) from exc

    request.state.user_id = user["id"]
    return user["id"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        cached_datasets=len(ACTIVE_DATAFRAMES),
        model=agent_module.MODEL_NAME,
    )


@app.post(
    "/upload/paper",
    response_model=UploadPaperResponse,
    status_code=201,
    tags=["papers"],
)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_paper(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    file: UploadFile = File(..., description="PDF paper to ingest"),
) -> UploadPaperResponse:
    """Upload a PDF, extract page-tagged chunks, embed them and store everything."""
    data = await _read_upload(
        file,
        max_bytes=MAX_UPLOAD_BYTES,
        allowed_types=PDF_CONTENT_TYPES,
        allowed_extensions=PDF_EXTENSIONS,
        label="PDF",
    )
    filename = _safe_filename(file.filename, "paper.pdf")
    user_id_str = user_id

    # Parse and embed before touching storage, so invalid PDFs cost nothing.
    try:
        total_pages, chunks = await run_in_threadpool(
            pdf_rag.extract_pdf, data, MAX_PDF_PAGES
        )
    except pdf_rag.PDFPageLimitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except pdf_rag.PDFProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.error("Embedding pipeline failed: %s", exc)
        raise HTTPException(status_code=503, detail="Embedding model is unavailable.") from exc

    storage_path = f"{user_id_str}/{uuid.uuid4().hex}.pdf"

    try:
        await run_in_threadpool(
            db.upload_file,
            db.PAPERS_BUCKET,
            storage_path,
            data,
            "application/pdf",
        )
    except db.DatabaseError as exc:
        logger.error("PDF storage upload failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Could not store the uploaded PDF: {exc}"
        ) from exc

    document: dict[str, Any] | None = None
    try:
        document = await _db_call(
            "paper upload",
            db.insert_document,
            user_id=user_id_str,
            filename=filename,
            storage_path=storage_path,
            file_size_bytes=len(data),
            total_pages=total_pages,
        )
        await _db_call(
            "chunk insert",
            db.insert_chunks_batch,
            document_id=str(document["id"]),
            user_id=user_id_str,
            chunks=chunks,
        )
    except HTTPException:
        # Roll back the partial ingestion so retries start clean.
        if document is not None:
            await run_in_threadpool(db.delete_document, str(document["id"]))
        await run_in_threadpool(db.remove_file, db.PAPERS_BUCKET, storage_path)
        raise

    return UploadPaperResponse(
        document_id=str(document["id"]),
        filename=filename,
        total_pages=total_pages,
        chunk_count=len(chunks),
        file_size_bytes=len(data),
    )


@app.post("/paper/qa", response_model=PaperQAResponse, tags=["papers"])
@limiter.limit(RATE_LIMIT_QA)
async def paper_qa(
    request: Request,
    payload: PaperQARequest,
    user_id: str = Depends(get_current_user_id),
) -> PaperQAResponse:
    """Answer a question about one document using pgvector retrieval + Groq."""
    document_id = str(payload.document_id)

    await _db_call("paper lookup", _require_owned_document, document_id, user_id)

    try:
        query_embedding = await run_in_threadpool(pdf_rag.embed_query, payload.question)
    except RuntimeError as exc:
        logger.error("Query embedding failed: %s", exc)
        raise HTTPException(status_code=503, detail="Embedding model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    matches = await _db_call(
        "vector search",
        db.search_paper_chunks,
        user_id=user_id,
        query_embedding=query_embedding,
        match_threshold=MATCH_THRESHOLD,
        match_count=payload.match_count,
        document_id=document_id,
    )

    if not matches and MATCH_THRESHOLD > 0.0:
        # A stricter MATCH_THRESHOLD was configured. Rather than claim the document
        # holds nothing relevant, retry unfiltered once and let ranking decide.
        logger.info(
            "No chunks passed threshold %.3f; retrying unfiltered for document %s",
            MATCH_THRESHOLD,
            document_id,
        )
        matches = await _db_call(
            "vector search (relaxed)",
            db.search_paper_chunks,
            user_id=user_id,
            query_embedding=query_embedding,
            match_threshold=0.0,
            match_count=payload.match_count,
            document_id=document_id,
        )

    if not matches:
        return PaperQAResponse(
            question=payload.question,
            answer=(
                "I could not find relevant passages for this question in the document. "
                "Try rephrasing it or uploading the paper again."
            ),
            citations=[],
        )

    prompt = _build_qa_prompt(payload.question, matches)
    try:
        answer = await run_in_threadpool(_groq_answer, prompt)
    except agent_module.AgentError as exc:
        logger.error("Paper Q&A LLM call failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The AI model is temporarily unavailable. Please try again in a moment.",
        ) from exc

    best_by_page: dict[int, PageCitation] = {}
    for match in matches:
        page = int(match["page_number"])
        citation = PageCitation(
            document_id=str(match["document_id"]),
            page_number=page,
            similarity=round(float(match["similarity"]), 4),
        )
        existing = best_by_page.get(page)
        if existing is None or citation.similarity > existing.similarity:
            best_by_page[page] = citation

    return PaperQAResponse(
        question=payload.question,
        answer=answer or "The language model returned an empty answer.",
        citations=[best_by_page[page] for page in sorted(best_by_page)],
    )


@app.post(
    "/upload/dataset",
    response_model=DatasetUploadResponse,
    status_code=201,
    tags=["datasets"],
)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_dataset(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    file: UploadFile = File(..., description="CSV dataset"),
) -> DatasetUploadResponse:
    """Upload a CSV, compute an EDA summary, persist metadata and cache the dataframe."""
    data = await _read_upload(
        file,
        max_bytes=MAX_DATASET_BYTES,
        allowed_types=CSV_CONTENT_TYPES,
        allowed_extensions=CSV_EXTENSIONS,
        label="CSV",
    )
    filename = _safe_filename(file.filename, "dataset.csv")
    user_id_str = user_id

    try:
        frame = await run_in_threadpool(analytics.load_dataframe, data)
    except analytics.DatasetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    row_count = int(frame.shape[0])
    col_count = int(frame.shape[1])
    if row_count > MAX_CSV_ROWS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CSV has {row_count:,} rows; the maximum is {MAX_CSV_ROWS:,}. "
                "Please sample the data before uploading."
            ),
        )
    if col_count > MAX_CSV_COLUMNS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"CSV has {col_count:,} columns; the maximum is {MAX_CSV_COLUMNS:,}. "
                "Please drop unused columns before uploading."
            ),
        )

    summary = await run_in_threadpool(analytics.summarize_dataframe, frame)

    storage_path = f"{user_id_str}/{uuid.uuid4().hex}.csv"
    dataset: dict[str, Any] | None = None
    try:
        await run_in_threadpool(
            db.upload_file, db.DATASETS_BUCKET, storage_path, data, "text/csv"
        )
        dataset = await _db_call(
            "dataset upload",
            db.insert_dataset,
            user_id=user_id_str,
            filename=filename,
            storage_path=storage_path,
            row_count=int(frame.shape[0]),
            col_count=int(frame.shape[1]),
            summary_stats=summary,
        )
    except (db.DatabaseError, HTTPException) as exc:
        await run_in_threadpool(db.remove_file, db.DATASETS_BUCKET, storage_path)
        if isinstance(exc, HTTPException):
            raise
        logger.error("CSV storage/insert failed: %s", exc)
        raise HTTPException(
            status_code=502, detail=f"Could not store the uploaded dataset: {exc}"
        ) from exc

    dataset_id = str(dataset["id"])
    _cache_dataframe(
        dataset_id,
        {
            "df": frame,
            "user_id": user_id_str,
            "filename": filename,
            "storage_path": storage_path,
        },
    )

    return DatasetUploadResponse(
        dataset_id=dataset_id,
        filename=filename,
        row_count=int(frame.shape[0]),
        col_count=int(frame.shape[1]),
        summary=summary,
    )


@app.post("/dataset/{dataset_id}/anomalies", tags=["datasets"])
@limiter.limit(RATE_LIMIT_ANOMALIES)
async def dataset_anomalies(
    request: Request,
    dataset_id: uuid.UUID,
    contamination: float = Form(
        analytics.DEFAULT_CONTAMINATION,
        description="Expected share of outliers, 0.01 - 0.20",
    ),
    features: list[str] | None = Form(
        default=None,
        description="Numeric columns to model; omitted means every non-labelled column.",
    ),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Run IsolationForest on the cached dataset and return the outlier records."""
    # Same bounds as the Streamlit slider, enforced server-side.
    if not analytics.MIN_CONTAMINATION <= contamination <= analytics.MAX_CONTAMINATION:
        raise HTTPException(
            status_code=422,
            detail=(
                "contamination must be between "
                f"{analytics.MIN_CONTAMINATION} and {analytics.MAX_CONTAMINATION} "
                "(expected share of outliers)."
            ),
        )

    entry = _cached_dataset(dataset_id, user_id)
    try:
        result = await run_in_threadpool(
            analytics.detect_outliers,
            entry["df"],
            contamination,
            features or None,
        )
    except analytics.DatasetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result["dataset_id"] = str(dataset_id)
    result["filename"] = entry["filename"]
    return result


@app.post("/agent/run", response_model=AgentRunResponse, tags=["agent"])
@limiter.limit(RATE_LIMIT_AGENT)
async def agent_run(
    request: Request,
    payload: AgentRunRequest,
    user_id: str = Depends(get_current_user_id),
) -> AgentRunResponse:
    """Run the tool-calling agent, persist the trace and store the Markdown report."""
    dataset_df = None
    dataset_id = None
    document_id = None

    if payload.dataset_id is not None:
        dataset_id = str(payload.dataset_id)
        dataset_df = _cached_dataset(payload.dataset_id, user_id)["df"]

    if payload.document_id is not None:
        document_id = str(payload.document_id)
        await _db_call("paper lookup", _require_owned_document, document_id, user_id)

    try:
        result = await run_in_threadpool(
            agent_module.run_agent_workflow,
            user_id,
            payload.goal,
            dataset_df,
            document_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except agent_module.AgentError as exc:
        logger.error("Agent run failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="The AI model is temporarily unavailable. Please try again in a moment.",
        ) from exc

    run_row = await _db_call(
        "agent run save",
        db.save_agent_run,
        user_id=user_id,
        goal=payload.goal,
        steps=result["steps"],
        status=result["status"],
    )
    report_row = await _db_call(
        "report save",
        db.save_report,
        user_id=user_id,
        title=result["title"],
        content_markdown=result["report"],
    )

    return AgentRunResponse(
        run_id=str(run_row["id"]),
        report_id=str(report_row["id"]),
        status=str(result["status"]),
        title=str(result["title"]),
        iterations=int(result["iterations"]),
        steps=result["steps"],
        report=str(result["report"]),
    )


__all__ = ["ACTIVE_DATAFRAMES", "app"]
