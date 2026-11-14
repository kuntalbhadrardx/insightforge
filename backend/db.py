"""Supabase data-access layer for InsightForge.

Every function in this module talks to Supabase with the *service-role* key, which
bypasses Row-Level Security. The service role is required for background work such
as PDF ingestion, but it means every query here must be scoped by ``user_id``
explicitly -- never trust a client-supplied id to be owned by the caller.

The client is created lazily so that importing the package (for tests, tooling or
documentation builds) does not require live credentials.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Iterable, Sequence

import httpx
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

logger = logging.getLogger(__name__)

PAPERS_BUCKET = "papers"
DATASETS_BUCKET = "datasets"

#: PostgREST payloads are bounded; keep each chunk insert comfortably small.
CHUNK_INSERT_BATCH_SIZE = 100


class DatabaseError(RuntimeError):
    """Raised when a Supabase operation fails or is misconfigured."""


class AuthError(RuntimeError):
    """Raised when a bearer token is missing, malformed, expired or rejected."""


_client: Client | None = None
_auth_client: Client | None = None


def get_client() -> Client:
    """Return a cached Supabase client, creating it on first use."""
    global _client
    if _client is None:
        url = (os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            raise DatabaseError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in the environment."
            )
        try:
            _client = create_client(url, key)
        except Exception as exc:  # pragma: no cover - depends on live config
            raise DatabaseError(f"Could not create Supabase client: {exc}") from exc
    return _client


def get_auth_client() -> Client:
    """Return a client dedicated to verifying end-user access tokens.

    Kept separate from :func:`get_client` so token verification never mutates the
    session state of the service-role client used for data access. The anon key is
    preferred here (it is the key a browser/SDK would use); the service-role key
    works too and is used when no anon key is configured.
    """
    global _auth_client
    if _auth_client is None:
        url = (os.getenv("SUPABASE_URL") or "").strip()
        key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
        if not key:
            key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
        if not url or not key:
            raise DatabaseError(
                "SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_SERVICE_ROLE_KEY) "
                "must be set in the environment."
            )
        try:
            _auth_client = create_client(url, key)
        except Exception as exc:  # pragma: no cover - depends on live config
            raise DatabaseError(f"Could not create Supabase auth client: {exc}") from exc
    return _auth_client


def get_user_from_token(token: str) -> dict[str, Any]:
    """Validate a Supabase access token and return ``{"id", "email"}``.

    Raises :class:`AuthError` when Supabase rejects the token (invalid signature,
    expired, revoked user) and :class:`DatabaseError` when the auth service could
    not be reached, so callers can answer 401 for bad credentials and 5xx for an
    outage instead of blaming the caller.
    """
    cleaned = (token or "").strip()
    if not cleaned:
        raise AuthError("Missing bearer token.")

    client = get_auth_client()
    try:
        response = client.auth.get_user(cleaned)
    except httpx.HTTPError as exc:
        logger.error("Supabase auth request failed: %s", exc)
        raise DatabaseError(f"Could not reach Supabase auth: {exc}") from exc
    except Exception as exc:
        # gotrue/supabase_auth raise AuthApiError (or AuthRetryableError) here for
        # expired, malformed or otherwise rejected JWTs.
        raise AuthError(f"Invalid or expired access token: {exc}") from exc

    user = getattr(response, "user", None)
    if user is None and isinstance(response, dict):
        user = response.get("user")
    if user is None:
        raise AuthError("Supabase returned no user for this token.")

    user_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    email = user.get("email") if isinstance(user, dict) else getattr(user, "email", None)
    if not user_id:
        raise AuthError("Supabase returned a user without an id.")

    return {"id": str(user_id), "email": email}


def _execute(query: Any, action: str) -> list[dict[str, Any]]:
    """Run a PostgREST query and normalise errors into :class:`DatabaseError`."""
    try:
        response = query.execute()
    except Exception as exc:
        logger.exception("Supabase operation failed: %s", action)
        raise DatabaseError(f"Supabase {action} failed: {exc}") from exc

    data = getattr(response, "data", None)
    if data is None:
        return []
    if isinstance(data, dict):
        return [data]
    return list(data)


def _as_json_object(value: Any) -> Any:
    """Coerce a value into something PostgREST can serialise as ``jsonb``."""
    try:
        return json.loads(json.dumps(value, default=str, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise DatabaseError(f"Value is not JSON serialisable: {exc}") from exc


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
#: Storage API status codes mapped to the failure they usually represent.
_STORAGE_FAILURE_HINTS: dict[int, str] = {
    400: "Request rejected -- most often the bucket does not exist (Storage returns "
    "'Bucket not found' as 400) or the object path is invalid.",
    401: "API key rejected. SUPABASE_SERVICE_ROLE_KEY must be the service_role key "
    "from Project Settings -> API, not the anon/publishable key.",
    403: "Permission denied. This is a Storage RLS policy (or a key without INSERT "
    "privilege) rather than a code bug. The service_role key bypasses RLS, so a 403 "
    "here usually means an anon key is configured.",
    404: "Bucket or storage endpoint not found. Confirm the bucket name (case "
    "sensitive) and that SUPABASE_URL is https://<ref>.supabase.co.",
    409: "An object already exists at this path and upsert was not enabled.",
    413: "File exceeds the bucket's per-object size limit.",
    429: "Project hit its storage request rate limit; retry after a short backoff.",
    500: "Supabase Storage internal error; retry, then check project status.",
    503: "Supabase Storage unavailable (maintenance or project paused).",
}

#: Substrings that identify a duplicate-object rejection across storage3 versions.
_COLLISION_MARKERS = (
    "already exists",
    "duplicate",
    "resource already exists",
    "key already exists",
    "the resource already exists",
)


def _supabase_url() -> str:
    """Return the configured project URL, or a marker when it is missing."""
    return (os.getenv("SUPABASE_URL") or "").strip() or "<SUPABASE_URL not set>"


def _key_role(key: str) -> str:
    """Read the JWT ``role`` claim so logs can show service_role vs anon.

    Only the claim is returned -- the key itself is never logged or returned.
    """
    if not key:
        return "<missing>"
    parts = key.split(".")
    if len(parts) != 3:
        return "non-JWT key (cannot determine role)"
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:  # pragma: no cover - malformed key
        return "unreadable JWT"
    return str(claims.get("role") or "<no role claim>")


def _find_response(exc: BaseException) -> Any | None:
    """Locate an ``httpx.Response`` in an exception chain, if one survived."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for attribute in ("response", "res"):
            candidate = getattr(current, attribute, None)
            if candidate is not None and hasattr(candidate, "status_code"):
                return candidate
        current = current.__cause__ or current.__context__
    return None


