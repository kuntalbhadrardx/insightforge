import { useMemo, useState } from "react";
import clsx from "clsx";
import {
  ArrowRight,
  ArrowUpRight,
  ChevronDown,
  Download,
  FileText,
  Layers,
  Loader2,
  Sparkles,
  Upload
} from "lucide-react";
import "./dashboard.css";

const NUMBER = new Intl.NumberFormat("en-US");

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric"
  });
}

function total(key) {
  return (items) => items.reduce((sum, item) => sum + (item[key] ?? 0), 0);
}

/**
 * One headline number. `value` is passed pre-formatted so the card never has to
 * guess whether it is holding a count, a page total, or "—" for no data.
 */
function Stat({ icon: Icon, label, value, hint }) {
  return (
    <div className="dash-card group relative overflow-hidden p-5">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[12px] font-medium tracking-wide text-slate-400">{label}</p>
        <span className="grid size-7 place-items-center rounded-lg border border-white/10 bg-white/[0.04] text-[#94a3b8]">
          <Icon className="size-3.5" aria-hidden="true" />
        </span>
      </div>
      <p className="mt-4 text-[2.1rem] font-medium leading-none tracking-tight text-white tabular-nums">
        {value}
      </p>
      <p className="dash-secondary mt-2 truncate text-[12px]" title={hint}>
        {hint}
      </p>
    </div>
  );
}

/** Pages-per-paper bars: real figures from /documents, never synthetic. */
function LibraryChart({ documents, error, onUpload, onRetryDocuments }) {
  const bars = useMemo(
    () =>
      [...documents]
        .sort((a, b) => (b.total_pages ?? 0) - (a.total_pages ?? 0))
        .slice(0, 7)
        .map((doc) => ({
          id: doc.id,
          name: doc.filename,
          pages: doc.total_pages ?? 0,
          chunks: doc.chunk_count ?? 0
        })),
    [documents]
  );

  if (error) {
    return (
      <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
        <p className="text-sm text-rose-200">Library unavailable</p>
        <p className="dash-faint max-w-xs break-words text-[12px]">{error}</p>
        {/* The retry lives here rather than in the chat: this card is where the
            failure is reported, so the way out belongs beside it. */}
        <button
          type="button"
          onClick={onRetryDocuments}
          className="mt-2 rounded-full border border-rose-400/40 bg-rose-500/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:bg-rose-500/20"
        >
          Try again
        </button>
      </div>
    );
  }

  if (bars.length === 0) {
    return (
      <div className="flex h-[220px] flex-col items-center justify-center gap-2 text-center">
        <p className="text-sm text-slate-300">No papers indexed yet</p>
        <p className="dash-faint max-w-xs text-[12px]">
          Upload a PDF and its page count appears here the moment ingestion finishes.
        </p>
        <button
          type="button"
          onClick={onUpload}
          className="mt-3 inline-flex min-h-11 items-center gap-1.5 rounded-full bg-accent px-3.5 py-2 text-[12px] font-semibold text-on-accent transition hover:bg-accent-light"
        >
          <Upload className="size-3.5" aria-hidden="true" />
          Upload your first paper
        </button>
      </div>
    );
  }

  const max = Math.max(...bars.map((bar) => bar.pages), 1);
  // The bars are divs, so the figures are restated once for screen readers.
  const chartSummary = bars
    .map((bar) => `${bar.name.replace(/\.pdf$/i, "")}: ${bar.pages} pages`)
    .join("; ");

  return (
    <div className="dash-plot">
      <div className="relative h-[190px]">
        <div className="dash-gridlines" aria-hidden="true" />
        <div
          className="relative flex h-full items-end gap-2 sm:gap-3"
          role="img"
          aria-label={`Pages per paper. ${chartSummary}.`}
        >
        {bars.map((bar, index) => {
          const height = Math.max(6, Math.round((bar.pages / max) * 100));
          return (
            <div key={bar.id} className="dash-bar group relative flex h-full flex-1 items-end">
              <div className="flex w-full flex-col items-center">
                <span className="mb-1.5 text-[11px] tabular-nums text-slate-300">
                  {bar.pages}
                </span>
                <div
                  className={clsx(
                    "w-full rounded-t-[6px]",
                    index === 0 ? "dash-hatch-solid" : "dash-hatch"
                  )}
                  style={{ height: `${(height / 100) * 160}px` }}
                />
              </div>
              <div className="dash-tip absolute bottom-full left-1/2 z-10 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border border-white/10 bg-[#0a0f14]/95 px-2.5 py-1.5 text-[11px] text-slate-200 shadow-xl shadow-black/50" aria-hidden="true">
                {bar.pages} pages · {NUMBER.format(bar.chunks)} chunks
              </div>
            </div>
          );
        })}
        </div>
      </div>
      <div className="dash-baseline flex gap-2 pt-2 sm:gap-3">
        {bars.map((bar) => (
          <p
            key={bar.id}
            className="flex-1 truncate text-center text-[11px] text-slate-400"
            title={bar.name}
          >
            {bar.name.replace(/\.pdf$/i, "")}
          </p>
        ))}
      </div>
    </div>
  );
}

