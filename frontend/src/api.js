const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

/** Prefer the API's own message (FastAPI puts it in `detail`) over a generic one. */
async function readError(res, fallback) {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    // Non-JSON error body: fall through to the caller's message.
  }
  return fallback;
}

export async function fetchDocuments(token) {
  const res = await fetch(`${BACKEND_URL}/documents`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(await readError(res, "Failed to load documents"));
  const payload = await res.json();
  return payload.documents ?? [];
}

export async function fetchChatHistory(documentId, token) {
  const res = await fetch(`${BACKEND_URL}/chat/history/${documentId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!res.ok) throw new Error(await readError(res, "Failed to load history"));
  return res.json();
}

export async function sendQuery(documentId, query, token) {
  const res = await fetch(`${BACKEND_URL}/paper/qa`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`
    },
    // The backend field is `question` (PaperQARequest); `query` is a 422.
    body: JSON.stringify({ document_id: documentId, question: query })
  });
  if (!res.ok) throw new Error(await readError(res, "Inference failed"));
  return res.json();
}

export async function checkBackend() {
  try {
    const res = await fetch(`${BACKEND_URL}/health`, {
      signal: AbortSignal.timeout(4000)
    });
    return res.ok;
  } catch {
    return false;
  }
}

export { BACKEND_URL };
