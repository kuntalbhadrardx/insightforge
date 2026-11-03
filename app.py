"""
InsightForge · Streamlit frontend
=================================

Single-file Streamlit UI for the InsightForge FastAPI backend.

Run from the ``insightforge`` directory:

    streamlit run app.py

Environment variables
---------------------
BACKEND_URL            Base URL of the FastAPI service (falls back to `st.secrets`,
                       then to the local development default)
INSIGHTFORGE_TIMEOUT   Request timeout in seconds (default 180; agent runs are slow)
SUPABASE_URL           Supabase project URL (used for the sign-in form)
SUPABASE_ANON_KEY      Supabase anon/publishable key (used for the sign-in form)

Every backend call is authenticated with the Supabase access token obtained at
sign-in; the backend derives the user id from that token, so the UI never sends
one.

The client is tolerant of both response shapes: the documented public contract
(``chunks_indexed``, integer ``citations``, ``anomalies_detected`` …) and the
shapes actually emitted by ``backend/main.py`` (``chunk_count``, citation
objects with ``page_number``, ``anomaly_count`` + ``sample_outliers`` …).
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fpdf import FPDF
from fpdf.fonts import FontFace
import plotly.express as px
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"


def _secret_or_none(name: str) -> str | None:
    """Read ``st.secrets[name]`` without exploding when no secrets file exists."""
    try:
        value = st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None
    return str(value) if value else None


def resolve_app_url() -> str | None:
    """``APP_URL`` from st.secrets (or the environment) for sign-up redirects."""
    for candidate in (_secret_or_none("APP_URL"), os.getenv("APP_URL")):
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def resolve_backend_url() -> str:
    """``BACKEND_URL`` from the environment or st.secrets, else the dev default."""
    for candidate in (
        os.getenv("BACKEND_URL"),
        _secret_or_none("BACKEND_URL"),
        os.getenv("INSIGHTFORGE_API_URL"),
    ):
        if candidate and candidate.strip():
            return candidate.strip().rstrip("/")
    return DEFAULT_BACKEND_URL


API_BASE_URL = resolve_backend_url()
REQUEST_TIMEOUT = float(os.getenv("INSIGHTFORGE_TIMEOUT", "180"))

MAX_PREVIEW_ROWS = 250
MAX_PLOT_ROWS = 20_000
DEFAULT_CONTAMINATION = 0.05
MIN_CONTAMINATION = 0.01
MAX_CONTAMINATION = 0.20
#: Mirrors backend.analytics.LEAKY_COLUMN_MARKERS so the UI can show which
#: columns are excluded from the model.
LEAKY_COLUMN_MARKERS = ("truth", "label", "target", "is_anomaly", "id")
PLOTLY_TEMPLATE = "plotly_dark"
PLOT_COLORWAY = [
    "#f0a04b",
    "#7cc4ff",
    "#a78bfa",
    "#4ade80",
    "#fb7185",
    "#fbbf24",
    "#38bdf8",
    "#f472b6",
]

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


# ---------------------------------------------------------------------------
# Backend client
# ---------------------------------------------------------------------------
class BackendError(RuntimeError):
    """Raised when the FastAPI backend is unreachable or answers with an error."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def show_backend_error(exc: BackendError) -> None:
    """Render a backend failure as a warning or an error, never a stack trace.

    A 429 is a pacing problem, not a bug, so it is shown as a warning; the
    message comes from the API's friendly detail string.
    """
    if exc.status_code == 429:
        st.warning(str(exc), icon="⏳")
    else:
        st.error(str(exc))


def _describe_http_error(response: requests.Response) -> str:
    """Extract the most useful message from a FastAPI error response."""
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return text[:400] or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if isinstance(detail, list):
            parts: list[str] = []
            for item in detail:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    location = ".".join(
                        str(part) for part in item.get("loc", []) if part != "body"
                    )
                    message = str(item.get("msg", "")).strip()
                    parts.append(f"{location}: {message}" if location else message)
            joined = "\n".join(part for part in parts if part)
            if joined:
                return joined
        return json.dumps(payload)[:400]

    return f"HTTP {response.status_code}"


# ---------------------------------------------------------------------------
# Authentication (Supabase sign-in -> bearer token for the backend)
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def supabase_auth_client() -> Any | None:
    """Create the Supabase client used only for sign-in / token refresh."""
    url = ((os.getenv("SUPABASE_URL") or _secret_or_none("SUPABASE_URL")) or "").strip()
    # Only the public anon key belongs in the frontend. The service-role key
    # bypasses row-level security and must never be loaded here.
    key = (
        (os.getenv("SUPABASE_ANON_KEY") or _secret_or_none("SUPABASE_ANON_KEY")) or ""
    ).strip()
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception:  # pragma: no cover - depends on live config
        return None


def access_token() -> str:
    return (st.session_state.get("access_token") or "").strip()


#: Refresh this many seconds before the token's ``exp`` so a slow upload or a
#: long agent run cannot start on a token that dies in flight.
TOKEN_EXPIRY_LEEWAY_SECONDS = 60