def describe_storage_error(exc: BaseException) -> dict[str, Any]:
    """Collect every diagnostic storage3/httpx exposes about a failure.

    Returns a JSON-safe dictionary with the raw exception representation, HTTP
    status, Supabase error code/message, and response headers/body when the SDK
    kept them. Safe to log: it never contains an API key.
    """
    status = getattr(exc, "status", None)
    if status is None:
        status = getattr(exc, "status_code", None)

    details: dict[str, Any] = {
        "exception_type": type(exc).__name__,
        "exception_repr": repr(exc),
        "status_code": status,
        "error_code": getattr(exc, "code", None),
        "error_message": getattr(exc, "message", None),
        "response_headers": None,
        "response_body": None,
        "cause": None,
    }

    response = _find_response(exc)
    if response is not None:
        details["status_code"] = details["status_code"] or getattr(
            response, "status_code", None
        )
        try:
            details["response_headers"] = dict(response.headers)
        except Exception:  # pragma: no cover - defensive only
            pass
        try:
            details["response_body"] = str(response.text)[:2000]
        except Exception:  # pragma: no cover - defensive only
            pass

    if exc.__cause__ is not None:
        details["cause"] = f"{type(exc.__cause__).__name__}: {exc.__cause__}"
    return details


def _status_of(details: dict[str, Any]) -> int | None:
    """Coerce a possibly-string HTTP status into an int."""
    raw = details.get("status_code")
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _is_collision(details: dict[str, Any]) -> bool:
    """True when the failure is an already-exists rejection."""
    if _status_of(details) == 409:
        return True
    blob = " ".join(
        str(details.get(key) or "").lower()
        for key in ("error_message", "error_code", "response_body", "exception_repr")
    )
    return any(marker in blob for marker in _COLLISION_MARKERS)


