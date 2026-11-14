import { Component, lazy, Suspense, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  BookOpen,
  ChevronDown,
  Download,
  FileUp,
  LayoutDashboard,
  Loader2,
  LogOut,
  MessageSquare,
  Send,
  Sparkles,
  Trash2
} from "lucide-react";
import { supabase } from "./supabase";
import AuthPage from "./AuthPage.jsx";
import Dashboard from "./Dashboard.jsx";
import {
  checkBackend,
  deleteChatHistory,
  downloadReport,
  fetchChatHistory,
  fetchDocuments,
  fetchReports,
  runAnomalies,
  sendQuery
} from "./api";
import Uploader from "./components/Uploader";

// Plotly is ~5 MB; keeping it out of the chat bundle means only the anomalies
// tab ever downloads it, and only when a dataset has actually been analysed.
const AnomalyPanel = lazy(() => import("./components/AnomalyPanel"));

const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "chat", label: "Research Chat", icon: MessageSquare },
  { id: "anomalies", label: "Outliers & Anomalies", icon: Activity }
];

function StatusPill({ online }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset",
        online === true && "bg-accent/10 text-accent ring-accent/30",
        online === false && "bg-rose-500/10 text-rose-300 ring-rose-500/30",
        online === null && "bg-white/5 text-slate-400 ring-white/10"
      )}
    >
      <span
        className={clsx(
          "size-1.5 rounded-full",
          online === true && "bg-accent",
          online === false && "bg-rose-400",
          online === null && "animate-pulse bg-slate-500"
        )}
      />
      {online === null ? "Checking" : online ? "Online" : "Offline"}
    </span>
  );
}