def _token_expiry(token: str) -> float | None:
    """Read the ``exp`` claim without verifying the signature (the server does)."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError):
        return None
    exp = claims.get("exp") if isinstance(claims, dict) else None
    return float(exp) if isinstance(exp, (int, float)) else None


def token_is_expired(
    token: str, leeway: float = TOKEN_EXPIRY_LEEWAY_SECONDS
) -> bool:
    """True when the token is expired or about to expire."""
    exp = _token_expiry(token)
    if exp is None:
        # Opaque or non-JWT token: only the backend can judge it.
        return False
    return time.time() >= exp - leeway


def is_signed_in() -> bool:
    return bool(access_token())


def sign_out() -> None:
    for key in ("access_token", "refresh_token", "user_email", "user_id"):
        st.session_state.pop(key, None)


def sign_in(email: str, password: str) -> str | None:
    """Sign in and store the session. Returns an error message, or ``None``."""
    client = supabase_auth_client()
    if client is None:
        return (
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY "
            "in .env and restart Streamlit."
        )
    try:
        result = client.auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
    except Exception as exc:
        return f"Sign-in failed: {exc}"

    session = getattr(result, "session", None)
    user = getattr(result, "user", None)
    if session is None or not getattr(session, "access_token", None):
        return "Sign-in failed: no access token was returned."

    st.session_state["access_token"] = session.access_token
    st.session_state["refresh_token"] = getattr(session, "refresh_token", None)
    st.session_state["user_email"] = getattr(user, "email", None) or email.strip()
    st.session_state["user_id"] = getattr(user, "id", None)
    return None


#: Deliberately permissive: "something@domain.tld" without spaces.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MIN_PASSWORD_LENGTH = 8


def validate_signup(email: str, password: str, confirm_password: str) -> str | None:
    """Client-side checks that run before any request to Supabase."""
    if not EMAIL_PATTERN.match((email or "").strip()):
        return "Enter a valid email address, for example you@example.com."
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm_password:
        return "Passwords do not match."
    return None


def _friendly_signup_error(exc: Exception) -> str:
    """Map Supabase sign-up failures onto readable text (never a stack trace)."""
    message = str(exc).lower()
    if "already registered" in message or "already been registered" in message:
        return "That email is already registered. Use the Sign in tab instead."
    if "already exists" in message:
        return "That email is already registered. Use the Sign in tab instead."
    if "password" in message and ("least" in message or "weak" in message):
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if "rate limit" in message or "too many" in message:
        return "Too many sign-up attempts. Wait a minute and try again."
    if "invalid" in message and "email" in message:
        return "That email address was rejected. Check it and try again."
    if "signups not allowed" in message or "disabled" in message:
        return "New sign-ups are currently disabled for this project."
    return "Could not create the account. Please try again in a moment."


def sign_up(
    email: str, password: str, confirm_password: str
) -> tuple[str | None, str | None]:
    """Create an account. Returns ``(error, notice)``; both ``None`` means signed in."""
    email = (email or "").strip()
    problem = validate_signup(email, password, confirm_password)
    if problem:
        return problem, None

    client = supabase_auth_client()
    if client is None:
        return (
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY "
            "in .env and restart Streamlit.",
            None,
        )

    payload: dict[str, Any] = {"email": email, "password": password}
    app_url = resolve_app_url()
    if app_url:
        payload["options"] = {"email_redirect_to": app_url}

    try:
        result = client.auth.sign_up(payload)
    except Exception as exc:
        return _friendly_signup_error(exc), None

    session = getattr(result, "session", None)
    user = getattr(result, "user", None)
    token = getattr(session, "access_token", None) if session else None
    if token:
        # Email confirmation is disabled: the account is usable right away.
        st.session_state["access_token"] = token
        st.session_state["refresh_token"] = getattr(session, "refresh_token", None)
        st.session_state["user_email"] = getattr(user, "email", None) or email
        st.session_state["user_id"] = getattr(user, "id", None)
        return None, None

    identities = getattr(user, "identities", None)
    if user is not None and isinstance(identities, list) and not identities:
        # Supabase reports a fresh user with no identities when the address is
        # already taken and confirmation is on, instead of raising an error.
        return "That email is already registered. Use the Sign in tab instead.", None

    return None, "Check your inbox and confirm your email, then sign in."


def refresh_access_token() -> bool:
    """Exchange the stored refresh token for a new access token."""
    client = supabase_auth_client()
    refresh = st.session_state.get("refresh_token")
    if client is None or not refresh:
        return False
    try:
        result = client.auth.refresh_session(refresh)
    except Exception:
        sign_out()
        return False

    session = getattr(result, "session", None)
    token = getattr(session, "access_token", None) if session else None
    if not token:
        sign_out()
        return False

    st.session_state["access_token"] = token
    st.session_state["refresh_token"] = getattr(session, "refresh_token", refresh)
    return True


def ensure_access_token() -> str:
    """Return a usable access token, refreshing it first when needed.

    Returns an empty string when there is no session and none can be restored.
    """
    token = access_token()
    if token and not token_is_expired(token):
        return token
    if st.session_state.get("refresh_token") and refresh_access_token():
        return access_token()
    sign_out()
    return ""


def auth_headers() -> dict[str, str]:
    token = ensure_access_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _redirect_to_login(message: str) -> None:
    """Drop the session and rerun so the login prompt replaces the workspace."""
    sign_out()
    st.session_state["auth_notice"] = message
    st.rerun()


def require_session() -> str:
    """Return the bearer token for a backend call, or bounce to the login screen."""
    token = ensure_access_token()
    if token:
        return token
    _redirect_to_login("Session expired, please log in again.")
    # st.rerun() halts the run; this is only reached outside a Streamlit context.
    raise BackendError("Authentication required: sign in to continue.", 401)


def api_request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    """Perform an authenticated backend request and return the decoded JSON."""
    url = f"{API_BASE_URL}{path}"
    token = require_session()
    headers = dict(kwargs.pop("headers", {}) or {})
    headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.request(
            method, url, timeout=REQUEST_TIMEOUT, headers=headers, **kwargs
        )
        if response.status_code == 401 and refresh_access_token():
            # Our clock said the token was fine; the server disagreed (revoked
            # session, rotated signing key). One refresh, then one retry.
            headers["Authorization"] = f"Bearer {access_token()}"
            response = requests.request(
                method, url, timeout=REQUEST_TIMEOUT, headers=headers, **kwargs
            )
    except requests.exceptions.ConnectionError as exc:
        raise BackendError(
            f"Cannot reach the InsightForge API at {API_BASE_URL}. "
            "Check that the backend is running and that BACKEND_URL points to it."
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise BackendError(
            f"The request to {path} timed out after {REQUEST_TIMEOUT:.0f}s. "
            "Large documents and agent runs can take a while — retry, or raise "
            "INSIGHTFORGE_TIMEOUT."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise BackendError(f"The request to {path} failed: {exc}") from exc

    if response.status_code == 401:
        # Retry already happened above; the session really is unusable.
        _redirect_to_login("Session expired, please log in again.")

    if not response.ok:
        raise BackendError(_describe_http_error(response), response.status_code)

    try:
        payload = response.json()
    except ValueError as exc:
        raise BackendError(
            f"The backend returned a non-JSON response for {path} "
            f"(HTTP {response.status_code})."
        ) from exc

    if not isinstance(payload, dict):
        raise BackendError(f"Unexpected response shape from {path}: {type(payload).__name__}")
    return payload


def api_health() -> dict[str, Any]:
    return api_request("GET", "/health")


def api_upload_paper(filename: str, data: bytes) -> dict[str, Any]:
    return api_request(
        "POST",
        "/upload/paper",
        files={"file": (filename, data, "application/pdf")},
    )


def api_upload_dataset(filename: str, data: bytes) -> dict[str, Any]:
    return api_request(
        "POST",
        "/upload/dataset",
        files={"file": (filename, data, "text/csv")},
    )


def api_ask_paper(document_id: str, question: str) -> dict[str, Any]:
    return api_request(
        "POST",
        "/paper/qa",
        json={"document_id": document_id, "question": question},
    )


def api_detect_anomalies(
    dataset_id: str,
    contamination: float,
    features: list[str] | None = None,
) -> dict[str, Any]:
    # The user is taken from the bearer token by the backend.
    form: dict[str, Any] = {"contamination": str(contamination)}
    if features:
        form["features"] = features
    return api_request(
        "POST",
        f"/dataset/{dataset_id}/anomalies",
        data=form,
    )


def api_run_agent(
    goal: str,
    document_id: str | None,
    dataset_id: str | None,
) -> dict[str, Any]:
    return api_request(
        "POST",
        "/agent/run",
        json={
            "goal": goal,
            "document_id": document_id or None,
            "dataset_id": dataset_id or None,
        },
    )


def api_list_documents(limit: int = 50) -> dict[str, Any]:
    return api_request("GET", "/documents", params={"limit": limit})


def api_chat_history(document_id: str) -> dict[str, Any]:
    return api_request("GET", f"/chat/history/{document_id}")


def api_save_chat_message(
    document_id: str,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return api_request(
        "POST",
        "/chat/message",
        json={
            "document_id": document_id,
            "role": role,
            "content": content,
            "citations": citations or None,
        },
    )


def api_clear_chat(document_id: str) -> dict[str, Any]:
    return api_request("DELETE", f"/chat/history/{document_id}")


# ---------------------------------------------------------------------------
# Response normalisation
# ---------------------------------------------------------------------------
def normalise_citations(raw: Any) -> list[int]:
    """Accept ``[1, 3]`` or ``[{"page_number": 1, ...}]`` and return unique pages."""
    pages: list[int] = []
    if not isinstance(raw, list):
        return pages
    for item in raw:
        candidate: Any = item
        if isinstance(item, dict):
            candidate = item.get("page_number", item.get("page", item.get("page_num")))
        try:
            page = int(candidate)
        except (TypeError, ValueError):
            continue
        if page > 0 and page not in pages:
            pages.append(page)
    return pages


def history_rows_to_entries(rows: list[Any]) -> list[dict[str, Any]]:
    """Rebuild Q&A pairs from stored ``user``/``assistant`` rows.

    A ``user`` row opens an entry and the next ``assistant`` row fills in its
    answer and citations. An unanswered question (a crash between the two saves)
    or an orphaned answer stays visible instead of disappearing.
    """
    entries: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None

    for row in rows:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or "").strip().lower()
        content = str(row.get("content") or "")

        if role == "user":
            if pending is not None:
                entries.append(pending)
            pending = {
                "question": content,
                "answer": "",
                "citations": [],
                "asked_at": row.get("created_at"),
            }
        elif role == "assistant":
            citations = normalise_citations(row.get("citations"))
            if pending is None:
                entries.append(
                    {
                        "question": "",
                        "answer": content,
                        "citations": citations,
                        "asked_at": row.get("created_at"),
                    }
                )
            else:
                pending["answer"] = content
                pending["citations"] = citations
                entries.append(pending)
                pending = None

    if pending is not None:
        entries.append(pending)
    return entries


def load_chat_history(document_id: str) -> None:
    """Fetch a document's saved conversation into ``qa_history``."""
    try:
        payload = api_chat_history(document_id)
    except BackendError as exc:
        st.session_state["qa_history"] = []
        st.session_state["chat_load_error"] = str(exc)
        # Mark it loaded anyway: retrying every rerun would hammer a failing API.
        st.session_state["chat_history_loaded_for"] = document_id
        return

    rows = payload.get("messages")
    st.session_state["qa_history"] = history_rows_to_entries(
        rows if isinstance(rows, list) else []
    )
    st.session_state["chat_history_loaded_for"] = document_id


def ensure_chat_history_loaded() -> None:
    """Load persisted history, once per document per Streamlit session."""
    document_id = st.session_state.get("document_id")
    if not document_id or not is_signed_in():
        return
    if st.session_state.get("chat_history_loaded_for") == document_id:
        return
    load_chat_history(str(document_id))


def persist_chat_turn(document_id: str, entry: dict[str, Any]) -> None:
    """Save a question and its answer; a failed write never hides the answer."""
    pages = normalise_citations(entry.get("citations") or [])
    citations = [{"page_number": page} for page in pages] or None
    try:
        api_save_chat_message(document_id, "user", entry.get("question", ""))
        api_save_chat_message(
            document_id, "assistant", entry.get("answer", ""), citations
        )
    except BackendError as exc:
        st.session_state["chat_persist_error"] = str(exc)
        return
    st.session_state["chat_persist_error"] = None


def open_document(document: dict[str, Any]) -> None:
    """Switch the workspace to a previously indexed paper."""
    document_id = str(document.get("id") or "")
    if not document_id:
        return
    st.session_state["document_id"] = document_id
    st.session_state["document_filename"] = document.get("filename") or "document"
    st.session_state["document_pages"] = document.get("total_pages")
    st.session_state["document_chunks"] = document.get("chunk_count")
    st.session_state["qa_history"] = []
    st.session_state["chat_history_loaded_for"] = None
    st.session_state["chat_load_error"] = None
    st.session_state["chat_persist_error"] = None
    st.rerun()


def clear_chat_history() -> None:
    """Delete the active document's conversation from Supabase and this session."""
    document_id = st.session_state.get("document_id")
    if not document_id:
        return

    try:
        api_clear_chat(str(document_id))
    except BackendError as exc:
        st.session_state["chat_persist_error"] = (
            f"Could not clear the saved chat history: {exc}"
        )
        st.rerun()
        return

    st.session_state["qa_history"] = []
    st.session_state["chat_history_loaded_for"] = str(document_id)
    st.session_state["chat_persist_error"] = None
    st.session_state["chat_notice"] = "Chat history cleared for this paper."
    st.rerun()


def normalise_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return summary if isinstance(summary, dict) else {}