def _failure_reason(details: dict[str, Any]) -> str:
    """Turn a failure into one actionable sentence."""
    status = _status_of(details)
    message = details.get("error_message") or details.get("error_code")
    blob = " ".join(
        str(details.get(key) or "").lower()
        for key in ("error_message", "error_code", "response_body", "exception_repr")
    )

    if "row-level security" in blob or "policy" in blob:
        return (
            "Blocked by a Row-Level Security policy; use the service_role key or add "
            "an INSERT policy for storage.objects on this bucket."
        )
    if "bucket not found" in blob or "bucket_not_found" in blob:
        return "The bucket does not exist in this project (create it in Storage, same name)."
    if "jwt" in blob or "invalid api key" in blob or "invalid signature" in blob:
        return (
            "The Supabase API key was rejected -- check that SUPABASE_SERVICE_ROLE_KEY "
            "is the service_role secret for this exact SUPABASE_URL project."
        )
    if "timeout" in blob or "timed out" in blob:
        return "Network timeout reaching Supabase Storage; check connectivity/proxy."

    hint = _STORAGE_FAILURE_HINTS.get(status) if status is not None else None
    if hint:
        return hint
    return f"Unexpected storage error ({details.get('exception_type')})."


def _bucket_available(bucket: str) -> bool | None:
    """Probe bucket existence up front. ``None`` means the probe was inconclusive."""
    probe = getattr(get_client().storage, "get_bucket", None)
    if probe is None:  # older storage3 without bucket introspection
        return None
    try:
        probe(bucket)
        return True
    except Exception as exc:
        if _status_of(describe_storage_error(exc)) == 404:
            return False
        logger.warning(
            "Bucket probe for '%s' was inconclusive: %s",
            bucket,
            describe_storage_error(exc),
        )
        return None


def _upload_once(
    bucket: str,
    object_path: str,
    data: bytes,
    content_type: str,
    *,
    upsert: bool,
) -> Any:
    """Perform a single storage upload with version-safe file options.

    storage3 expects ``upsert`` as the string ``"true"``/``"false"`` (it becomes
    the ``x-upsert`` header). Passing a Python bool raises inside httpx, and
    passing the string ``"false"`` is truthy in the SDK, so the key is only
    included when an overwrite is actually wanted.
    """
    options: dict[str, Any] = {"content-type": content_type}
    if upsert:
        options["upsert"] = "true"

    return get_client().storage.from_(bucket).upload(
        path=object_path,
        file=data,
        file_options=options,
    )