function EmptyRow({ children }) {
  return <p className="dash-faint px-1 py-6 text-center text-[12px]">{children}</p>;
}

export default function Dashboard({
  documents,
  documentsError,
  selectedDocId,
  onSelectDocument,
  reports,
  online,
  onOpenChat,
  onOpenPaper,
  onOpenAnomalies,
  onUpload,
  onExport,
  onRetryDocuments,
  exporting
}) {
  const [question, setQuestion] = useState("");

  const stats = useMemo(() => {
    const pages = total("total_pages")(documents);
    const chunks = total("chunk_count")(documents);
    const newest = documents[0];
    const latestBrief = reports[0];
    return {
      papers: documents.length,
      pages,
      chunks,
      briefs: reports.length,
      avgPages: documents.length ? Math.round(pages / documents.length) : 0,
      newestHint: newest
        ? `Newest · ${formatDate(newest.created_at)}`
        : "Nothing indexed yet",
      pagesHint: documents.length
        ? `${documents.length} paper${documents.length === 1 ? "" : "s"} · avg ${
            documents.length ? Math.round(pages / documents.length) : 0
          } each`
        : "No pages to count yet",
      chunksHint: chunks ? "pgvector · 384-d MiniLM" : "Embeddings appear after upload",
      briefsHint: latestBrief ? latestBrief.title : "No brief saved yet"
    };
  }, [documents, reports]);

  const recentPapers = documents.slice(0, 5);
  const recentBriefs = reports.slice(0, 4);
  const selectedPaper = documents.find((doc) => doc.id === selectedDocId) ?? null;
  const paperLabel = selectedPaper?.filename?.replace(/\.pdf$/i, "") ?? null;
  // A question needs a paper to be grounded in, so the strip names its target.
  const canAsk = Boolean(selectedPaper);

  function handleAsk(event) {
    event.preventDefault();
    const text = question.trim();
    onOpenChat(text);
    setQuestion("");
  }

  return (
    <div className="dash-root relative min-h-screen overflow-x-hidden bg-[#04070a] px-5 pb-14 pt-6 sm:px-8">
      <div className="dash-bloom" aria-hidden="true" />

      <div className="relative mx-auto max-w-[1180px]">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.26em] text-[#94a3b8]">
              Research console
            </p>
            <h1 className="mt-2 text-[2.9rem] font-medium leading-none tracking-[-0.03em] text-white sm:text-[3.4rem]">
              Overview
            </h1>
          </div>

          <div className="flex items-center gap-2.5">
            <span
              role="status"
              aria-live="polite"
              className={clsx(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11.5px]",
                online === true && "border-accent/30 bg-accent/10 text-accent",
                online === false && "border-rose-500/30 bg-rose-500/10 text-rose-300",
                online === null && "border-white/10 bg-white/5 text-slate-400"
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
              {online === null ? "Checking API" : online ? "API online" : "API offline"}
            </span>
            <button
              type="button"
              onClick={onUpload}
                                className="inline-flex min-h-11 items-center gap-2 rounded-full bg-gradient-to-r from-accent-light to-accent px-4 py-2 text-[12.5px] font-semibold text-on-accent transition hover:brightness-105"
            >
              <Upload className="size-3.5" aria-hidden="true" />
              Add a paper
            </button>
          </div>
        </header>

        <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            icon={FileText}
            label="Papers indexed"
            value={NUMBER.format(stats.papers)}
            hint={stats.newestHint}
          />
          <Stat
            icon={Layers}
            label="Pages indexed"
            value={NUMBER.format(stats.pages)}
            hint={stats.pagesHint}
          />
          <Stat
            icon={Sparkles}
            label="Embedded chunks"
            value={NUMBER.format(stats.chunks)}
            hint={stats.chunksHint}
          />
          <Stat
            icon={Download}
            label="Saved briefs"
            value={NUMBER.format(stats.briefs)}
            hint={stats.briefsHint}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
          <section className="dash-card p-6 lg:col-span-2">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-[15px] font-medium text-white">Library</h2>
                <p className="dash-secondary mt-0.5 text-[12px]">
                  Pages per paper, largest first
                </p>
              </div>
              {/* Nothing to open until a paper exists; the upload CTA in the
                  card below is the action that has somewhere to go. */}
              {documents.length > 0 && (
                <button
                  type="button"
                  onClick={() => onOpenChat("")}
                  className="inline-flex min-h-11 items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-[11.5px] text-slate-300 transition hover:border-accent/40 hover:text-accent"
                >
                  Open chat
                  <ArrowUpRight className="size-3" aria-hidden="true" />
                </button>
              )}
            </div>

            <div className="mt-6">
              <LibraryChart
                documents={documents}
                error={documentsError}
                onUpload={onUpload}
                onRetryDocuments={onRetryDocuments}
              />
            </div>

            <form onSubmit={handleAsk} className="dash-prompt mt-6 flex-wrap">
              <Sparkles className="size-4 shrink-0 text-[#94a3b8]" aria-hidden="true" />
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                disabled={!canAsk}
                maxLength={2000}
                placeholder={
                  !canAsk
                    ? "Add a paper to start asking questions"
                    : paperLabel
                      ? `Ask ${paperLabel} about methods, results…`
                      : "What would you like to explore next?"
                }
                aria-label={
                  paperLabel
                    ? `Question for the research chat about ${paperLabel}`
                    : "Question for the research chat"
                }
                className="min-h-11 w-full min-w-0 flex-1 bg-transparent text-[13px] text-slate-100 outline-none placeholder:text-slate-400 sm:w-auto"
              />
              {documents.length > 1 && (
                <div className="relative shrink-0">
                  <select
                    aria-label="Paper this question is about"
                    value={selectedDocId ?? ""}
                    onChange={(event) => onSelectDocument(event.target.value)}
                    className="min-h-11 max-w-[10rem] appearance-none truncate rounded-full border border-white/10 bg-white/[0.04] py-1 pl-2.5 pr-6 text-[11px] text-slate-300 outline-none transition focus:border-accent/50"
                  >
                    {documents.map((doc) => (
                      <option key={doc.id} value={doc.id}>
                        {doc.filename}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    className="pointer-events-none absolute right-2 top-1/2 size-3 -translate-y-1/2 text-slate-400"
                    aria-hidden="true"
                  />
                </div>
              )}
              <button
                type="submit"
                disabled={!canAsk}
                aria-label="Ask in research chat"
                className="grid size-11 shrink-0 place-items-center rounded-full bg-white/10 text-slate-200 transition hover:bg-accent hover:text-on-accent disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ArrowRight className="size-3.5" aria-hidden="true" />
              </button>
            </form>
          </section>

          <div className="grid grid-cols-1 gap-3">
            <section className="dash-card relative overflow-hidden p-6">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                Latest brief
              </p>
              {reports[0] ? (
                <>
                  <h2 className="mt-3 line-clamp-3 text-[19px] font-medium leading-snug text-white">
                    {reports[0].title}
                  </h2>
                  <p className="dash-secondary mt-1.5 text-[12px]">
                    {formatDate(reports[0].created_at)}
                  </p>
                  <div className="mt-5 flex gap-2">
                    {["markdown", "pdf"].map((format) => (
                      <button
                        key={format}
                        type="button"
                        onClick={() => onExport(format, reports[0].id)}
                        disabled={exporting !== null}
                        className="inline-flex min-h-11 flex-1 items-center justify-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-2 text-[11.5px] text-slate-200 transition hover:border-accent/40 hover:text-accent disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {exporting === format ? (
                          <Loader2 className="size-3 animate-spin" aria-hidden="true" />
                        ) : (
                          <Download className="size-3" aria-hidden="true" />
                        )}
                        {format === "pdf" ? "PDF" : "Markdown"}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <div className="mt-4">
                  <p className="text-[13px] text-slate-300">Nothing saved yet</p>
                  <p className="dash-faint mt-1 text-[12px] leading-relaxed">
                    Briefs are written by the agent and can be exported as Markdown or PDF.
                  </p>
                </div>
              )}
            </section>

            <section className="dash-card p-6">
              <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                Jump back in
              </p>
              <div className="mt-3 grid gap-1.5">
                <button
                  type="button"
                  onClick={() => onOpenChat("")}
                  className="dash-action"
                >
                  Research chat
                  <ArrowUpRight className="size-3.5" aria-hidden="true" />
                </button>
                <button type="button" onClick={onOpenAnomalies} className="dash-action">
                  Outliers &amp; anomalies
                  <ArrowUpRight className="size-3.5" aria-hidden="true" />
                </button>
                <button type="button" onClick={onUpload} className="dash-action">
                  Upload a dataset or paper
                  <ArrowUpRight className="size-3.5" aria-hidden="true" />
                </button>
              </div>
            </section>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 lg:grid-cols-3">
          <section className="dash-card p-6 lg:col-span-2">
            <div className="flex items-center justify-between">
              <h2 className="text-[15px] font-medium text-white">Recent papers</h2>
              <span className="dash-faint text-[12px]">
                {documents.length} total
              </span>
            </div>
            {recentPapers.length === 0 ? (
              <EmptyRow>
                {documentsError ? "Library failed to load." : "Upload a PDF and it shows up here."}
              </EmptyRow>
            ) : (
              <ul className="mt-3 divide-y divide-white/[0.06]">
                {recentPapers.map((doc) => (
                  <li key={doc.id}>
                    <button
                      type="button"
                      onClick={() => onOpenPaper(doc.id)}
                      className="group flex w-full items-center gap-3 py-3 text-left"
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-slate-400 transition group-hover:border-accent/40 group-hover:text-accent">
                        <FileText className="size-3.5" aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] text-slate-200 transition group-hover:text-white">
                          {doc.filename}
                        </span>
                        <span className="dash-faint block text-[12px]">
                          {doc.total_pages ?? "—"} pages ·{" "}
                          {NUMBER.format(doc.chunk_count ?? 0)} chunks
                        </span>
                      </span>
                      <span className="dash-faint shrink-0 text-[12px] tabular-nums">
                        {formatDate(doc.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="dash-card p-6">
            <h2 className="text-[15px] font-medium text-white">Recent briefs</h2>
            {recentBriefs.length === 0 ? (
              <EmptyRow>No briefs saved yet.</EmptyRow>
            ) : (
              <ul className="mt-3 space-y-3">
                {recentBriefs.map((report) => (
                  <li key={report.id} className="border-b border-white/[0.06] pb-3 last:border-0 last:pb-0">
                    <p className="line-clamp-2 text-[12.5px] leading-snug text-slate-300">
                      {report.title}
                    </p>
                    <p className="dash-faint mt-1 text-[12px]">
                      {formatDate(report.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