def normalise_anomalies(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload.get("sample_flagged_rows")
    if not isinstance(rows, list):
        rows = payload.get("sample_outliers")
    if not isinstance(rows, list):
        rows = []

    count = payload.get("anomalies_detected", payload.get("anomaly_count", 0))
    percentage = payload.get("anomaly_percentage", 0.0)
    try:
        count_int = int(count or 0)
    except (TypeError, ValueError):
        count_int = 0
    try:
        percentage_float = float(percentage or 0.0)
    except (TypeError, ValueError):
        percentage_float = 0.0

    def _names(key: str) -> list[str]:
        return [str(name) for name in payload.get(key) or []]

    return {
        "count": count_int,
        "percentage": percentage_float,
        "rows": [row for row in rows if isinstance(row, dict)],
        "method": str(payload.get("method", "IsolationForest")),
        "numeric_columns": _names("numeric_columns"),
        "feature_columns": _names("feature_columns") or _names("numeric_columns"),
        "excluded_columns": _names("excluded_columns"),
        "deduplicated_rows": int(payload.get("deduplicated_rows") or 0),
        "contamination": payload.get("contamination"),
        "scored_rows": payload.get("scored_rows"),
        "row_count": payload.get("row_count"),
    }


def step_tool(step: dict[str, Any]) -> str:
    tool = step.get("tool")
    if isinstance(tool, str) and tool:
        return tool
    label = str(step.get("step", "step"))
    return label.split(":", 1)[-1].strip() if ":" in label else label


def step_params(step: dict[str, Any]) -> dict[str, Any]:
    for key in ("arguments", "params"):
        value = step.get(key)
        if isinstance(value, dict):
            return value
    return {}


def step_result(step: dict[str, Any]) -> Any:
    if "result" in step:
        return step["result"]
    return step.get("step")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"


def fmt_float(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def fmt_bytes(size: Any) -> str:
    try:
        amount = float(size)
    except (TypeError, ValueError):
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{amount:.1f} GB"


def fmt_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, default=str)
    return value


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
SESSION_DEFAULTS: dict[str, Any] = {
    "access_token": None,
    "refresh_token": None,
    "user_email": None,
    "user_id": None,
    "document_id": None,
    "document_filename": None,
    "document_chunks": None,
    "document_pages": None,
    "dataset_id": None,
    "dataset_filename": None,
    "dataset_df": None,
    "dataset_summary": {},
    "qa_history": [],
    "executive_report": None,
    "chat_history_loaded_for": None,
    "chat_notice": None,
    "chat_load_error": None,
    "chat_persist_error": None,
    "last_agent_run": None,
    "anomaly_result": None,
    "anomaly_contamination": DEFAULT_CONTAMINATION,
    "health": None,
}


def init_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, (dict, list)) else value


def reset_session() -> None:
    """Clear workspace state but keep the signed-in session."""
    preserved = {
        key: st.session_state.get(key)
        for key in ("access_token", "refresh_token", "user_email", "user_id")
    }
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()
    st.session_state.update(preserved)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
CSS = """
<style>
:root {
    --if-bg: #0b0d12;
    --if-bg-soft: #0f131b;
    --if-panel: #141821;
    --if-panel-2: #1a1f2a;
    --if-border: #262d3a;
    --if-text: #e8ebf2;
    --if-muted: #93a0b5;
    --if-accent: #f0a04b;
    --if-accent-soft: rgba(240, 160, 75, 0.14);
    --if-info: #7cc4ff;
    --if-danger: #ff6b6b;
    --if-ok: #4ade80;
    color-scheme: dark;
}

html, body, .stApp, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(1100px 520px at 12% -10%, rgba(240, 160, 75, 0.10), transparent 60%),
        radial-gradient(900px 480px at 92% 0%, rgba(124, 196, 255, 0.08), transparent 55%),
        var(--if-bg) !important;
    color: var(--if-text) !important;
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, sans-serif;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { right: 1rem; }
.block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1320px; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #10141c 0%, #0c1017 100%) !important;
    border-right: 1px solid var(--if-border);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.6rem; }

.if-brand {
    display: flex; align-items: center; gap: 12px; margin-bottom: 6px;
}
.if-brand-mark {
    width: 42px; height: 42px; border-radius: 12px; flex: 0 0 42px;
    background: linear-gradient(135deg, #f0a04b 0%, #d97706 55%, #b45309 100%);
    display: flex; align-items: center; justify-content: center;
    font-size: 20px; font-weight: 800; color: #16110a;
    box-shadow: 0 8px 24px rgba(240, 160, 75, 0.28);
}
.if-brand-title { font-size: 1.12rem; font-weight: 750; letter-spacing: -0.02em; line-height: 1.1; }
.if-brand-sub { font-size: 0.72rem; color: var(--if-muted); letter-spacing: 0.09em; text-transform: uppercase; }

.if-badge {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 3px 10px; border-radius: 999px; font-size: 0.68rem; font-weight: 650;
    letter-spacing: 0.06em; text-transform: uppercase;
    background: var(--if-accent-soft); color: var(--if-accent);
    border: 1px solid rgba(240, 160, 75, 0.32);
}
.if-badge-ok {
    background: rgba(74, 222, 128, 0.12); color: var(--if-ok);
    border-color: rgba(74, 222, 128, 0.32);
}
.if-badge-off {
    background: rgba(255, 107, 107, 0.12); color: var(--if-danger);
    border-color: rgba(255, 107, 107, 0.32);
}
.if-badge-muted {
    background: rgba(147, 160, 181, 0.10); color: var(--if-muted);
    border-color: rgba(147, 160, 181, 0.24);
}

.if-side-label {
    display: flex; align-items: center; gap: 8px;
    margin: 22px 0 8px; font-size: 0.78rem; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase; color: var(--if-muted);
}
.if-side-label span.if-step {
    width: 20px; height: 20px; border-radius: 6px; font-size: 0.7rem;
    background: var(--if-panel-2); border: 1px solid var(--if-border);
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--if-accent); letter-spacing: 0;
}

.if-status-line {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 8px 10px; margin-top: 8px; border-radius: 10px;
    background: var(--if-panel); border: 1px solid var(--if-border);
    font-size: 0.76rem; color: var(--if-muted);
}
.if-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
.if-dot-ok { background: var(--if-ok); box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.16); }
.if-dot-off { background: var(--if-danger); box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.16); }
.if-dot-unknown { background: var(--if-muted); }

/* ---------- Hero ---------- */
.if-hero {
    position: relative; overflow: hidden;
    border: 1px solid var(--if-border); border-radius: 18px;
    padding: 22px 24px; margin-bottom: 20px;
    background:
        radial-gradient(700px 220px at 0% 0%, rgba(240, 160, 75, 0.13), transparent 65%),
        linear-gradient(180deg, var(--if-panel) 0%, #12161e 100%);
}
.if-hero h1 {
    margin: 8px 0 6px; font-size: 1.85rem; font-weight: 780;
    letter-spacing: -0.035em; line-height: 1.15; color: #fff;
}
.if-hero p { margin: 0; color: var(--if-muted); font-size: 0.9rem; max-width: 74ch; }

/* ---------- Cards & metrics ---------- */
.if-metric {
    border: 1px solid var(--if-border); border-radius: 14px; padding: 14px 16px;
    background: linear-gradient(180deg, var(--if-panel-2) 0%, var(--if-panel) 100%);
    transition: all 0.2s ease-in-out; height: 100%;
}
.if-metric:hover {
    transform: translateY(-2px); transition: all 0.2s ease-in-out;
    border-color: rgba(240, 160, 75, 0.45);
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.36);
}
.if-metric-label {
    font-size: 0.7rem; font-weight: 650; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--if-muted); margin-bottom: 6px;
}
.if-metric-value {
    font-size: 1.7rem; font-weight: 760; letter-spacing: -0.03em;
    color: var(--if-text); line-height: 1.15;
}
.if-metric-hint { font-size: 0.74rem; color: var(--if-muted); margin-top: 4px; }
.if-metric-danger .if-metric-value { color: var(--if-danger); }
.if-metric-accent .if-metric-value { color: var(--if-accent); }
.if-metric-info .if-metric-value { color: var(--if-info); }

.if-card {
    border: 1px solid var(--if-border); border-radius: 16px; padding: 18px 20px;
    background: var(--if-panel); animation: ifRise 0.35s ease-out both;
}
@keyframes ifRise {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

/* Animated answer/report surfaces */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    animation: ifRise 0.32s ease-out both;
}

/* ---------- Answer / citations ---------- */
.if-answer-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px; margin-bottom: 10px;
}
.if-answer-title { font-size: 0.76rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--if-muted); }
.if-citations { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.if-cite {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 999px; font-size: 0.72rem; font-weight: 650;
    background: rgba(124, 196, 255, 0.10); color: var(--if-info);
    border: 1px solid rgba(124, 196, 255, 0.28);
    transition: all 0.2s ease-in-out;
}
.if-cite:hover { transform: translateY(-2px); background: rgba(124, 196, 255, 0.18); }

/* ---------- Agent trace ---------- */
.if-step-row {
    border-left: 2px solid rgba(240, 160, 75, 0.35);
    padding: 2px 0 12px 14px; margin-left: 4px;
}
.if-step-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.if-step-index {
    font-size: 0.66rem; font-weight: 700; color: var(--if-accent);
    background: var(--if-accent-soft); border: 1px solid rgba(240, 160, 75, 0.3);
    border-radius: 6px; padding: 1px 7px; letter-spacing: 0.05em;
}
.if-step-tool { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 0.82rem; font-weight: 600; color: var(--if-text); }
.if-step-iter { font-size: 0.7rem; color: var(--if-muted); }
.if-step-error { color: var(--if-danger); font-size: 0.78rem; margin-top: 4px; }

/* ---------- Empty state ---------- */
.if-empty {
    border: 1px dashed var(--if-border); border-radius: 16px;
    padding: 34px 24px; text-align: center; background: rgba(20, 24, 33, 0.5);
}
.if-empty-icon { font-size: 1.9rem; margin-bottom: 8px; }
.if-empty h4 { margin: 0 0 6px; font-size: 1rem; color: var(--if-text); }
.if-empty p { margin: 0; font-size: 0.85rem; color: var(--if-muted); }

/* ---------- Inputs & buttons ---------- */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: var(--if-panel-2) !important; color: var(--if-text) !important;
    border: 1px solid var(--if-border) !important; border-radius: 10px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: rgba(240, 160, 75, 0.6) !important;
    box-shadow: 0 0 0 2px rgba(240, 160, 75, 0.16) !important;
}
[data-testid="stFileUploaderDropzone"] {
    background: var(--if-panel) !important; border: 1px dashed var(--if-border) !important;
    border-radius: 12px !important;
}
.stButton > button, .stDownloadButton > button {
    border-radius: 10px; border: 1px solid var(--if-border);
    background: var(--if-panel-2); color: var(--if-text); font-weight: 600;
    transition: all 0.2s ease-in-out;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-2px); transition: all 0.2s ease-in-out;
    border-color: rgba(240, 160, 75, 0.55); color: #fff;
    box-shadow: 0 10px 22px rgba(0, 0, 0, 0.32);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #f0a04b 0%, #d97706 100%);
    color: #16110a; border: none;
}
.stButton > button[kind="primary"]:hover { color: #0b0d12; box-shadow: 0 12px 26px rgba(240, 160, 75, 0.32); }

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px; border-bottom: 1px solid var(--if-border); padding-bottom: 4px;
}
.stTabs [data-baseweb="tab"] {
    height: 42px; border-radius: 10px 10px 0 0; padding: 0 16px;
    font-weight: 600; font-size: 0.88rem; color: var(--if-muted);
    background: transparent; transition: all 0.2s ease-in-out;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--if-text); background: rgba(255, 255, 255, 0.03); }
.stTabs [aria-selected="true"] {
    color: var(--if-accent) !important;
    background: var(--if-accent-soft) !important;
    border-bottom: 2px solid var(--if-accent) !important;
}

/* ---------- Misc ---------- */
[data-testid="stDataFrame"] { border: 1px solid var(--if-border); border-radius: 12px; }
[data-testid="stExpander"] {
    border: 1px solid var(--if-border) !important; border-radius: 12px !important;
    background: var(--if-panel) !important;
}
hr { border-color: var(--if-border) !important; }
h2, h3, h4 { letter-spacing: -0.02em; color: var(--if-text); }
a { color: var(--if-info); }
code { background: rgba(255, 255, 255, 0.06); border-radius: 5px; padding: 1px 5px; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2b3342; border-radius: 8px; }
::-webkit-scrollbar-thumb:hover { background: #3a4457; }
</style>
"""