def upload_file(
    bucket: str,
    path: str,
    data: bytes,
    content_type: str,
    *,
    upsert: bool = False,
) -> str:
    """Upload ``data`` to ``bucket``/``path`` and return the object path.

    Drop-in replacement for the previous helper: same four positional arguments.
    Adds verbose diagnostics (bucket, path, byte size, content type, key role),
    probes the bucket first, transparently retries a collision with upsert, and
    raises :class:`DatabaseError` whose message names the root cause.
    """
    if not data:
        raise DatabaseError("Refusing to upload an empty file to storage.")
    if not bucket or not bucket.strip():
        raise DatabaseError("Storage bucket name is empty.")

    bucket = bucket.strip()
    object_path = (path or "").strip().lstrip("/")
    if not object_path or object_path.endswith("/"):
        raise DatabaseError(f"Invalid storage object path: {path!r}")

    size = len(data)
    service_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    logger.info(
        "Storage upload starting :: project=%s bucket=%s path=%s size=%d bytes "
        "content_type=%s key_role=%s",
        _supabase_url(),
        bucket,
        object_path,
        size,
        content_type,
        _key_role(service_key),
    )

    if not service_key:
        message = (
            "SUPABASE_SERVICE_ROLE_KEY is not set for this process; storage upload "
            "cannot be attempted. Set it in insightforge/.env and restart the server "
            "(python-dotenv only loads at import time)."
        )
        logger.error("Storage upload aborted :: %s", message)
        raise DatabaseError(message)

    try:
        available = _bucket_available(bucket)
    except DatabaseError:
        raise
    except Exception:  # pragma: no cover - probe must never block a valid upload
        logger.warning("Bucket existence probe failed; continuing", exc_info=True)
        available = None

    if available is False:
        message = (
            f"Storage upload failed for bucket '{bucket}': the bucket does not exist "
            f"in project {_supabase_url()}. Create it under Storage with this exact name."
        )
        logger.error("Storage upload aborted :: %s", message)
        raise DatabaseError(message)

    try:
        response = _upload_once(
            bucket, object_path, data, content_type, upsert=upsert
        )
    except Exception as exc:
        details = describe_storage_error(exc)
        logger.error(
            "Storage upload FAILED :: project=%s bucket=%s path=%s size=%d bytes "
            "content_type=%s diagnostics=%s",
            _supabase_url(),
            bucket,
            object_path,
            size,
            content_type,
            details,
        )

        if _is_collision(details):
            logger.warning(
                "Object already exists at %s/%s; retrying once with upsert=true",
                bucket,
                object_path,
            )
            try:
                response = _upload_once(
                    bucket, object_path, data, content_type, upsert=True
                )
            except Exception as retry_exc:
                retry_details = describe_storage_error(retry_exc)
                logger.error(
                    "Storage upload retry with upsert FAILED :: bucket=%s path=%s "
                    "diagnostics=%s",
                    bucket,
                    object_path,
                    retry_details,
                )
                raise DatabaseError(
                    f"Storage upload failed for bucket '{bucket}' at '{object_path}' "
                    f"(size={size} B, content_type={content_type}) after retrying with "
                    f"upsert: {_failure_reason(retry_details)} "
                    f"[status={retry_details.get('status_code')}, "
                    f"code={retry_details.get('error_code')}, "
                    f"message={retry_details.get('error_message')!r}]"
                ) from retry_exc
            logger.info(
                "Existing object replaced via upsert :: %s/%s (size=%d B)",
                bucket,
                object_path,
                size,
            )
        else:
            raise DatabaseError(
                f"Storage upload failed for bucket '{bucket}' at '{object_path}' "
                f"(size={size} B, content_type={content_type}): "
                f"{_failure_reason(details)} "
                f"[status={details.get('status_code')}, "
                f"code={details.get('error_code')}, "
                f"message={details.get('error_message')!r}, "
                f"exception={details.get('exception_repr')}]"
            ) from exc

    stored = getattr(response, "path", None) or getattr(response, "Key", None)
    logger.info(
        "Storage upload OK :: bucket=%s path=%s size=%d bytes content_type=%s "
        "response=%s",
        bucket,
        object_path,
        size,
        content_type,
        stored if stored is not None else repr(response),
    )
    return object_path


def remove_file(bucket: str, path: str) -> None:
    """Best-effort delete of a storage object (used for rollback)."""
    try:
        get_client().storage.from_(bucket).remove([path])
    except Exception:  # pragma: no cover - rollback must never mask the original error
        logger.warning("Could not roll back storage object %s/%s", bucket, path, exc_info=True)


def download_file(bucket: str, path: str) -> bytes:
    """Fetch a storage object's bytes (used to rebuild the dataset cache)."""
    try:
        payload = get_client().storage.from_(bucket).download(path)
    except Exception as exc:
        raise DatabaseError(f"Could not download {bucket}/{path}: {exc}") from exc
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, bytearray):
        return bytes(payload)
    raise DatabaseError(f"Storage returned no bytes for {bucket}/{path}")


def create_signed_url(bucket: str, path: str, expires_in: int = 3600) -> str | None:
    """Create a short-lived download URL, or ``None`` if it cannot be created."""
    try:
        response = get_client().storage.from_(bucket).create_signed_url(path, expires_in)
    except Exception:
        logger.warning("Could not sign URL for %s/%s", bucket, path, exc_info=True)
        return None
    payload: dict[str, Any]
    if isinstance(response, dict):
        payload = response
    elif hasattr(response, "model_dump"):
        payload = response.model_dump()
    else:
        payload = {}
    return payload.get("signedURL") or payload.get("signed_url") or payload.get("signedUrl")


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------
def insert_document(
    *,
    user_id: str,
    filename: str,
    storage_path: str,
    file_size_bytes: int,
    total_pages: int,
) -> dict[str, Any]:
    """Insert a ``documents`` row and return it."""
    rows = _execute(
        get_client()
        .table("documents")
        .insert(
            {
                "user_id": user_id,
                "filename": filename,
                "storage_path": storage_path,
                "file_size_bytes": int(file_size_bytes),
                "total_pages": int(total_pages),
            }
        ),
        "insert document",
    )
    if not rows:
        raise DatabaseError("Document insert returned no row.")
    return rows[0]


