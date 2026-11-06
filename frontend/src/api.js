export const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/** Prefer the API's own message (FastAPI puts it in `detail`) over a generic one. */
async function readError(res, fallback) {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      const first = body.detail[0];
      if (typeof first?.msg === "string") return first.msg;
    }
  } catch {
    // Non-JSON error body: fall through to the caller's message.
  }
  return fallback;
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchDocuments(token) {
  const res = await fetch(`${BASE_URL}/documents`, {
    headers: authHeaders(token)
  });
  if (!res.ok) throw new Error(await readError(res, "Failed to load documents"));
  const payload = await res.json();
  return payload.documents ?? [];
}

/**
 * Multipart upload shared by the paper and dataset zones.
 *
 * `endpoint` is the backend path ("/upload/paper", "/upload/dataset"), which is
 * what lets one Uploader component serve both tabs. Content-Type is left to the
 * browser so the multipart boundary is set correctly.
 */
export async function uploadFile(endpoint, file, token) {
  const body = new FormData();
  body.append("file", file);

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    method: "POST",
    headers: authHeaders(token),
    body
  });
  if (!res.ok) throw new Error(await readError(res, "Upload failed"));
  return res.json();
}

export async function fetchChatHistory(documentId, token) {
  const res = await fetch(`${BASE_URL}/chat/history/${documentId}`, {
    headers: authHeaders(token)
  });
  if (!res.ok) throw new Error(await readError(res, "Failed to load history"));
  return res.json();
}

export async function deleteChatHistory(documentId, token) {
  const res = await fetch(`${BASE_URL}/chat/history/${documentId}`, {
    method: "DELETE",
    headers: authHeaders(token)
  });
  if (!res.ok) throw new Error(await readError(res, "Could not clear the chat"));
  return res.json();
}

export async function sendQuery(documentId, query, token) {
  const res = await fetch(`${BASE_URL}/paper/qa`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    // The backend field is `question` (PaperQARequest); `query` is a 422.
    body: JSON.stringify({ document_id: documentId, question: query })
  });
  if (!res.ok) throw new Error(await readError(res, "Inference failed"));
  return res.json();
}

/** Saved executive briefs (newest first) — the agent's persisted reports. */
export async function fetchReports(token) {
  const res = await fetch(`${BASE_URL}/reports`, {
    headers: authHeaders(token)
  });
  if (!res.ok) throw new Error(await readError(res, "Failed to load briefs"));
  const payload = await res.json();
  return payload.reports ?? [];
}

/**
 * Download one brief as a Blob, ready for an object-URL download.
 * Returns `{ blob, filename }`; the filename comes from Content-Disposition.
 */
export async function downloadReport(reportId, format, token) {
  const res = await fetch(`${BASE_URL}/reports/${reportId}/export/${format}`, {
    headers: authHeaders(token)
  });
  if (!res.ok) {
    throw new Error(await readError(res, `Could not export the brief as ${format}`));
  }

  const disposition = res.headers.get("Content-Disposition") || "";
  const match = /filename="?([^";]+)"?/i.exec(disposition);
  const extension = format === "pdf" ? "pdf" : "md";

  return {
    blob: await res.blob(),
    filename: match?.[1] || `insightforge_brief.${extension}`
  };
}

/** Run IsolationForest over a cached dataset; returns the diagnostics payload. */
export async function runAnomalies(datasetId, { contamination, features } = {}, token) {
  const body = new FormData();
  if (contamination !== undefined) body.append("contamination", String(contamination));
  for (const feature of features ?? []) body.append("features", feature);

  const res = await fetch(`${BASE_URL}/dataset/${datasetId}/anomalies`, {
    method: "POST",
    headers: authHeaders(token),
    body
  });
  if (!res.ok) throw new Error(await readError(res, "Anomaly detection failed"));
  return res.json();
}

export async function checkBackend() {
  try {
    const res = await fetch(`${BASE_URL}/health`, {
      signal: AbortSignal.timeout(4000)
    });
    return res.ok;
  } catch {
    return false;
  }
}