def inject_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Small UI helpers
# ---------------------------------------------------------------------------
def metric_card(label: str, value: str, hint: str = "", variant: str = "") -> None:
    variant_class = f" if-metric-{variant}" if variant else ""
    hint_html = f'<div class="if-metric-hint">{esc(hint)}</div>' if hint else ""
    st.markdown(
        f"""
        <div class="if-metric{variant_class}">
            <div class="if-metric-label">{esc(label)}</div>
            <div class="if-metric-value">{esc(value)}</div>
            {hint_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(text: str, variant: str = "") -> str:
    variant_class = f" if-badge-{variant}" if variant else ""
    return f'<span class="if-badge{variant_class}">{esc(text)}</span>'


def empty_state(icon: str, title: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="if-empty">
            <div class="if-empty-icon">{icon}</div>
            <h4>{esc(title)}</h4>
            <p>{esc(message)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def citation_pills(pages: list[int]) -> None:
    if not pages:
        st.markdown(
            '<div class="if-citations">'
            + badge("no page citations returned", "muted")
            + "</div>",
            unsafe_allow_html=True,
        )
        return
    pills = "".join(f'<span class="if-cite">📄 Page {page}</span>' for page in pages)
    st.markdown(f'<div class="if-citations">{pills}</div>', unsafe_allow_html=True)


def section_heading(text: str, caption: str = "") -> None:
    st.markdown(f"#### {text}")
    if caption:
        st.caption(caption)


# ---------------------------------------------------------------------------
# Local CSV / summary helpers
# ---------------------------------------------------------------------------
def parse_csv(data: bytes) -> pd.DataFrame | None:
    """Best-effort local parse so charts and previews work client-side."""
    for encoding in CSV_ENCODINGS:
        try:
            frame = pd.read_csv(io.BytesIO(data), encoding=encoding, low_memory=False)
        except Exception:
            continue
        if frame.shape[1] == 0:
            continue
        frame.columns = [str(column).strip() for column in frame.columns]
        return frame
    return None


def stats_dataframe(summary: dict[str, Any]) -> pd.DataFrame:
    stats = summary.get("numeric_summary")
    if not isinstance(stats, dict):
        stats = summary.get("summary_stats")
    if not isinstance(stats, dict) or not stats:
        return pd.DataFrame()
    try:
        frame = pd.DataFrame(stats)
    except Exception:
        return pd.DataFrame()
    if frame.empty:
        return pd.DataFrame()
    frame.index = [str(index) for index in frame.index]
    frame.index.name = "statistic"
    return frame.reset_index()


def column_profile(summary: dict[str, Any], df: pd.DataFrame | None) -> pd.DataFrame:
    columns = summary.get("columns")
    if isinstance(columns, list) and columns and isinstance(columns[0], dict):
        return pd.DataFrame(columns)

    if df is None:
        return pd.DataFrame()

    row_count = max(len(df), 1)
    return pd.DataFrame(
        [
            {
                "name": str(name),
                "dtype": str(df[name].dtype),
                "non_null": int(df[name].notna().sum()),
                "missing": int(df[name].isna().sum()),
                "missing_pct": round(float(df[name].isna().sum()) / row_count * 100, 2),
                "unique": int(df[name].nunique(dropna=True)),
            }
            for name in df.columns
        ]
    )


def is_leaky_column(name: Any) -> bool:
    """True when a column name marks it as a label, target or identifier."""
    lowered = str(name).strip().lower()
    return any(marker in lowered for marker in LEAKY_COLUMN_MARKERS)


def model_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return ``(modelling features, excluded leaky columns)`` for a dataframe."""
    excluded = [str(name) for name in df.columns if is_leaky_column(name)]
    excluded_set = set(excluded)
    features = [
        str(name)
        for name in df.select_dtypes(include="number").columns
        if str(name) not in excluded_set
    ]
    return features, excluded


def dataset_metrics(df: pd.DataFrame | None, summary: dict[str, Any]) -> dict[str, Any]:
    if df is not None:
        rows = int(df.shape[0])
        cols = int(df.shape[1])
        missing = int(df.isna().sum().sum())
        numeric_columns, _ = model_feature_columns(df)
    else:
        rows = int(summary.get("row_count", 0) or 0)
        cols = int(summary.get("col_count", 0) or 0)
        missing_map = summary.get("missing_values")
        missing = (
            int(sum(int(value) for value in missing_map.values()))
            if isinstance(missing_map, dict)
            else int(summary.get("total_missing", 0) or 0)
        )
        numeric_columns = [str(name) for name in summary.get("numeric_columns") or []]

    cells = rows * cols
    rate = (missing / cells * 100) if cells else 0.0
    return {
        "rows": rows,
        "cols": cols,
        "missing": missing,
        "missing_rate": rate,
        "numeric_columns": numeric_columns,
    }


def build_figure(df: pd.DataFrame, x: str, y: str | None, kind: str):
    """Build the requested Plotly figure with a consistent dark theme."""
    plot_df = df
    sampled = False
    if len(plot_df) > MAX_PLOT_ROWS:
        plot_df = plot_df.sample(MAX_PLOT_ROWS, random_state=42)
        sampled = True

    if kind == "Histogram":
        figure = px.histogram(plot_df, x=x, nbins=40, color_discrete_sequence=PLOT_COLORWAY)
    elif kind == "Scatter":
        figure = px.scatter(
            plot_df,
            x=x,
            y=y,
            color_discrete_sequence=PLOT_COLORWAY,
            opacity=0.82,
        )
    elif kind == "Line":
        ordered = plot_df.sort_values(by=x, kind="stable")
        figure = px.line(ordered, x=x, y=y, color_discrete_sequence=PLOT_COLORWAY)
    else:  # Bar
        figure = px.bar(plot_df, x=x, y=y, color_discrete_sequence=PLOT_COLORWAY)

    figure.update_layout(
        template=PLOTLY_TEMPLATE,
        colorway=PLOT_COLORWAY,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", color="#e8ebf2", size=12),
        margin=dict(l=12, r=12, t=44, b=12),
        hoverlabel=dict(
            bgcolor="#1a1f2a",
            bordercolor="#2b3342",
            font=dict(color="#e8ebf2", family="Inter, Segoe UI, sans-serif"),
        ),
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
    )
    figure.update_xaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.12)")
    figure.update_yaxes(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.12)")
    return figure, sampled


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_health() -> None:
    health = st.session_state.get("health")
    if not isinstance(health, dict):
        st.markdown(
            '<div class="if-status-line"><span><span class="if-dot if-dot-unknown"></span>'
            "Backend status unknown</span></div>",
            unsafe_allow_html=True,
        )
        return
    if health.get("ok"):
        detail = esc(health.get("model", "—"))
        cached = health.get("cached_datasets", 0)
        st.markdown(
            '<div class="if-status-line">'
            '<span><span class="if-dot if-dot-ok"></span>API online</span>'
            f'<span>{detail} · {fmt_int(cached)} cached</span></div>',
            unsafe_allow_html=True,
        )
    else:
        error_text = str(health.get("error") or "Connection failed")
        error_line = error_text.splitlines()[0] if error_text.splitlines() else "Connection failed"
        st.markdown(
            '<div class="if-status-line">'
            '<span><span class="if-dot if-dot-off"></span>API offline</span>'
            f'<span>{esc(error_line)[:60]}</span></div>',
            unsafe_allow_html=True,
        )