def delete_document(document_id: str) -> None:
    """Delete a document row (used to roll back a failed ingestion)."""
    try:
        _execute(
            get_client().table("documents").delete().eq("id", document_id),
            "delete document",
        )
    except DatabaseError:  # pragma: no cover - rollback path
        logger.warning("Could not roll back document %s", document_id, exc_info=True)


def get_document(*, document_id: str, user_id: str) -> dict[str, Any] | None:
    """Fetch a document owned by ``user_id`` (or ``None``)."""
    rows = _execute(
        get_client()
        .table("documents")
        .select("id,user_id,filename,storage_path,file_size_bytes,total_pages,created_at")
        .eq("id", document_id)
        .eq("user_id", user_id)
        .limit(1),
        "fetch document",
    )
    return rows[0] if rows else None


def list_documents(*, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """List a user's documents newest first, with chunk counts when available.

    ``chunks(count)`` is an embedded PostgREST aggregate resolved through the
    ``chunks.document_id`` foreign key. If a project's schema or PostgREST cache
    does not expose that relationship the query fails, so it falls back to a
    plain list -- the picker still works, just without counts.
    """
    columns = "id,filename,total_pages,created_at"
    try:
        rows = _execute(
            get_client()
            .table("documents")
            .select(f"{columns},chunks(count)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit),
            "list documents",
        )
    except DatabaseError:
        logger.warning(
            "Embedded chunks(count) unavailable; listing documents without counts",
            exc_info=True,
        )
        rows = _execute(
            get_client()
            .table("documents")
            .select(columns)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit),
            "list documents",
        )

    documents: list[dict[str, Any]] = []
    for row in rows:
        embedded = row.pop("chunks", None)
        count: Any = None
        if isinstance(embedded, list) and embedded:
            first = embedded[0]
            count = first.get("count") if isinstance(first, dict) else None
        elif isinstance(embedded, dict):
            count = embedded.get("count")
        try:
            row["chunk_count"] = int(count) if count is not None else None
        except (TypeError, ValueError):
            row["chunk_count"] = None
        documents.append(row)
    return documents


# ---------------------------------------------------------------------------
# chat_history
# ---------------------------------------------------------------------------
#: Roles permitted by the ``chat_history.role`` check constraint.
CHAT_ROLES = ("user", "assistant")
#: Upper bound on a single history read; the API pages nothing yet.
CHAT_HISTORY_MAX_ROWS = 500


def insert_chat_message(
    *,
    user_id: str,
    document_id: str,
    role: str,
    content: str,
    citations: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Persist one chat turn and return the stored row."""
    role_value = (role or "").strip().lower()
    if role_value not in CHAT_ROLES:
        raise DatabaseError(
            f"Invalid chat role {role!r}; expected one of {', '.join(CHAT_ROLES)}."
        )
    text = (content or "").strip()
    if not text:
        raise DatabaseError("Refusing to store an empty chat message.")

    rows = _execute(
        get_client()
        .table("chat_history")
        .insert(
            {
                "user_id": user_id,
                "document_id": document_id,
                "role": role_value,
                "content": text,
                "citations": _as_json_object(list(citations)) if citations else None,
            }
        ),
        "insert chat message",
    )
    if not rows:
        raise DatabaseError("Chat message insert returned no row.")
    return rows[0]


def list_chat_history(
    *,
    user_id: str,
    document_id: str,
    limit: int = CHAT_HISTORY_MAX_ROWS,
) -> list[dict[str, Any]]:
    """Return one document's conversation for ``user_id``, oldest message first."""
    if limit <= 0:
        raise DatabaseError("limit must be positive.")
    return _execute(
        get_client()
        .table("chat_history")
        .select("id,user_id,document_id,role,content,citations,created_at")
        .eq("user_id", user_id)
        .eq("document_id", document_id)
        .order("created_at", desc=False)
        .limit(min(limit, CHAT_HISTORY_MAX_ROWS)),
        "fetch chat history",
    )


def clear_chat_history(*, user_id: str, document_id: str) -> int:
    """Delete every stored turn for one document; returns the rows removed."""
    rows = _execute(
        get_client()
        .table("chat_history")
        .delete()
        .eq("user_id", user_id)
        .eq("document_id", document_id),
        "clear chat history",
    )
    return len(rows)


# ---------------------------------------------------------------------------
# chunks
# ---------------------------------------------------------------------------
def insert_chunks_batch(
    *,
    document_id: str,
    user_id: str,
    chunks: Sequence[dict[str, Any]],
) -> int:
    """Insert many ``chunks`` rows in batches and return the number written.

    Each input chunk must contain ``content``, ``page_number``, ``chunk_index`` and
    ``embedding`` (a 384-length sequence of floats).
    """
    if not chunks:
        return 0

    rows: list[dict[str, Any]] = []
    for chunk in chunks:
        embedding = chunk.get("embedding")
        if not embedding:
            raise DatabaseError("Chunk is missing its embedding.")
        if len(embedding) != 384:
            raise DatabaseError(f"Embedding must have 384 dimensions, got {len(embedding)}.")
        rows.append(
            {
                "document_id": document_id,
                "user_id": user_id,
                "content": str(chunk["content"]),
                "page_number": int(chunk.get("page_number", 1)),
                "chunk_index": int(chunk.get("chunk_index", len(rows))),
                "embedding": [float(value) for value in embedding],
            }
        )

    inserted = 0
    for start in range(0, len(rows), CHUNK_INSERT_BATCH_SIZE):
        batch = rows[start : start + CHUNK_INSERT_BATCH_SIZE]
        written = _execute(
            get_client().table("chunks").insert(batch),
            f"insert chunks batch starting at {start}",
        )
        inserted += len(written) or len(batch)
    return inserted


def search_paper_chunks(
    *,
    user_id: str,
    query_embedding: Sequence[float],
    match_threshold: float = 0.20,
    match_count: int = 6,
    document_id: str | None = None,
) -> list[dict[str, Any]]:
    """Call the ``match_chunks`` RPC and return normalised excerpts."""
    if len(query_embedding) != 384:
        raise DatabaseError(f"Query embedding must have 384 dimensions, got {len(query_embedding)}.")
    if not 0.0 <= match_threshold <= 1.0:
        raise DatabaseError("match_threshold must be between 0 and 1.")
    if match_count <= 0:
        raise DatabaseError("match_count must be positive.")

    params: dict[str, Any] = {
        "query_embedding": [float(value) for value in query_embedding],
        "match_threshold": float(match_threshold),
        "match_count": int(match_count),
        "filter_user_id": user_id,
        "filter_document_id": document_id,
    }

    rows = _execute(get_client().rpc("match_chunks", params), "match_chunks RPC")

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "id": row.get("id"),
                "document_id": row.get("document_id"),
                "content": row.get("content") or "",
                "page_number": int(row.get("page_number") or 1),
                "similarity": float(row.get("similarity") or 0.0),
            }
        )
    results.sort(key=lambda item: item["similarity"], reverse=True)
    return results


