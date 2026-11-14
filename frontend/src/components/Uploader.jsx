import { useEffect, useId, useRef, useState } from "react";
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
      const pages = payload.total_pages
        ? ` · ${Number(payload.total_pages).toLocaleString()} pages`
        : "";
      const chunks = payload.chunk_count
        ? ` · ${Number(payload.chunk_count).toLocaleString()} chunks`
        : "";
      return `${payload.filename ?? "Paper"} indexed${pages}${chunks}`;
    }
    if (payload?.dataset_id) {
      const rows = Number(payload.row_count ?? 0).toLocaleString();
      const columns = Number(payload.col_count ?? 0).toLocaleString();
      return `${payload.filename ?? "Dataset"} loaded · ${rows} rows × ${columns} columns`;
    }
    return "Upload complete";
  }

  // `accept` only filters the native picker; a drop bypasses it entirely.
  const allowedExtensions = (accept ?? "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter((entry) => entry.startsWith("."));

  /** Why this file cannot be uploaded, or null when it can. */
  function rejection(file) {
    if (!file) return "No file was read. Choose it again.";
    if (file.size === 0) return `${file.name} is empty (0 bytes).`;
    if (maxSizeMB && file.size > maxSizeMB * 1024 * 1024) {
      const size = (file.size / (1024 * 1024)).toFixed(1);
      return `${file.name} is ${size} MB; the limit is ${maxSizeMB} MB.`;
    }
    if (allowedExtensions.length > 0) {
      const name = file.name.toLowerCase();
      if (!allowedExtensions.some((extension) => name.endsWith(extension))) {
        return `${file.name} is not ${allowedExtensions.join(" or ")}. Choose a supported file.`;
      }
    }
    return null;
  }

  async function submit(file) {
    if (busy) return;

    const problem = rejection(file);
    if (problem) {
      setStatus("error");
      setMessage(problem);
      if (inputRef.current) inputRef.current.value = "";
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

  function openPicker(event) {
    if (busy) return;
    // The hidden input sits inside the zone: let its own click through instead
    // of re-opening the picker from the bubbling event.
    if (event?.target === inputRef.current) return;
    inputRef.current?.click();
  }

  const isDraggingFiles = (event) =>
    Array.from(event.dataTransfer?.types ?? []).includes("Files");

  // A drag that leaves the window or ends elsewhere never fires dragleave on
  // the zone, which would leave the highlight lit until the next drop.
  useEffect(() => {
    if (!dragging) return undefined;
    const clear = () => setDragging(false);
    window.addEventListener("blur", clear);
    window.addEventListener("dragend", clear);
    window.addEventListener("drop", clear);
    return () => {
      window.removeEventListener("blur", clear);
      window.removeEventListener("dragend", clear);
      window.removeEventListener("drop", clear);
    };
  }, [dragging]);

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={busy ? -1 : 0}
        aria-label={title}
        aria-disabled={busy}
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
        onDragEnd={() => setDragging(false)}
        className={clsx(
          "group flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border border-dashed px-6 py-8 text-center outline-none transition",
          "focus-visible:ring-2 focus-visible:ring-[#9bf7c4]/40",
          dragging
            ? "border-[#9bf7c4] bg-[#9bf7c4]/5"
            : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]",
          disabled && "cursor-not-allowed opacity-60 hover:border-white/10"
        )}
      >
        <div
          className={clsx(
            "grid size-10 place-items-center rounded-xl border transition",
            dragging
              ? "border-[#9bf7c4]/40 bg-[#9bf7c4]/10 text-[#9bf7c4]"
              : "border-white/10 bg-white/[0.03] text-slate-400 group-hover:text-slate-200"
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
          <p className="mt-0.5 text-xs leading-relaxed text-slate-400">
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
            status === "success" && "border-[#9bf7c4]/30 bg-[#9bf7c4]/10 text-[#9bf7c4]",
            status === "uploading" && "border-white/10 bg-white/[0.04] text-slate-300"
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
              className="shrink-0 rounded text-slate-400 transition hover:text-slate-100"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
