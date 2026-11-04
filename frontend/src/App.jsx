import { lazy, Suspense, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  Activity,
  BookOpen,
  ChevronDown,
  Download,
  Eye,
  EyeOff,
  FileUp,
  Loader2,
  LogOut,
  MessageSquare,
  Send,
  Sparkles,
  Trash2
} from "lucide-react";
import { supabase } from "./supabase";
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
  { id: "chat", label: "Research Chat", icon: MessageSquare },
  { id: "anomalies", label: "Outliers & Anomalies", icon: Activity }
];

const INPUT_CLASSES =
  "w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20";

function StatusPill({ online }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset",
        online === true && "bg-emerald-500/10 text-emerald-300 ring-emerald-500/30",
        online === false && "bg-rose-500/10 text-rose-300 ring-rose-500/30",
        online === null && "bg-slate-800 text-slate-400 ring-slate-700"
      )}
    >
      <span
        className={clsx(
          "size-1.5 rounded-full",
          online === true && "bg-emerald-400",
          online === false && "bg-rose-400",
          online === null && "animate-pulse bg-slate-500"
        )}
      />
      {online === null ? "Checking" : online ? "Online" : "Offline"}
    </span>
  );
}

function AuthView() {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { data, error: authError } =
        mode === "signin"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password });

      if (authError) {
        setError(authError.message);
        return;
      }
      // Sign-up with email confirmation on: no session until the link is clicked.
      if (mode === "signup" && !data.session) {
        setNotice("Account created. Confirm your email address, then sign in.");
      }
    } catch (err) {
      setError(
        err?.message ??
          "Could not reach Supabase. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-sm font-bold text-white">
            IF
          </div>
          <div>
            <p className="text-base font-semibold leading-tight text-slate-50">InsightForge</p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
              Research console
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-2xl shadow-black/40 backdrop-blur">
          <div className="mb-5 grid grid-cols-2 gap-1 rounded-lg bg-slate-950/60 p-1 text-sm">
            {[
              { id: "signin", label: "Sign in" },
              { id: "signup", label: "Sign up" }
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setMode(tab.id);
                  setError(null);
                  setNotice(null);
                }}
                className={clsx(
                  "rounded-md px-3 py-1.5 font-medium transition",
                  mode === tab.id
                    ? "bg-slate-800 text-slate-50 shadow"
                    : "text-slate-400 hover:text-slate-200"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-slate-400">Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@lab.edu"
                className={INPUT_CLASSES}
              />
            </label>

            <label className="block space-y-1.5">
              <span className="text-xs font-medium text-slate-400">Password</span>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  minLength={6}
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="••••••••"
                  className={`${INPUT_CLASSES} pr-10`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  aria-pressed={showPassword}
                  title={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-lg text-slate-500 transition hover:text-slate-200 focus:outline-none focus-visible:text-sky-400"
                >
                  {showPassword ? (
                    <EyeOff className="size-4" aria-hidden="true" />
                  ) : (
                    <Eye className="size-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </label>

            {error && (
              <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                {error}
              </p>
            )}
            {notice && (
              <p className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                {notice}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {mode === "signin" ? "Sign in" : "Create account"}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-slate-500">
          Every paper, question and answer is scoped to your account.
        </p>
      </div>
    </div>
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
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "rounded-br-sm bg-sky-600 text-white"
            : "rounded-bl-sm border border-slate-800 bg-slate-900 text-slate-200"
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
                  isUser ? "bg-white/15 text-white/80" : "bg-slate-800 text-slate-400"
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
      <div className="flex items-center gap-3 rounded-2xl rounded-bl-sm border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-400">
        <span className="flex gap-1" aria-hidden="true">
          {[0, 150, 300].map((delay) => (
            <span
              key={delay}
              className="size-1.5 animate-bounce rounded-full bg-sky-400"
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
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 bg-slate-900/30 px-6 py-2">
        <p className="truncate text-[11px] text-slate-500">
          <span className="font-medium text-slate-400">Executive brief:</span>{" "}
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
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-[11px] font-medium text-slate-300 transition hover:border-slate-600 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
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
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 px-6 py-4">
        <div>
          <h1 className="text-sm font-semibold text-slate-100">Research Chat</h1>
          <p className="text-xs text-slate-500">
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
              className="appearance-none rounded-lg border border-slate-700 bg-slate-900 py-2 pl-3 pr-9 text-xs text-slate-200 outline-none transition focus:border-sky-500 disabled:opacity-60"
            >
              {!hasDocuments && <option value="">No papers indexed</option>}
              {documents.map((doc) => (
                <option key={doc.id} value={doc.id}>
                  {doc.filename}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-3 top-1/2 size-3.5 -translate-y-1/2 text-slate-500"
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
                ? "border-sky-500/50 bg-sky-500/10 text-sky-300"
                : "border-slate-700 bg-slate-900 text-slate-400 hover:text-slate-200"
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
            className="grid size-9 place-items-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition hover:border-rose-500/40 hover:bg-rose-500/10 hover:text-rose-300 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-slate-700 disabled:hover:bg-slate-900 disabled:hover:text-slate-400"
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
        <div className="border-b border-slate-800 bg-slate-900/20 px-4 py-4 sm:px-6">
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
          {!hasDocuments && (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">
              <BookOpen className="mx-auto size-6 text-slate-500" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-200">No papers indexed yet</p>
              <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
                Upload a PDF with the button above to index it, then pick it in the paper
                selector.
              </p>
            </div>
          )}

          {hasDocuments && !loadingHistory && messages.length === 0 && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-8 text-center">
              <Sparkles className="mx-auto size-6 text-sky-400" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-200">
                Ask about {selected?.filename ?? "this paper"}
              </p>
              <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
                Methods, sample sizes, contamination thresholds, or what the limitations section
                admits. Answers cite the pages they came from.
              </p>
            </div>
          )}

          {loadingHistory && (
            <p className="flex items-center justify-center gap-2 text-xs text-slate-500">
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

      <form onSubmit={submit} className="border-t border-slate-800 bg-slate-950/80 px-4 py-4 sm:px-6">
        <div className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            rows={1}
            value={draft}
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) submit(event);
            }}
            disabled={!hasDocument || sending}
            placeholder={
              hasDocument ? "Ask about methods, results, limitations…" : "Select a paper to start"
            }
            className="max-h-40 min-h-11 flex-1 resize-none rounded-xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send question"
            className="grid size-11 shrink-0 place-items-center rounded-xl bg-sky-600 text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
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

function AnomaliesView({ token }) {
  const [dataset, setDataset] = useState(null);
  const [contamination, setContamination] = useState(0.05);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  async function run() {
    if (!dataset || running) return;
    setRunning(true);
    setError(null);
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
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-sm font-semibold text-slate-100">Outliers &amp; Anomalies</h1>
        <p className="text-xs text-slate-500">
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
            <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-200">{dataset.filename}</p>
                  <p className="text-[11px] text-slate-500">
                    {Number(dataset.row_count ?? 0).toLocaleString()} rows ×{" "}
                    {Number(dataset.col_count ?? 0).toLocaleString()} columns
                  </p>
                </div>

                <button
                  type="button"
                  onClick={run}
                  disabled={running}
                  className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
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
                  className="w-full accent-sky-500"
                />
                <span className="block text-[10px] text-slate-600">
                  Allowed range 0.01 – 0.20, matching the API.
                </span>
              </label>
            </section>
          )}

          {error && (
            <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
              {error}
            </p>
          )}

          {running && !result && (
            <p className="flex items-center gap-2 text-xs text-slate-500">
              <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
              Fitting IsolationForest and scoring each row
            </p>
          )}

          {result ? (
            <Suspense
              fallback={
                <p className="flex items-center gap-2 text-xs text-slate-500">
                  <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                  Loading charts
                </p>
              }
            >
              <AnomalyPanel result={result} />
            </Suspense>
          ) : (
            !dataset && (
              <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center">
                <Activity className="mx-auto size-7 text-slate-500" aria-hidden="true" />
                <p className="mt-3 text-sm font-medium text-slate-200">
                  Upload a dataset to screen it
                </p>
                <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">
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
  const [view, setView] = useState("chat");
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
  const bottomRef = useRef(null);
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
      setSelectedDocId(null);
      setMessages([]);
      return;
    }

    let active = true;
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
      .catch(() => {
        if (active) setDocuments([]);
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

  async function handleSend() {
    const question = draft.trim();
    if (!question || sending || !selectedDocId || !session) return;

    setDraft("");
    setSending(true);
    setMessages((previous) => [...previous, { role: "user", content: question }]);

    try {
      const payload = await sendQuery(selectedDocId, question, session.access_token);
      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: payload.answer,
          citations: payload.citations ?? []
        }
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        { role: "error", content: error?.message ?? "Inference failed" }
      ]);
    } finally {
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

  async function handleExport(format) {
    const latest = reports[0];
    if (!latest || !session || exporting) return;

    setExporting(format);
    setExportError(null);
    try {
      const { blob, filename } = await downloadReport(
        latest.id,
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
      <div className="grid min-h-screen place-items-center text-slate-500">
        <Loader2 className="size-5 animate-spin" aria-label="Loading" />
      </div>
    );
  }

  if (!session) return <AuthView />;

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="flex w-64 shrink-0 flex-col border-r border-slate-800 bg-slate-900/50">
        <div className="flex items-center gap-3 px-5 py-5">
          <div className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 text-sm font-bold text-white">
            IF
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight text-slate-50">InsightForge</p>
            <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">
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
              aria-current={view === id ? "page" : undefined}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                view === id
                  ? "bg-slate-800 text-slate-50"
                  : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>

        <div className="mt-auto border-t border-slate-800 p-3">
          <p className="truncate px-2 pb-2 text-xs text-slate-500">
            {session.user?.email ?? "Signed in"}
          </p>
          <button
            type="button"
            onClick={() => supabase.auth.signOut()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-400 transition hover:bg-rose-500/10 hover:text-rose-300"
          >
            <LogOut className="size-4" aria-hidden="true" />
            Sign Out
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        {view === "chat" ? (
          <ChatPanel
            documents={documents}
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
  );
}