function MessageBubble({ message }) {
  if (message.role === "error") {
    return (
      <div className="mx-auto max-w-full rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-center text-xs text-rose-200">
        {message.content}
      </div>
    );
  }

  const isUser = message.role === "user";
  const citations = message.citations ?? [];

  return (
    <div className={clsx("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={clsx(
          "max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "rounded-br-sm bg-gradient-to-br from-accent-light to-accent text-on-accent"
            : "rounded-bl-sm border border-white/10 bg-white/[0.04] text-slate-200"
        )}
      >
        {message.content}
        {citations.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t border-white/10 pt-2">
            {citations.map((citation, index) => (
              <span
                key={`${citation.page_number}-${index}`}
                title={`cosine similarity ${Number(citation.similarity ?? 0).toFixed(2)}`}
                className={clsx(
                  "rounded-md px-1.5 py-0.5 text-[11px]",
                  isUser
                    ? "bg-on-accent/10 text-on-accent/80"
                    : "bg-white/[0.06] text-slate-400"
                )}
              >
                p. {citation.page_number}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-3 rounded-2xl rounded-bl-sm border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-400">
        <span className="flex gap-1" aria-hidden="true">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-1.5 animate-pulse rounded-full bg-accent"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </span>
        Searching passages and drafting an answer
      </div>
    </div>
  );
}

function ExportBar({ reports, exporting, error, onExport }) {
  const latest = reports[0];
  const disabled = !latest || Boolean(exporting);

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 bg-white/[0.02] px-6 py-2">
        <p className="truncate text-[11px] text-slate-400">
          <span className="font-medium text-slate-200">Executive brief:</span>{" "}
          {latest ? latest.title : "none saved yet"}
        </p>
        <div className="flex gap-2">
          {[
            { format: "markdown", label: "Export Markdown" },
            { format: "pdf", label: "Export PDF" }
          ].map(({ format, label }) => (
            <button
              key={format}
              type="button"
              disabled={disabled}
              onClick={() => onExport(format)}
              title={
                latest
                  ? `Download the latest brief as ${format === "pdf" ? "PDF" : "Markdown"}`
                  : "Run the autonomous agent to generate a brief first"
              }
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-accent/35 hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
            >
              {exporting === format ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Download className="size-3.5" aria-hidden="true" />
              )}
              {label}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <p className="border-b border-rose-500/20 bg-rose-500/10 px-6 py-2 text-[11px] text-rose-200">
          {error}
        </p>
      )}
    </>
  );
}

function ChatPanel({
  documents,
  documentsError,
  onRetryDocuments,
  selectedDocId,
  onSelectDocument,
  messages,
  sending,
  loadingHistory,
  draft,
  onDraftChange,
  onSend,
  onClearChat,
  clearing,
  reports,
  exporting,
  exportError,
  onExport,
  showUploader,
  onToggleUploader,
  onPaperUploaded,
  token
}) {
  const hasDocuments = documents.length > 0;
  const hasDocument = Boolean(selectedDocId);
  const canSend = hasDocument && draft.trim().length > 0 && !sending;
  const selected = documents.find((doc) => doc.id === selectedDocId);

  function submit(event) {
    event?.preventDefault?.();
    if (canSend) onSend();
  }

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-6 py-4">
        <div>
          <h1 className="text-sm font-semibold text-slate-100">Research Chat</h1>
          <p className="text-xs text-slate-400">
            Retrieval-grounded answers with page citations
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <select
              aria-label="Paper"
              value={selectedDocId ?? ""}
              onChange={(event) => onSelectDocument(event.target.value || null)}
              disabled={!hasDocuments}
              title={selected?.filename ?? "No papers indexed"}
              className="max-w-[15rem] appearance-none truncate rounded-lg border border-white/10 bg-white/[0.04] py-2 pl-3 pr-9 text-xs text-slate-200 outline-none transition focus:border-accent/60 disabled:opacity-60"
            >
              {!hasDocuments && <option value="">No papers indexed</option>}
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
          </div>

          <button
            type="button"
            onClick={onToggleUploader}
            aria-pressed={showUploader}
            title="Upload a PDF"
            className={clsx(
              "grid size-9 place-items-center rounded-lg border transition",
              showUploader
                ? "border-accent/50 bg-accent/10 text-accent"
                : "border-white/10 bg-white/[0.04] text-slate-400 hover:text-slate-200"
            )}
          >
            <FileUp className="size-4" aria-hidden="true" />
          </button>

          <button
            type="button"
            onClick={onClearChat}
            disabled={!hasDocument || clearing}
            aria-label="Clear chat"
            title={hasDocument ? "Delete this paper's saved conversation" : "Select a paper first"}
            className="grid size-9 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-slate-400 transition hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-white/10 disabled:hover:bg-white/[0.04] disabled:hover:text-slate-400"
          >
            {clearing ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Trash2 className="size-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </header>

      <ExportBar
        reports={reports}
        exporting={exporting}
        error={exportError}
        onExport={onExport}
      />

      {showUploader && (
        <div className="border-b border-white/10 bg-white/[0.02] px-4 py-4 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <Uploader
              endpoint="/upload/paper"
              token={token}
              accept=".pdf,application/pdf"
              title="Upload a research paper"
              hint="Dragging a PDF here indexes it for retrieval"
              maxSizeMB={15}
              onUploaded={onPaperUploaded}
            />
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {documentsError && (
            <div
              role="alert"
              className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-6 text-center"
            >
              <p className="text-sm font-medium text-rose-100">Could not load your library</p>
              <p className="mx-auto mt-1 max-w-sm break-words text-xs leading-relaxed text-rose-200">
                {documentsError}
              </p>
              <button
                type="button"
                onClick={onRetryDocuments}
                className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:bg-rose-500/20"
              >
                Try again
              </button>
            </div>
          )}

          {!hasDocuments && !documentsError && (
            <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-8 text-center">
              <BookOpen className="mx-auto size-6 text-slate-400" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-200">No papers indexed yet</p>
              <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-400">
                Upload a PDF with the button above to index it, then pick it in the paper
                selector.
              </p>
            </div>
          )}

          {hasDocuments && !loadingHistory && messages.length === 0 && (
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-8 text-center">
              <Sparkles className="mx-auto size-6 text-[#94a3b8]" aria-hidden="true" />
              <p
                className="mt-3 break-words text-sm font-medium text-slate-200"
                title={selected?.filename}
              >
                Ask about {selected?.filename ?? "this paper"}
              </p>
              <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-400">
                Methods, sample sizes, contamination thresholds, or what the limitations section
                admits. Answers cite the pages they came from.
              </p>
            </div>
          )}

          {loadingHistory && (
            <p className="flex items-center justify-center gap-2 text-xs text-slate-400">
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              Loading conversation
            </p>
          )}

          {messages.map((message, index) => (
            <MessageBubble key={index} message={message} />
          ))}

          {sending && <ThinkingBubble />}
        </div>
      </div>

      <form onSubmit={submit} className="border-t border-white/10 bg-[#04070a]/85 px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            rows={1}
            value={draft}
            maxLength={2000}
            title="Up to 2,000 characters"
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) submit(event);
            }}
            disabled={!hasDocument || sending}
            placeholder={
              hasDocument ? "Ask about methods, results, limitations…" : "Select a paper to start"
            }
            className="max-h-40 min-h-11 flex-1 resize-none rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-400 outline-none transition focus:border-accent/60 focus:ring-2 focus:ring-accent/20 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send question"
            className="grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-accent-light to-accent text-on-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:from-white/10 disabled:to-white/10 disabled:text-slate-400"
          >
            {sending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            ) : (
              <Send className="size-4" aria-hidden="true" />
            )}
          </button>
        </div>
      </form>
    </>
  );
}

/**
 * Plotly is a ~5 MB lazy chunk. Without this boundary a failed chunk download
 * throws during render and takes the whole console down with it.
 */
class ChartBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
    this.retry = this.retry.bind(this);
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  retry() {
    this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div
        role="alert"
        className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-5 py-6 text-center"
      >
        <p className="text-sm font-medium text-rose-100">Charts could not be loaded</p>
        <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-rose-200">
          The chart bundle failed to download. The figures above are computed and still valid.
        </p>
        <button
          type="button"
          onClick={this.retry}
          className="mt-3 rounded-lg border border-rose-400/40 bg-rose-500/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:bg-rose-500/20"
        >
          Load charts again
        </button>
      </div>
    );
  }
}

