import { useId, useRef, useState } from "react";
import clsx from "clsx";
import {
  CheckCircle2,
  FileUp,
  Loader2,
  TriangleAlert,
  UploadCloud,
  X
} from "lucide-react";
import { uploadFile } from "../api";

/**
 * Drag-and-drop upload zone shared by the paper and dataset tabs.
 *
 * The only thing that differs between the two uses is `endpoint`, so the
 * component stays a thin wrapper around `uploadFile` and reports the parsed
 * response through `onUploaded` for the parent to refresh its own state.
 */
export default function Uploader({
  endpoint,
  token,
  accept,
  title = "Upload a file",
  hint,
  maxSizeMB,
  onUploaded,
  disabled = false
}) {
  const inputRef = useRef(null);
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | uploading | success | error
  const [message, setMessage] = useState(null);

  const busy = status === "uploading" || disabled;

  function describe(payload) {
    if (payload?.document_id) {
      const pages = payload.total_pages ? ` · ${payload.total_pages} pages` : "";
      const chunks = payload.chunk_count ? ` · ${payload.chunk_count} chunks` : "";
      return `${payload.filename} indexed${pages}${chunks}`;
    }
    if (payload?.dataset_id) {
      return `${payload.filename} loaded · ${payload.row_count} rows × ${payload.col_count} columns`;
    }
    return "Upload complete";
  }

  async function submit(file) {
    if (!file || busy) return;

    if (maxSizeMB && file.size > maxSizeMB * 1024 * 1024) {
      const size = (file.size / (1024 * 1024)).toFixed(1);
      setStatus("error");
      setMessage(`${file.name} is ${size} MB; the limit is ${maxSizeMB} MB.`);
      return;
    }

    setStatus("uploading");
    setMessage(file.name);

    try {
      const payload = await uploadFile(endpoint, file, token);
      setStatus("success");
      setMessage(describe(payload));
      onUploaded?.(payload);
    } catch (error) {
      setStatus("error");
      setMessage(error?.message ?? "Upload failed");
    } finally {
      // Allow re-picking the same file after an error.
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) submit(file);
  }

  function openPicker() {
    if (!busy) inputRef.current?.click();
  }

  const isDraggingFiles = (event) =>
    Array.from(event.dataTransfer?.types ?? []).includes("Files");

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={title}
        aria-disabled={disabled}
        aria-busy={status === "uploading"}
        onClick={openPicker}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openPicker();
          }
        }}
        onDragEnter={(event) => {
          if (!isDraggingFiles(event) || busy) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => {
          if (!isDraggingFiles(event) || busy) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={(event) => {
          // Ignore drags moving between children of the zone.
          if (event.currentTarget.contains(event.relatedTarget)) return;
          setDragging(false);
        }}
        onDrop={handleDrop}
        className={clsx(
          "group flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-6 py-8 text-center outline-none transition",
          "focus-visible:ring-2 focus-visible:ring-sky-500/40",
          dragging
            ? "border-sky-500 bg-sky-500/5"
            : "border-slate-700 bg-slate-900/40 hover:border-slate-600 hover:bg-slate-900/60",
          disabled && "cursor-not-allowed opacity-60 hover:border-slate-700"
        )}
      >
        <div
          className={clsx(
            "grid size-10 place-items-center rounded-xl border transition",
            dragging
              ? "border-sky-500/40 bg-sky-500/10 text-sky-300"
              : "border-slate-700 bg-slate-950/60 text-slate-400 group-hover:text-slate-300"
          )}
        >
          {status === "uploading" ? (
            <Loader2 className="size-5 animate-spin" aria-hidden="true" />
          ) : (
            <UploadCloud className="size-5" aria-hidden="true" />
          )}
        </div>

        <div>
          <p className="text-sm font-medium text-slate-200">
            {status === "uploading" ? "Uploading…" : title}
          </p>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
            {hint ?? "Drag a file here, or click to browse"}
            {maxSizeMB ? ` · up to ${maxSizeMB} MB` : ""}
          </p>
        </div>

        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept={accept}
          disabled={busy}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) submit(file);
          }}
        />
      </div>

      {message && (
        <div
          role={status === "error" ? "alert" : "status"}
          className={clsx(
            "flex items-start gap-2 rounded-lg border px-3 py-2 text-xs",
            status === "error" && "border-rose-500/30 bg-rose-500/10 text-rose-200",
            status === "success" && "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
            status === "uploading" && "border-slate-700 bg-slate-900/60 text-slate-300"
          )}
        >
          {status === "error" && (
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          )}
          {status === "success" && (
            <CheckCircle2 className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          )}
          {status === "uploading" && (
            <FileUp className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          )}
          <span className="flex-1 break-words">{message}</span>
          {status !== "uploading" && (
            <button
              type="button"
              onClick={() => {
                setStatus("idle");
                setMessage(null);
              }}
              aria-label="Dismiss"
              className="shrink-0 rounded text-slate-500 transition hover:text-slate-200"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