def refresh_health() -> None:
    try:
        payload = api_health()
    except BackendError as exc:
        st.session_state["health"] = {"ok": False, "error": str(exc)}
        return
    st.session_state["health"] = {
        "ok": str(payload.get("status", "")).lower() == "ok",
        "model": payload.get("model", "—"),
        "cached_datasets": payload.get("cached_datasets", 0),
    }


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="if-brand">
                <div class="if-brand-mark">IF</div>
                <div>
                    <div class="if-brand-title">InsightForge</div>
                    <div class="if-brand-sub">Research · Data · Agents</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="margin: 10px 0 4px;">{badge("FastAPI · Groq · pgvector")}</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="if-side-label">Account</div>', unsafe_allow_html=True)
        if is_signed_in():
            st.success(
                f"Signed in as **{st.session_state.get('user_email') or 'user'}**",
                icon="✅",
            )
            st.caption(f"user id · `{st.session_state.get('user_id') or '—'}`")
            if st.button("Sign out", width="stretch", key="sign_out_button"):
                sign_out()
                st.rerun()
        else:
            notice = st.session_state.pop("auth_notice", None)
            if notice:
                st.warning(notice)
            sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Sign up"])
            with sign_in_tab:
                with st.form("sign_in_form"):
                    email = st.text_input("Email", key="sign_in_email")
                    password = st.text_input(
                        "Password", type="password", key="sign_in_password"
                    )
                    submitted = st.form_submit_button("Sign in", type="primary")
                if submitted:
                    error = sign_in(email, password)
                    if error:
                        st.error(error)
                    else:
                        st.rerun()
            with sign_up_tab:
                with st.form("sign_up_form"):
                    new_email = st.text_input("Email", key="sign_up_email")
                    new_password = st.text_input(
                        "Password",
                        type="password",
                        key="sign_up_password",
                        help=f"At least {MIN_PASSWORD_LENGTH} characters.",
                    )
                    confirm_password = st.text_input(
                        "Confirm password", type="password", key="sign_up_confirm"
                    )
                    sign_up_submitted = st.form_submit_button(
                        "Create account", type="primary"
                    )
                if sign_up_submitted:
                    sign_up_error, sign_up_notice = sign_up(
                        new_email, new_password, confirm_password
                    )
                    if sign_up_error:
                        st.error(sign_up_error)
                    elif sign_up_notice:
                        st.success(sign_up_notice, icon="📧")
                    else:
                        st.rerun()
            st.caption(
                "Sign in or create an account. The backend derives your user id "
                "from the access token, so every document and query is scoped to you."
            )
        st.caption(f"API · `{API_BASE_URL}`")

        if is_signed_in():
            if st.button(
                "↻ Refresh backend status", width="stretch", key="refresh_health"
            ):
                refresh_health()
            render_health()

        st.divider()

        # ----- Section 1: PDF ingestion -----------------------------------
        st.markdown(
            '<div class="if-side-label"><span class="if-step">1</span>Paper ingestion</div>',
            unsafe_allow_html=True,
        )
        documents: list[dict[str, Any]] = []
        if is_signed_in():
            try:
                listing = api_list_documents()
                raw_documents = listing.get("documents")
                if isinstance(raw_documents, list):
                    documents = [
                        doc for doc in raw_documents if isinstance(doc, dict)
                    ]
            except BackendError:
                # A broken listing must not block indexing a fresh paper.
                documents = []

        if documents:
            choices: dict[str, dict[str, Any]] = {}
            for document in documents:
                label = str(document.get("filename") or "document")
                pages = document.get("total_pages")
                if pages:
                    label += f" · {fmt_int(pages)}p"
                choices[label] = document

            picked = st.selectbox(
                "Open an indexed paper",
                list(choices),
                index=None,
                placeholder="Reopen a paper from an earlier session…",
                key="open_document_label",
            )
            if st.button("📂 Open paper", width="stretch", key="open_document_button"):
                if picked:
                    open_document(choices[picked])
                else:
                    st.warning("Choose a paper first.")

        uploaded_pdf = st.file_uploader(
            "Upload a research paper (PDF)", type=["pdf"], key="pdf_uploader"
        )
        if st.button(
            "📥 Index document",
            width="stretch",
            type="primary",
            key="index_pdf_button",
        ):
            if uploaded_pdf is None:
                st.warning("Choose a PDF first.")
            else:
                with st.status("Indexing paper…", expanded=True) as status:
                    st.write("Uploading PDF and extracting text…")
                    try:
                        payload = api_upload_paper(
                            uploaded_pdf.name,
                            uploaded_pdf.getvalue(),
                        )
                        chunks = payload.get(
                            "chunks_indexed",
                            payload.get("chunk_count", payload.get("chunks", 0)),
                        )
                        st.write("Generating MiniLM embeddings…")
                        st.write("Storing document and chunk rows…")
                        status.update(
                            label=f"Indexed · {fmt_int(chunks)} chunks",
                            state="complete",
                            expanded=False,
                        )
                        st.session_state["document_id"] = payload.get("document_id")
                        st.session_state["document_filename"] = payload.get(
                            "filename", uploaded_pdf.name
                        )
                        st.session_state["document_chunks"] = chunks
                        st.session_state["document_pages"] = payload.get("total_pages")
                        st.session_state["qa_history"] = []
                        st.session_state["chat_history_loaded_for"] = payload.get(
                            "document_id"
                        )
                        st.session_state["chat_notice"] = None
                    except BackendError as exc:
                        status.update(label="Indexing failed", state="error", expanded=True)
                        show_backend_error(exc)

        if st.session_state.get("document_id"):
            pages = st.session_state.get("document_pages")
            chunk_label = fmt_int(st.session_state.get("document_chunks") or 0)
            st.markdown(
                '<div class="if-status-line">'
                f'<span>📄 {esc(st.session_state.get("document_filename") or "document")}</span>'
                f'<span>{chunk_label} chunks'
                + (f" · {fmt_int(pages)}p" if pages else "")
                + "</span></div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "🗑 Clear chat",
                width="stretch",
                key="clear_chat_button",
                help=(
                    "Delete this paper's saved conversation from Supabase and "
                    "from this session."
                ),
            ):
                clear_chat_history()
        else:
            st.caption("No paper indexed yet.")

        st.divider()

        # ----- Section 2: CSV ingestion -----------------------------------
        st.markdown(
            '<div class="if-side-label"><span class="if-step">2</span>Dataset ingestion</div>',
            unsafe_allow_html=True,
        )
        uploaded_csv = st.file_uploader("Upload a dataset (CSV)", type=["csv"], key="csv_uploader")
        if st.button(
            "📊 Load dataset",
            width="stretch",
            type="primary",
            key="load_dataset_button",
        ):
            if uploaded_csv is None:
                st.warning("Choose a CSV first.")
            else:
                with st.status("Loading dataset…", expanded=True) as status:
                    st.write("Uploading CSV and computing EDA summary…")
                    raw_bytes = uploaded_csv.getvalue()
                    try:
                        payload = api_upload_dataset(
                            uploaded_csv.name, raw_bytes
                        )
                        st.write("Caching dataframe for analysis…")
                        frame = parse_csv(raw_bytes)
                        status.update(
                            label="Dataset ready", state="complete", expanded=False
                        )
                        st.session_state["dataset_id"] = payload.get("dataset_id")
                        st.session_state["dataset_filename"] = payload.get(
                            "filename", uploaded_csv.name
                        )
                        st.session_state["dataset_summary"] = normalise_summary(payload)
                        st.session_state["dataset_df"] = frame
                        st.session_state["anomaly_result"] = None
                    except BackendError as exc:
                        status.update(label="Loading failed", state="error", expanded=True)
                        show_backend_error(exc)

        frame = st.session_state.get("dataset_df")
        if st.session_state.get("dataset_id"):
            summary = st.session_state.get("dataset_summary") or {}
            metrics = dataset_metrics(frame if isinstance(frame, pd.DataFrame) else None, summary)
            st.markdown(
                '<div class="if-status-line">'
                f'<span>📊 {esc(st.session_state.get("dataset_filename") or "dataset")}</span>'
                f'<span>{fmt_int(metrics["rows"])} × {fmt_int(metrics["cols"])}</span></div>',
                unsafe_allow_html=True,
            )
            if isinstance(frame, pd.DataFrame):
                _, excluded_now = model_feature_columns(frame)
                if excluded_now:
                    st.caption("Excluded from model: " + ", ".join(excluded_now))
        else:
            st.caption("No dataset loaded yet.")

        st.divider()
        if st.button("🧹 Reset session", width="stretch", key="reset_session"):
            reset_session()
            st.rerun()