def hybrid_search_chunks(
    *,
    user_id: str,
    query_text: str,
    query_embedding: Sequence[float],
    match_count: int = 6,
    document_id: str | None = None,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Call the ``hybrid_search_chunks`` RPC (vector + full-text, fused by RRF).

    Returns one entry per chunk with its page number, cosine similarity, the
    fused ``rrf_score`` and the per-list ranks, already ordered best-first.
    A chunk found only by the text query has ``similarity`` 0 and a null
    ``vector_rank``; one found only by the vector scan has a null ``fts_rank``.
    """
    if len(query_embedding) != 384:
        raise DatabaseError(
            f"Query embedding must have 384 dimensions, got {len(query_embedding)}."
        )
    if match_count <= 0:
        raise DatabaseError("match_count must be positive.")
    if rrf_k < 0:
        raise DatabaseError("rrf_k must be zero or positive.")

    params: dict[str, Any] = {
        "query_text": (query_text or "").strip(),
        "query_embedding": [float(value) for value in query_embedding],
        "match_count": int(match_count),
        "filter_user_id": user_id,
        "filter_document_id": document_id,
        "rrf_k": int(rrf_k),
    }

    rows = _execute(
        get_client().rpc("hybrid_search_chunks", params),
        "hybrid_search_chunks RPC",
    )

    results: list[dict[str, Any]] = []
    for row in rows:
        vector_rank = row.get("vector_rank")
        fts_rank = row.get("fts_rank")
        results.append(
            {
                "id": row.get("chunk_id") or row.get("id"),
                "document_id": row.get("document_id"),
                "content": row.get("content") or "",
                "page_number": int(row.get("page_number") or 1),
                "similarity": float(row.get("similarity") or 0.0),
                "rrf_score": float(row.get("rrf_score") or 0.0),
                "vector_rank": int(vector_rank) if vector_rank is not None else None,
                "fts_rank": int(fts_rank) if fts_rank is not None else None,
            }
        )
    results.sort(key=lambda item: item["rrf_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# datasets
# ---------------------------------------------------------------------------
def insert_dataset(
    *,
    user_id: str,
    filename: str,
    storage_path: str,
    row_count: int,
    col_count: int,
    summary_stats: dict[str, Any],
) -> dict[str, Any]:
    """Insert a ``datasets`` row and return it."""
    rows = _execute(
        get_client()
        .table("datasets")
        .insert(
            {
                "user_id": user_id,
                "filename": filename,
                "storage_path": storage_path,
                "row_count": int(row_count),
                "col_count": int(col_count),
                "summary_stats": _as_json_object(summary_stats),
            }
        ),
        "insert dataset",
    )
    if not rows:
        raise DatabaseError("Dataset insert returned no row.")
    return rows[0]


def get_dataset(*, dataset_id: str, user_id: str) -> dict[str, Any] | None:
    """Fetch dataset metadata owned by ``user_id`` (or ``None``)."""
    rows = _execute(
        get_client()
        .table("datasets")
        .select("id,user_id,filename,storage_path,row_count,col_count,summary_stats,created_at")
        .eq("id", dataset_id)
        .eq("user_id", user_id)
        .limit(1),
        "fetch dataset",
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# agent_runs / reports
# ---------------------------------------------------------------------------
def save_agent_run(
    *,
    user_id: str,
    goal: str,
    steps: Iterable[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    """Persist an agent execution trace and return the stored row."""
    rows = _execute(
        get_client()
        .table("agent_runs")
        .insert(
            {
                "user_id": user_id,
                "goal": goal,
                "steps": _as_json_object(list(steps)),
                "status": status,
            }
        ),
        "insert agent run",
    )
    if not rows:
        raise DatabaseError("Agent run insert returned no row.")
    return rows[0]


def list_reports(*, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return the caller's saved briefs, newest first.

    Only metadata is selected: the Markdown body is fetched by
    :func:`get_report` when someone actually exports it, so listing stays cheap.
    """
    return _execute(
        get_client()
        .table("reports")
        .select("id,user_id,title,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit),
        "list reports",
    )


def get_report(*, report_id: str, user_id: str) -> dict[str, Any] | None:
    """Fetch one saved brief owned by ``user_id`` (or ``None``)."""
    rows = _execute(
        get_client()
        .table("reports")
        .select("id,user_id,title,content_markdown,created_at")
        .eq("id", report_id)
        .eq("user_id", user_id)
        .limit(1),
        "fetch report",
    )
    return rows[0] if rows else None


def save_report(
    *,
    user_id: str,
    title: str,
    content_markdown: str,
) -> dict[str, Any]:
    """Persist a generated Markdown report and return the stored row."""
    rows = _execute(
        get_client()
        .table("reports")
        .insert(
            {
                "user_id": user_id,
                "title": title,
                "content_markdown": content_markdown,
            }
        ),
        "insert report",
    )
    if not rows:
        raise DatabaseError("Report insert returned no row.")
    return rows[0]


__all__ = [
    "DATASETS_BUCKET",
    "PAPERS_BUCKET",
    "AuthError",
    "DatabaseError",
    "create_signed_url",
    "delete_document",
    "describe_storage_error",
    "get_auth_client",
    "get_client",
    "get_dataset",
    "get_user_from_token",
    "get_document",
    "get_report",
    "hybrid_search_chunks",
    "insert_chunks_batch",
    "insert_dataset",
    "insert_document",
    "list_documents",
    "list_reports",
    "remove_file",
    "save_agent_run",
    "save_report",
    "search_paper_chunks",
    "upload_file",
    "CHAT_HISTORY_MAX_ROWS",
    "CHAT_ROLES",
    "clear_chat_history",
    "insert_chat_message",
    "list_chat_history",
]