function AnomaliesView({ token }) {
  const [dataset, setDataset] = useState(null);
  const [contamination, setContamination] = useState(0.05);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  // Bumped per run so a failed chart boundary resets on the next attempt.
  const [runId, setRunId] = useState(0);

  async function run() {
    if (!dataset || running) return;
    setRunning(true);
    setError(null);
    setRunId((id) => id + 1);
    try {
      const payload = await runAnomalies(
        dataset.dataset_id,
        { contamination },
        token
      );
      setResult(payload);
    } catch (err) {
      setError(err?.message ?? "Anomaly detection failed");
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <header className="border-b border-white/10 px-6 py-4">
        <h1 className="text-sm font-semibold text-slate-100">Outliers &amp; Anomalies</h1>
        <p className="text-xs text-slate-400">
          IsolationForest screening over an uploaded CSV dataset
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <Uploader
            endpoint="/upload/dataset"
            token={token}
            accept=".csv,text/csv"
            title="Upload a CSV dataset"
            hint="Label and id columns are excluded from the model automatically"
            maxSizeMB={10}
            onUploaded={(payload) => {
              setDataset(payload);
              setResult(null);
              setError(null);
            }}
          />

          {dataset && (
            <section className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p
                    className="max-w-[22rem] truncate text-sm font-medium text-slate-200"
                    title={dataset.filename}
                  >
                    {dataset.filename}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {Number(dataset.row_count ?? 0).toLocaleString()} rows ×{" "}
                    {Number(dataset.col_count ?? 0).toLocaleString()} columns
                  </p>
                </div>

                <button
                  type="button"
                  onClick={run}
                  disabled={running}
                  className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-br from-accent-light to-accent px-4 py-2 text-xs font-semibold text-on-accent transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {running ? (
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <Activity className="size-3.5" aria-hidden="true" />
                  )}
                  {running ? "Screening rows…" : "Run anomaly detection"}
                </button>
              </div>

              <label className="mt-4 block space-y-1.5">
                <span className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>Expected outlier share (contamination)</span>
                  <span className="tabular-nums text-slate-300">
                    {contamination.toFixed(2)}
                  </span>
                </span>
                <input
                  type="range"
                  min={0.01}
                  max={0.2}
                  step={0.01}
                  value={contamination}
                  onChange={(event) => setContamination(Number(event.target.value))}
                  className="w-full [accent-color:var(--accent)]"
                />
                <span className="block text-[11px] text-slate-400">
                  Allowed range 0.01 – 0.20, matching the API.
                </span>
              </label>
            </section>
          )}

          {error && (
            <div
              role="alert"
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2"
            >
              <p className="min-w-0 flex-1 break-words text-xs text-rose-200">{error}</p>
              <button
                type="button"
                onClick={run}
                disabled={running}
                className="shrink-0 rounded-md border border-rose-400/40 px-2.5 py-1 text-[11px] font-medium text-rose-100 transition hover:bg-rose-500/20 disabled:opacity-60"
              >
                Try again
              </button>
            </div>
          )}

          {running && !result && (
            <p className="flex items-center gap-2 text-xs text-slate-400">
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              Fitting IsolationForest and scoring each row
            </p>
          )}

          {result ? (
            <Suspense
              fallback={
                <p className="flex items-center gap-2 text-xs text-slate-400">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  Loading charts
                </p>
              }
            >
              <ChartBoundary key={runId}>
                <AnomalyPanel result={result} />
              </ChartBoundary>
            </Suspense>
          ) : (
            !dataset && (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.02] p-10 text-center">
                <Activity className="mx-auto size-7 text-slate-400" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-slate-200">
                  Upload a dataset to screen it
                </p>
                <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-400">
                  The score distribution, per-feature contributions and the most anomalous rows
                  render here as interactive charts once a dataset is analysed.
                </p>
              </div>
            )
          )}
        </div>
      </div>
    </>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [view, setView] = useState("overview");
  const [online, setOnline] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [reports, setReports] = useState([]);
  const [exporting, setExporting] = useState(null);
  const [exportError, setExportError] = useState(null);
  const [clearing, setClearing] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [documentsError, setDocumentsError] = useState(null);
  const bottomRef = useRef(null);
  // Guards against a double Enter and against a paper switch mid-request.
  const sendingRef = useRef(false);
  const selectedDocIdRef = useRef(null);
  // Set right before a refresh so the freshly uploaded paper is selected.
  const pendingDocRef = useRef(null);

  // Auth gate: restore the stored session, then follow sign-in/sign-out events.
  useEffect(() => {
    let active = true;

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active) setSession(data.session ?? null);
      })
      .catch(() => {
        // Unreachable/placeholder Supabase URL: show the sign-in form rather than a blank page.
      })
      .finally(() => {
        if (active) setAuthChecked(true);
      });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, []);

  // Backend heartbeat for the sidebar status pill.
  useEffect(() => {
    let active = true;

    const ping = async () => {
      const ok = await checkBackend();
      if (active) setOnline(ok);
    };

    ping();
    const timer = setInterval(ping, 30000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  // The caller's indexed papers; the chat is scoped to one of them.
  useEffect(() => {
    if (!session) {
      setDocuments([]);
      setDocumentsError(null);
      setSelectedDocId(null);
      setMessages([]);
      return;
    }

    let active = true;
    setDocumentsError(null);
    fetchDocuments(session.access_token)
      .then((list) => {
        if (!active) return;
        setDocuments(list);
        setSelectedDocId((current) => {
          const preferred = pendingDocRef.current;
          pendingDocRef.current = null;
          if (preferred && list.some((doc) => doc.id === preferred)) return preferred;
          if (current && list.some((doc) => doc.id === current)) return current;
          return list[0]?.id ?? null;
        });
      })
      .catch((error) => {
        if (!active) return;
        // An API failure must not read as an empty library.
        setDocumentsError(error?.message ?? "The API did not answer the library request.");
      });

    return () => {
      active = false;
    };
  }, [session, refreshKey]);

  // Saved briefs power the export bar.
  useEffect(() => {
    if (!session) {
      setReports([]);
      return;
    }

    let active = true;
    fetchReports(session.access_token)
      .then((list) => {
        if (active) setReports(list);
      })
      .catch(() => {
        if (active) setReports([]);
      });

    return () => {
      active = false;
    };
  }, [session]);

  // Saved conversation for the selected paper.
  useEffect(() => {
    if (!session || !selectedDocId) {
      setMessages([]);
      return;
    }

    let active = true;
    setLoadingHistory(true);
    fetchChatHistory(selectedDocId, session.access_token)
      .then((payload) => {
        if (!active) return;
        setMessages(
          (payload.messages ?? []).map((message) => ({
            role: message.role,
            content: message.content,
            citations: message.citations ?? []
          }))
        );
      })
      .catch(() => {
        // A paper with no reachable history still works: start from an empty thread.
        if (active) setMessages([]);
      })
      .finally(() => {
        if (active) setLoadingHistory(false);
      });

    return () => {
      active = false;
    };
  }, [session, selectedDocId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, loadingHistory]);

  useEffect(() => {
    selectedDocIdRef.current = selectedDocId;
  }, [selectedDocId]);

  async function handleSend() {
    const question = draft.trim();
    if (!question || sendingRef.current || !selectedDocId || !session) return;

    // The answer belongs to the paper that was open when the question was sent.
    const askedDocId = selectedDocId;
    sendingRef.current = true;
    setDraft("");
    setSending(true);
    setMessages((previous) => [...previous, { role: "user", content: question }]);

    try {
      const payload = await sendQuery(askedDocId, question, session.access_token);
      // Switching papers mid-flight must not file the answer under the new one.
      if (selectedDocIdRef.current !== askedDocId) return;
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: payload.answer,
          citations: payload.citations ?? []
        }
      ]);
    } catch (error) {
      if (selectedDocIdRef.current !== askedDocId) return;
      // A failed send must not cost the user the question they typed.
      setDraft((current) => current || question);
      setMessages((previous) => [
        ...previous,
        {
          role: "error",
          content: `${error?.message ?? "Inference failed"} — your question is back in the box.`
        }
      ]);
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  async function handleClearChat() {
    if (!selectedDocId || !session || clearing) return;
    const confirmed = window.confirm(
      "Delete this paper's saved conversation? This cannot be undone."
    );
    if (!confirmed) return;

    setClearing(true);
    try {
      await deleteChatHistory(selectedDocId, session.access_token);
      setMessages([]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        { role: "error", content: error?.message ?? "Could not clear the chat" }
      ]);
    } finally {
      setClearing(false);
    }
  }

  async function handleExport(format, reportId) {
    // The chat bar exports the newest brief; the overview can name any of them.
    const target = reportId ?? reports[0]?.id;
    if (!target || !session || exporting) return;

    setExporting(format);
    setExportError(null);
    try {
      const { blob, filename } = await downloadReport(
        target,
        format,
        session.access_token
      );

      // Blob -> object URL -> synthetic click is the only way to name the file.
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setExportError(error?.message ?? "Export failed");
    } finally {
      setExporting(null);
    }
  }

  function handlePaperUploaded(payload) {
    if (payload?.document_id) pendingDocRef.current = payload.document_id;
    setShowUploader(false);
    setRefreshKey((key) => key + 1);
  }

  if (!authChecked) {
    return (
      <div className="grid min-h-screen place-items-center text-slate-400">
        <Loader2 className="size-5 animate-spin" aria-label="Loading" />
      </div>
    );
  }

  if (!session) return <AuthPage embedded />;

  return (
    <div className="min-h-screen bg-[#04070a] text-slate-100">
      {/* Below lg the sidebar would eat most of the width, so it collapses to one row. */}
      <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-white/[0.07] bg-[#04070a]/95 px-3 py-2 backdrop-blur lg:hidden">
        <div className="mr-1 grid size-7 place-items-center rounded-lg border border-accent/30 bg-gradient-to-br from-accent-light to-accent text-[11px] font-bold text-on-accent">
          IF
        </div>
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setView(id)}
            aria-label={label}
            title={label}
            aria-current={view === id ? "page" : undefined}
            className={clsx(
              "grid size-9 place-items-center rounded-lg transition",
              view === id
                ? "bg-white/[0.07] text-accent ring-1 ring-inset ring-accent/20"
                : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
          </button>
        ))}
        <button
          type="button"
          onClick={() => supabase.auth.signOut()}
          aria-label="Sign out"
          title="Sign out"
          className="ml-auto grid size-9 place-items-center rounded-lg text-slate-400 transition hover:bg-rose-500/10 hover:text-rose-300"
        >
          <LogOut className="size-4" aria-hidden="true" />
        </button>
      </header>

      <div className="flex">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-white/[0.07] bg-[#04070a] lg:flex">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="grid size-9 place-items-center rounded-xl border border-accent/30 bg-gradient-to-br from-accent-light to-accent text-sm font-bold text-on-accent">
            IF
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight text-white">InsightForge</p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-[#94a3b8]">
              Research console
            </p>
          </div>
        </div>

        <div className="px-5">
          <StatusPill online={online} />
        </div>

        <nav className="mt-6 flex flex-col gap-1 px-3">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setView(id)}
              aria-label={label}
              title={label}
              aria-current={view === id ? "page" : undefined}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                view === id
                  ? "bg-white/[0.07] text-white ring-1 ring-inset ring-accent/20"
                  : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
              )}
            >
              <Icon
                className={clsx("size-4", view === id && "text-accent")}
                aria-hidden="true"
              />
              {label}
            </button>
          ))}
        </nav>

        <div className="mt-auto border-t border-white/[0.07] p-3">
          <p className="truncate px-2 pb-2 text-xs text-slate-400">
            {session.user?.email ?? "Signed in"}
          </p>
          <button
            type="button"
            onClick={() => supabase.auth.signOut()}
            aria-label="Sign out"
            title="Sign out"
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-rose-500/10 hover:text-rose-300"
          >
            <LogOut className="size-4" aria-hidden="true" />
            Sign Out
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        {view === "overview" ? (
          <Dashboard
            documents={documents}
            documentsError={documentsError}
            selectedDocId={selectedDocId}
            onSelectDocument={setSelectedDocId}
            reports={reports}
            online={online}
            exporting={exporting}
            onRetryDocuments={() => setRefreshKey((key) => key + 1)}
            onExport={handleExport}
            onUpload={() => {
              setShowUploader(true);
              setView("chat");
            }}
            onOpenChat={(question) => {
              if (question) setDraft(question);
              setView("chat");
            }}
            onOpenPaper={(id) => {
              setSelectedDocId(id);
              setView("chat");
            }}
            onOpenAnomalies={() => setView("anomalies")}
          />
        ) : view === "chat" ? (
          <ChatPanel
            documents={documents}
            documentsError={documentsError}
            onRetryDocuments={() => setRefreshKey((key) => key + 1)}
            selectedDocId={selectedDocId}
            onSelectDocument={setSelectedDocId}
            messages={messages}
            sending={sending}
            loadingHistory={loadingHistory}
            draft={draft}
            onDraftChange={setDraft}
            onSend={handleSend}
            onClearChat={handleClearChat}
            clearing={clearing}
            reports={reports}
            exporting={exporting}
            exportError={exportError}
            onExport={handleExport}
            showUploader={showUploader}
            onToggleUploader={() => setShowUploader((open) => !open)}
            onPaperUploaded={handlePaperUploaded}
            token={session.access_token}
          />
        ) : (
          <AnomaliesView token={session.access_token} />
        )}
        <div ref={bottomRef} />
      </main>
      </div>
    </div>
  );
}