# ---------------------------------------------------------------------------
# Tab 1: Research paper Q&A
# ---------------------------------------------------------------------------
def render_paper_tab() -> None:
    document_id = st.session_state.get("document_id")
    ensure_chat_history_loaded()
    if not document_id:
        st.markdown("## 📄 Research Paper Q&A")
        empty_state(
            "📄",
            "No paper indexed yet",
            "Upload a PDF in the sidebar and press “Index document” to enable retrieval-augmented Q&A.",
        )
        return

    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown("## 📄 Research Paper Q&A")
        st.caption(
            f"Answering from `{st.session_state.get('document_filename')}` · "
            f"{fmt_int(st.session_state.get('document_chunks') or 0)} indexed chunks"
        )
    with header_cols[1]:
        pages = st.session_state.get("document_pages")
        st.markdown(
            f'<div style="text-align:right; padding-top: 14px;">'
            f'{badge(f"{fmt_int(pages)} pages" if pages else "document ready", "ok")}</div>',
            unsafe_allow_html=True,
        )

    notice = st.session_state.pop("chat_notice", None)
    if notice:
        st.success(notice, icon="💾")
    load_error = st.session_state.pop("chat_load_error", None)
    if load_error:
        st.warning(
            "Saved chat history could not be loaded, so this thread starts empty. "
            f"{load_error}"
        )
    persist_error = st.session_state.pop("chat_persist_error", None)
    if persist_error:
        st.warning(
            "This conversation is not being saved, so it will be gone after a "
            f"reload. {persist_error}"
        )

    history: list[dict[str, Any]] = st.session_state.get("qa_history") or []
    if not history:
        empty_state(
            "🔍",
            "Ask your first question",
            "Answers are grounded in the retrieved passages; every claim comes with page citations.",
        )

    for entry in history:
        with st.chat_message("user"):
            st.markdown(entry.get("question", ""))
        with st.chat_message("assistant", avatar="🔎"):
            with st.container(border=True):
                st.markdown(
                    f'<div class="if-answer-head">'
                    f'<span class="if-answer-title">Grounded answer</span>'
                    f'{badge("pgvector · MiniLM", "muted")}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(entry.get("answer") or "_No answer returned._")
                citation_pills(entry.get("citations") or [])

    question = st.chat_input("Ask anything about this paper…", key="paper_question_input")
    if not question:
        return

    question = question.strip()
    if not question:
        return

    with st.spinner("Retrieving passages and composing an answer…"):
        try:
            payload = api_ask_paper(str(document_id), question)
        except BackendError as exc:
            show_backend_error(exc)
            return

    entry = {
        "question": question,
        "answer": payload.get("answer", ""),
        "citations": normalise_citations(payload.get("citations")),
        "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    history.append(entry)
    st.session_state["qa_history"] = history
    persist_chat_turn(str(document_id), entry)
    st.rerun()


# ---------------------------------------------------------------------------
# Tab 2: Tabular analytics & Plotly
# ---------------------------------------------------------------------------
def render_analytics_tab() -> None:
    st.markdown("## 📊 Tabular Analytics")
    st.caption("Exploratory statistics and an interactive Plotly studio over the active dataset.")

    frame = st.session_state.get("dataset_df")
    summary = st.session_state.get("dataset_summary") or {}
    dataset_id = st.session_state.get("dataset_id")

    if not dataset_id:
        empty_state(
            "📊",
            "No dataset loaded",
            "Upload a CSV in the sidebar and press “Load dataset” to unlock exploratory analytics.",
        )
        return

    if not isinstance(frame, pd.DataFrame):
        st.warning(
            "The CSV was accepted by the backend but could not be parsed locally, "
            "so charts are unavailable. Re-upload the file to retry."
        )
        frame = None

    metrics = dataset_metrics(frame, summary)

    metric_cols = st.columns(4)
    with metric_cols[0]:
        metric_card("Total rows", fmt_int(metrics["rows"]), "records in dataset")
    with metric_cols[1]:
        metric_card("Total columns", fmt_int(metrics["cols"]), "features detected", "info")
    with metric_cols[2]:
        metric_card(
            "Missing value rate",
            f"{metrics['missing_rate']:.2f}%",
            f"{fmt_int(metrics['missing'])} empty cells",
            "danger" if metrics["missing_rate"] > 5 else "accent",
        )
    with metric_cols[3]:
        metric_card(
            "Numeric columns",
            fmt_int(len(metrics["numeric_columns"])),
            "eligible for modelling",
        )

    st.write("")

    if frame is not None:
        section_heading("Dataset preview", f"First {min(MAX_PREVIEW_ROWS, len(frame))} rows")
        preview = frame.head(MAX_PREVIEW_ROWS).copy()
        st.dataframe(preview, width="stretch", height=300)

        with st.expander("Column profile & descriptive statistics"):
            profile = column_profile(summary, frame)
            if profile.empty:
                st.info("No column profile available for this dataset.")
            else:
                st.dataframe(profile, width="stretch", hide_index=True)
            stats = stats_dataframe(summary)
            if not stats.empty:
                st.markdown("**Descriptive statistics**")
                st.dataframe(stats, width="stretch", hide_index=True)

        st.write("")
        section_heading("Plotly studio", "Pick axes and a chart type; hover for exact values.")
        with st.container(border=True):
            numeric_columns = metrics["numeric_columns"]
            if not numeric_columns:
                st.info(
                    "This dataset has no numeric columns, so there is nothing to plot. "
                    "Anomaly detection is unavailable for the same reason."
                )
                return

            control_cols = st.columns([1, 1, 1])
            with control_cols[0]:
                x_axis = st.selectbox("X axis", numeric_columns, key="plot_x_axis")
            with control_cols[1]:
                y_options = ["(none)"] + [col for col in numeric_columns if col != x_axis]
                y_choice = st.selectbox("Y axis", y_options, key="plot_y_axis")
            with control_cols[2]:
                chart_type = st.selectbox(
                    "Plot type", ["Scatter", "Line", "Bar", "Histogram"], key="plot_type"
                )

            y_axis = None if y_choice == "(none)" else y_choice
            if chart_type != "Histogram" and y_axis is None:
                st.info("Select a Y axis to render this chart type.")
            else:
                try:
                    figure, sampled = build_figure(frame, x_axis, y_axis, chart_type)
                except Exception as exc:  # malformed column values
                    st.error(f"Could not build the chart: {exc}")
                else:
                    st.plotly_chart(figure, width="stretch", theme=None)
                    if sampled:
                        st.caption(
                            f"Showing a random sample of {fmt_int(MAX_PLOT_ROWS)} rows "
                            f"for performance (dataset has {fmt_int(len(frame))})."
                        )
    else:
        with st.expander("Backend summary"):
            st.json(summary)


# ---------------------------------------------------------------------------
# Tab 3: Anomaly detection
# ---------------------------------------------------------------------------
def render_anomaly_tab() -> None:
    st.markdown("## 🚨 Anomaly Detection")
    st.caption(
        "IsolationForest over the numeric columns. The scan runs server-side on the "
        "dataframe cached by the worker that ingested this dataset."
    )

    dataset_id = st.session_state.get("dataset_id")
    if not dataset_id:
        empty_state(
            "🚨",
            "No dataset loaded",
            "Load a CSV in the sidebar first — anomaly detection needs numeric data.",
        )
        return

    frame_for_model = st.session_state.get("dataset_df")
    if isinstance(frame_for_model, pd.DataFrame):
        feature_options, local_excluded = model_feature_columns(frame_for_model)
    else:
        feature_options, local_excluded = [], []

    if local_excluded:
        st.caption(
            "**Excluded from model:** "
            + ", ".join(f"`{name}`" for name in local_excluded)
            + " (label, target, truth or id columns)"
        )

    if feature_options:
        selected_features = st.multiselect(
            "Features used by IsolationForest",
            options=feature_options,
            default=feature_options,
            key="anomaly_feature_selection",
            help="Only these numeric columns are used for scoring. Label columns stay excluded.",
        )
    else:
        selected_features = []

    controls = st.columns([1, 1, 2])
    with controls[0]:
        stored = float(st.session_state.get("anomaly_contamination", DEFAULT_CONTAMINATION))
        stored = min(max(stored, MIN_CONTAMINATION), MAX_CONTAMINATION)
        contamination = st.slider(
            "Contamination",
            min_value=MIN_CONTAMINATION,
            max_value=MAX_CONTAMINATION,
            value=stored,
            step=0.01,
            key="anomaly_contamination_slider",
            help="Expected share of outliers in the data",
        )
        st.session_state["anomaly_contamination"] = contamination
    with controls[1]:
        st.write("")
        st.write("")
        scan_clicked = st.button(
            "🚨 Execute anomaly scan",
            type="primary",
            width="stretch",
            key="run_anomaly_scan",
        )
    with controls[2]:
        st.write("")
        metrics = dataset_metrics(
            st.session_state.get("dataset_df")
            if isinstance(st.session_state.get("dataset_df"), pd.DataFrame)
            else None,
            st.session_state.get("dataset_summary") or {},
        )
        st.caption(
            f"Dataset `{st.session_state.get('dataset_filename')}` · "
            f"{fmt_int(metrics['rows'])} rows · {fmt_int(len(metrics['numeric_columns']))} numeric columns"
        )

    if scan_clicked:
        with st.spinner("Fitting IsolationForest…"):
            try:
                payload = api_detect_anomalies(
                    str(dataset_id), contamination, list(selected_features)
                )
            except BackendError as exc:
                if exc.status_code == 404:
                    st.error(
                        f"{exc}\n\nThe dataset cache was cleared (server restart or a "
                        "different worker). Re-upload the CSV in the sidebar and try again."
                    )
                else:
                    show_backend_error(exc)
                st.session_state["anomaly_result"] = None
            else:
                st.session_state["anomaly_result"] = normalise_anomalies(payload)

    result = st.session_state.get("anomaly_result")
    if not isinstance(result, dict):
        empty_state(
            "🔬",
            "No scan yet",
            "Run a scan to flag multi-dimensional outliers and inspect the sample rows.",
        )
        return

    callouts = st.columns(3)
    with callouts[0]:
        metric_card("Flagged outliers", fmt_int(result["count"]), "rows scored as anomalies", "danger")
    with callouts[1]:
        metric_card("Outlier percentage", f"{result['percentage']:.2f}%", "of all rows", "accent")
    with callouts[2]:
        applied = result.get("contamination")
        applied = float(applied) if isinstance(applied, (int, float)) else contamination
        metric_card("Method", result["method"], f"contamination {applied:.2f}", "info")

    result_excluded = result.get("excluded_columns") or []
    if result_excluded:
        st.caption(
            "**Excluded from model:** " + ", ".join(f"`{name}`" for name in result_excluded)
        )
    model_features = result.get("feature_columns") or []
    if model_features:
        st.caption(
            f"IsolationForest fitted on {len(model_features)} feature(s): "
            + ", ".join(f"`{name}`" for name in model_features)
        )
    if result.get("deduplicated_rows"):
        st.caption(
            f"Dropped {fmt_int(result['deduplicated_rows'])} exact duplicate row(s) "
            "before fitting."
        )

    st.write("")

    frame = st.session_state.get("dataset_df")
    rows = result.get("rows") or []

    if rows and isinstance(frame, pd.DataFrame) and "row_index" in rows[0]:
        section_heading(
            "Flagged rows",
            "Outliers are pinned to the top; anomaly_score is the IsolationForest decision function.",
        )
        indexes: list[int] = []
        scores: dict[int, Any] = {}
        for row in rows:
            try:
                index = int(row.get("row_index"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(frame):
                indexes.append(index)
                scores[index] = row.get("anomaly_score")

        view = frame.copy()
        view.insert(0, "status", ["🚨 outlier" if i in indexes else "" for i in view.index])
        view.insert(1, "anomaly_score", [scores.get(i) for i in view.index])
        flagged_rows = view[view["status"] != ""]
        preview_rows = pd.concat([flagged_rows, view[view["status"] == ""].head(15)])
        preview_rows = preview_rows.reset_index().rename(columns={"index": "row_index"})

        def highlight_flagged(row: pd.Series) -> list[str]:
            style = "background-color: rgba(255, 107, 107, 0.16); color: #ffd9d9;"
            return [style if row.get("status") else "" for _ in row]

        st.dataframe(
            preview_rows.style.apply(highlight_flagged, axis=1),
            width="stretch",
            hide_index=True,
            height=360,
        )
        if len(indexes) > len(flagged_rows):
            st.caption("Some flagged rows were dropped from the view; reload to refresh the cache.")
    elif rows:
        section_heading("Flagged sample rows", "Returned by the backend scan.")
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=360)
    else:
        st.info("The scan returned no sample rows to display.")


# ---------------------------------------------------------------------------
# Executive brief export (Markdown / PDF)
# ---------------------------------------------------------------------------
#: MIME type for the Markdown download.
MARKDOWN_MIME = "text/markdown"

#: Unicode TrueType fonts, first match wins. A Windows dev box and the Debian
#: container Streamlit Cloud runs in ship different fonts, so the builder probes
#: known locations and falls back to fpdf2's built-in Helvetica (Latin-1).
_PDF_FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
)

#: Characters the built-in fonts cannot encode, mapped to ASCII equivalents.
_PDF_ASCII_FALLBACKS = {
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    "•": "-",
    "·": "-",
    "→": "->",
    "←": "<-",
    "≥": ">=",
    "≤": "<=",
    "×": "x",
    "÷": "/",
    "≈": "~",
    "✓": "v",
    "⚠": "!",
    "�\u00a0": " ",
}

_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")


def _pdf_safe(text: str, unicode_ok: bool) -> str:
    """Make text renderable: Latin-1-safe when only the built-in fonts exist."""
    if unicode_ok:
        return text
    for bad, good in _PDF_ASCII_FALLBACKS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def _strip_inline_markdown(text: str) -> str:
    """Flatten inline emphasis and links so no stray ``*`` or ``_`` reaches the PDF.

    The agent writes identifiers such as ``p_value`` and ``A_B_test``; passing
    those to a Markdown renderer would silently italicise them.
    """
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)
    return text.strip()


def _split_table_row(line: str) -> list[str]:
    """Split a pipe-table row into trimmed cells."""
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def parse_markdown_blocks(markdown_text: str) -> list[tuple[Any, ...]]:
    """Split a brief into renderable blocks: headings, bullets, tables, code…"""
    lines = (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[tuple[Any, ...]] = []
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            blocks.append(("code", "\n".join(code)))
            continue

        if _TABLE_SEPARATOR.match(stripped):
            # Separator with no header row above it: nothing to render.
            index += 1
            continue

        if (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and _TABLE_SEPARATOR.match(lines[index + 1].strip())
        ):
            rows = [_split_table_row(stripped)]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_split_table_row(lines[index]))
                index += 1
            blocks.append(("table", rows))
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            blocks.append(("heading", len(heading.group(1)), heading.group(2).strip()))
            index += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            blocks.append(("rule",))
            index += 1
            continue

        if re.match(r"^[-*+]\s+", stripped):
            blocks.append(("bullet", re.sub(r"^[-*+]\s+", "", stripped)))
            index += 1
            continue

        numbered = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if numbered:
            blocks.append(("numbered", numbered.group(1), numbered.group(2).strip()))
            index += 1
            continue

        if stripped.startswith(">"):
            blocks.append(("quote", stripped.lstrip(">").strip()))
            index += 1
            continue

        paragraph: list[str] = [stripped]
        index += 1
        while index < len(lines):
            following = lines[index].strip()
            if (
                not following
                or following.startswith(("#", "- ", "* ", "+ ", ">", "```", "|"))
                or _TABLE_SEPARATOR.match(following)
                or re.match(r"^\d+[.)]\s+", following)
            ):
                break
            paragraph.append(following)
            index += 1
        blocks.append(("paragraph", " ".join(paragraph)))

    return blocks


class _BriefPDF(FPDF):
    """A4 brief with a page footer; font choice is carried on the instance."""

    brief_title = "InsightForge brief"
    font_family = "Helvetica"
    unicode_ok = False

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(self.font_family, "", 8)
        self.set_text_color(130, 138, 150)
        label = _pdf_safe(self.brief_title, self.unicode_ok)
        self.cell(0, 6, f"{label[:80]} - page {self.page_no()}/{{nb}}", align="C")


def _register_pdf_font(pdf: FPDF) -> tuple[str, bool]:
    """Register a Unicode TTF when one exists; otherwise keep core Helvetica."""
    for regular, bold in _PDF_FONT_CANDIDATES:
        if not os.path.exists(regular):
            continue
        try:
            pdf.add_font("Brief", "", regular)
            pdf.add_font("Brief", "B", bold if os.path.exists(bold) else regular)
            return "Brief", True
        except Exception:
            continue
    return "Helvetica", False


def _table_column_widths(rows: list[list[str]], total: float) -> list[float]:
    """Size columns by their longest cell so wide text gets the room."""
    columns = max((len(row) for row in rows), default=1)
    weights: list[float] = []
    for column in range(columns):
        longest = max(
            (len(row[column]) for row in rows if column < len(row)), default=1
        )
        weights.append(float(max(4, min(longest, 34))))
    scale = total / sum(weights)
    return [weight * scale for weight in weights]


def build_brief_pdf(
    markdown_text: str, title: str = "InsightForge brief"
) -> tuple[bytes | None, str | None]:
    """Render a Markdown brief to PDF bytes.

    Returns ``(pdf_bytes, error_message)``: exactly one of them is ``None``, so
    the caller can disable the button and show the reason instead of raising
    inside a Streamlit render.
    """
    if not (markdown_text or "").strip():
        return None, "There is nothing to export yet."

    try:
        pdf = _BriefPDF(format="A4", unit="mm")
        family, unicode_ok = _register_pdf_font(pdf)
        pdf.font_family = family
        pdf.unicode_ok = unicode_ok
        pdf.brief_title = title

        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(18, 16, 18)
        pdf.alias_nb_pages()
        pdf.add_page()

        body_color = (31, 36, 48)
        accent_color = (176, 96, 26)
        muted_color = (110, 118, 132)

        pdf.set_font(family, "B", 17)
        pdf.set_text_color(*body_color)
        pdf.multi_cell(0, 8, _pdf_safe(_strip_inline_markdown(title), unicode_ok))
        pdf.ln(2)
        pdf.set_draw_color(220, 224, 232)
        pdf.set_line_width(0.4)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

        for block in parse_markdown_blocks(markdown_text):
            kind = block[0]
            pdf.set_x(pdf.l_margin)

            if kind == "heading":
                level, text = int(block[1]), str(block[2])
                size = {1: 15.5, 2: 13.0, 3: 11.8}.get(level, 11.0)
                pdf.ln(3.0 if level > 1 else 1.0)
                pdf.set_font(family, "B", size)
                pdf.set_text_color(*accent_color)
                pdf.multi_cell(
                    0,
                    size * 0.42,
                    _pdf_safe(_strip_inline_markdown(text), unicode_ok),
                    align="L",
                )
                pdf.set_text_color(*body_color)
                pdf.ln(1.4)

            elif kind in ("bullet", "numbered"):
                text = str(block[-1])
                if kind == "bullet":
                    marker = "•" if unicode_ok else "-"
                else:
                    marker = f"{block[1]}."
                pdf.set_font(family, "", 10.2)
                pdf.set_text_color(*body_color)
                indent = 5.0
                pdf.set_x(pdf.l_margin + indent)
                pdf.multi_cell(
                    pdf.epw - indent,
                    5.4,
                    _pdf_safe(f"{marker} {_strip_inline_markdown(text)}", unicode_ok),
                    align="L",
                )
                pdf.ln(0.8)

            elif kind == "table":
                rows = [
                    [
                        _pdf_safe(_strip_inline_markdown(cell), unicode_ok)
                        for cell in row
                    ]
                    for row in block[1]
                ]
                columns = max(len(row) for row in rows)
                rows = [row + [""] * (columns - len(row)) for row in rows]
                pdf.set_font(family, "", 9.0)
                pdf.set_text_color(*body_color)
                pdf.ln(1.2)
                with pdf.table(
                    width=pdf.epw,
                    col_widths=_table_column_widths(rows, pdf.epw),
                    text_align="LEFT",
                    line_height=5.0,
                    headings_style=FontFace(
                        emphasis="BOLD",
                        fill_color=(240, 242, 246),
                        color=body_color,
                    ),
                    borders_layout="HORIZONTAL_LINES",
                    first_row_as_headings=True,
                ) as table:
                    for row in rows:
                        table_row = table.row()
                        for cell in row:
                            table_row.cell(cell)
                pdf.ln(2.5)

            elif kind == "code":
                pdf.set_font("Courier", "", 8.6)
                pdf.set_text_color(*body_color)
                pdf.set_fill_color(244, 246, 249)
                pdf.multi_cell(
                    pdf.epw,
                    4.6,
                    _pdf_safe(str(block[1]), False),
                    align="L",
                    fill=True,
                )
                pdf.ln(1.8)

            elif kind == "quote":
                pdf.set_font(family, "", 10.0)
                pdf.set_text_color(*muted_color)
                pdf.set_x(pdf.l_margin + 5)
                pdf.multi_cell(
                    pdf.epw - 5,
                    5.4,
                    _pdf_safe(_strip_inline_markdown(str(block[1])), unicode_ok),
                    align="L",
                )
                pdf.set_text_color(*body_color)
                pdf.ln(1.5)

            elif kind == "rule":
                pdf.ln(1.5)
                pdf.set_draw_color(220, 224, 232)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(2.5)

            else:  # paragraph
                pdf.set_font(family, "", 10.2)
                pdf.set_text_color(*body_color)
                pdf.multi_cell(
                    0,
                    5.5,
                    _pdf_safe(_strip_inline_markdown(str(block[1])), unicode_ok),
                    align="L",
                )
                pdf.ln(1.8)

        return bytes(pdf.output()), None
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"PDF export failed: {exc}"


def brief_timestamp(finished_at: Any = None) -> str:
    """Filename stamp taken from the run's completion time, not the rerun clock."""
    digits = "".join(ch for ch in str(finished_at or "") if ch.isdigit())
    if len(digits) >= 14:
        return digits[:14]
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def render_brief_export_bar(
    report_text: str,
    *,
    title: str = "InsightForge brief",
    finished_at: Any = None,
) -> None:
    """Side-by-side Markdown and PDF downloads for the executive brief."""
    stamp = brief_timestamp(finished_at)
    has_report = bool((report_text or "").strip())

    markdown_col, pdf_col = st.columns(2)

    with markdown_col:
        st.download_button(
            "📄 Download as Markdown (.md)",
            data=(report_text or "").encode("utf-8"),
            file_name=f"insightforge_brief_{stamp}.md",
            mime=MARKDOWN_MIME,
            width="stretch",
            key="download_brief_markdown",
            disabled=not has_report,
        )

    with pdf_col:
        pdf_bytes, pdf_error = (
            build_brief_pdf(report_text, title=title) if has_report else (None, None)
        )
        st.download_button(
            "🧾 Download as PDF",
            data=pdf_bytes or b"",
            file_name=f"insightforge_brief_{stamp}.pdf",
            mime="application/pdf",
            width="stretch",
            key="download_brief_pdf",
            disabled=pdf_bytes is None,
        )
        if pdf_error:
            st.caption(pdf_error)


# ---------------------------------------------------------------------------
# Tab 4: Autonomous agent
# ---------------------------------------------------------------------------
def render_agent_tab() -> None:
    st.markdown("## 🤖 Autonomous AI Agent")
    st.caption(
        "Groq tool-calling agent: it decides when to search papers, describe the dataset "
        "or run anomaly detection, then writes a Markdown report."
    )

    has_dataset = bool(st.session_state.get("dataset_id"))
    has_document = bool(st.session_state.get("document_id"))

    with st.container(border=True):
        goal = st.text_area(
            "Analytical objective",
            value=(
                "Analyze the trends in the dataset and correlate them with the findings "
                "in the uploaded paper."
            ),
            height=110,
            key="agent_goal_input",
            placeholder="e.g. Find the most anomalous regions and explain them using the paper.",
        )
        attach_cols = st.columns(3)
        with attach_cols[0]:
            use_dataset = st.checkbox(
                "Attach dataset",
                value=has_dataset,
                disabled=not has_dataset,
                key="agent_use_dataset",
                help=None if has_dataset else "Load a CSV first.",
            )
        with attach_cols[1]:
            use_document = st.checkbox(
                "Attach paper",
                value=has_document,
                disabled=not has_document,
                key="agent_use_document",
                help=None if has_document else "Index a PDF first.",
            )
        with attach_cols[2]:
            st.caption(
                "Agent limit: 4 tool iterations. Longer goals may finish with status "
                "`max_iterations`."
            )

        run_clicked = st.button(
            "🚀 Run autonomous agent",
            type="primary",
            width="stretch",
            key="run_agent_button",
        )

    if run_clicked:
        if not goal.strip():
            st.warning("Describe what the agent should investigate.")
            return

        with st.status("🤖 Autonomous Agent Working…", expanded=True) as status:
            st.write("Planning the investigation…")
            started = time.perf_counter()
            try:
                payload = api_run_agent(
                    goal.strip(),
                    str(st.session_state["document_id"]) if use_document else None,
                    str(st.session_state["dataset_id"]) if use_dataset else None,
                )
            except BackendError as exc:
                status.update(label="Agent run failed", state="error", expanded=True)
                show_backend_error(exc)
                return

            steps = payload.get("steps") or []
            st.write(
                f"Agent used {len(steps)} tool call(s) — replaying the reasoning trace…"
            )

            for position, step in enumerate(steps, start=1):
                if not isinstance(step, dict):
                    continue
                tool = step_tool(step)
                iteration = step.get("iteration")
                tool_html = (
                    f'<div class="if-step-row">'
                    f'<div class="if-step-head">'
                    f'<span class="if-step-index">STEP {position}</span>'
                    f'<span class="if-step-tool">{esc(tool)}</span>'
                    + (
                        f'<span class="if-step-iter">iteration {esc(iteration)}</span>'
                        if iteration is not None
                        else ""
                    )
                    + "</div></div>"
                )
                st.markdown(tool_html, unsafe_allow_html=True)

                params = step_params(step)
                if params:
                    st.caption(f"parameters · `{json.dumps(params, default=str)[:240]}`")

                result = step_result(step)
                if isinstance(result, (dict, list)):
                    st.json(result, expanded=False)
                elif result is not None:
                    st.code(str(result)[:1200], language="text")

                error = step.get("error")
                if error:
                    st.markdown(
                        f'<div class="if-step-error">⚠ {esc(error)}</div>',
                        unsafe_allow_html=True,
                    )
                time.sleep(0.12)

            elapsed = time.perf_counter() - started
            run_status = str(payload.get("status", "completed"))
            status.update(
                label=(
                    f"Agent finished · {len(steps)} tool calls · "
                    f"{elapsed:.1f}s · {run_status}"
                ),
                state="complete" if run_status == "completed" else "error",
                expanded=False,
            )

            st.session_state["last_agent_run"] = {
                "goal": goal.strip(),
                "report": payload.get("report") or "",
                "steps": steps,
                "status": run_status,
                "title": payload.get("title") or "InsightForge report",
                "run_id": payload.get("run_id"),
                "report_id": payload.get("report_id"),
                "iterations": payload.get("iterations"),
                "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            # The export bar reads this directly, so the brief survives reruns.
            st.session_state["executive_report"] = payload.get("report") or ""

    run = st.session_state.get("last_agent_run")
    if not isinstance(run, dict):
        empty_state(
            "🧠",
            "No agent run yet",
            "Give the agent an objective; it will gather evidence with tools and write a report.",
        )
        return

    st.divider()
    header_cols = st.columns([3, 1])
    with header_cols[0]:
        st.markdown(f"### {run.get('title') or 'Report'}")
        st.caption(
            f"goal · {run.get('goal')}  \n"
            f"status `{run.get('status')}` · {len(run.get('steps') or [])} tool calls · "
            f"{run.get('iterations') or '—'} iterations"
        )
    with header_cols[1]:
        st.markdown(
            f'<div style="text-align:right; padding-top: 14px;">'
            f'{badge("executive brief", "ok")}</div>',
            unsafe_allow_html=True,
        )

    report_text = st.session_state.get("executive_report") or run.get("report") or ""
    render_brief_export_bar(
        report_text,
        title=str(run.get("title") or "InsightForge brief"),
        finished_at=run.get("finished_at"),
    )
    st.write("")

    with st.container(border=True):
        st.markdown(
            f'<div class="if-answer-head">'
            f'<span class="if-answer-title">Final report</span>'
            f'{badge("Groq · llama-3.1-8b-instant", "muted")}</div>',
            unsafe_allow_html=True,
        )
        if report_text.strip():
            st.markdown(report_text)
        else:
            st.info("The agent returned an empty report.")

    with st.expander("Reasoning trace (raw)"):
        st.json(run.get("steps") or [])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="InsightForge · AI Research & Data Analysis",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_styles()
    init_state()

    # /health is public, but there is no reason to probe the backend before the
    # user has a session; the probe runs as soon as they sign in.
    if is_signed_in() and (
        "health" not in st.session_state or st.session_state["health"] is None
    ):
        refresh_health()

    render_sidebar()

    st.markdown(
        """
        <div class="if-hero">
            <span class="if-badge">AI Research Workspace</span>
            <h1>InsightForge</h1>
            <p>
                Grounded paper Q&amp;A over pgvector, exploratory analytics with interactive
                charts, IsolationForest anomaly scans, and an autonomous agent that turns
                evidence into a written report.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not is_signed_in():
        st.info(
            "**Sign in to continue.** Open the sidebar and use the **Sign in** tab, or "
            "create an account in the **Sign up** tab, and InsightForge will scope every "
            "upload, question and agent run to your account.",
            icon="🔐",
        )
        return

    tabs = st.tabs(
        [
            "📄 Paper Q&A",
            "📊 Analytics",
            "🚨 Anomalies",
            "🤖 Agent & Report",
        ]
    )
    with tabs[0]:
        render_paper_tab()
    with tabs[1]:
        render_analytics_tab()
    with tabs[2]:
        render_anomaly_tab()
    with tabs[3]:
        render_agent_tab()


if __name__ == "__main__":
    main()
