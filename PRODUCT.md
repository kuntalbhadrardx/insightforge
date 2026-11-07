# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

InsightForge is a portfolio and demonstration project, not a live product: the
audience is people evaluating the work — reviewers, recruiters, and engineers
reading the code and trying the console — rather than a daily user base who
depends on it. Confirmed by the project owner.

A secondary audience implied by the feature set is someone with a pile of
papers and a CSV who wants cited answers, a quick dataset read, and outlier
flagging in one session. This is inferred from the built capabilities, not a
confirmed customer segment.

## Product Purpose

An AI research and data-analysis workspace. You upload a PDF and ask grounded,
page-cited questions about it; load a CSV and explore it with pandas summaries
and Plotly charts; flag multi-dimensional outliers with IsolationForest; or
hand a goal to a tool-calling agent that chooses among those capabilities and
writes a Markdown report.

Success for a demo of this kind means the whole loop is observable and
trustworthy in a single sitting: sign in, ingest, ask, analyse, and get a
report whose claims can be traced back to a retrieved page or a computed
statistic.

## Positioning

One workspace for papers, tabular datasets, and anomaly detection — not three
separate tools. Confirmed by the project owner as the mechanism a neighbouring
tool could not truthfully copy.

The trust mechanisms support that position and are part of the shipped
behaviour: answers cite `[page N]` or refuse, and the agent receives computed
JSON statistics rather than raw rows, so it never performs arithmetic of its
own.

## Operating Context

- Sign-in is email + password through Supabase Auth; the console holds the
  access token and sends `Authorization: Bearer <token>` on every backend call.
- Ingest accepts PDFs and CSVs, both validated for size, type, row/column/page
  caps before anything is written.
- Documents, datasets, chat history, agent runs, and reports persist per user in
  Supabase (Postgres + pgvector + Storage).
- The console has two working surfaces: **Research Chat** and **Outliers &
  Anomalies**, plus a backend reachability pill (`Checking` / `Online` /
  `Offline`).
- The frontend is deployed on Vercel and the FastAPI backend on Railway, so the
  browser origin and the API origin differ; CORS is part of normal operation.
- Running locally means a Vite dev server plus uvicorn, against a Supabase
  project whose migrations must be applied.

## Capabilities and Constraints

Confirmed functionality:

- PDF ingestion with page-tagged chunks and 384-d MiniLM embeddings in
  pgvector; retrieval answers cite pages, de-duplicated and similarity-ranked.
- If no chunk clears the similarity cut-off the API retries once unfiltered and
  otherwise states the paper does not cover the question.
- CSV ingest with encoding fallback and a pandas EDA summary; KPI cards for
  rows, columns, missing rate, and model-eligible numeric columns; Plotly
  scatter/line/bar/histogram with sampling above 20k rows.
- IsolationForest anomaly detection with a 0.01–0.20 contamination control,
  median imputation, exact-duplicate removal, and a label-leakage guard that
  excludes columns named like `truth`, `label`, `target`, `is_anomaly`, or `id`
  and re-validates the selection server-side.
- A Groq `openai/gpt-oss-20b` function-calling agent bounded to 4 iterations,
  with `search_papers`, `describe_data`, and `detect_anomalies` tools; every
  call, argument, and result is recorded and reports are persisted.

Constraints:

- Every retrieval and storage path is scoped to the authenticated user id; the
  backend derives it from the validated Supabase JWT.
- Rate limiting is per user id, falling back to IP for anonymous calls.
- The language model is configurable but defaults to Groq `openai/gpt-oss-20b`.

Explicitly undecided: whether the current stack (Supabase, Groq, FastAPI, React
+ Vite) is fixed or open to replacement. The owner left the constraints
question unanswered, so future work must not assume it is settled either way.

## Brand Commitments

The name **InsightForge** and the console's own framing as a "Research console"
are established. No other brand commitment, voice guide, or visual identity was
declared binding.

## Evidence on Hand

- The repository itself: backend modules (`agent.py`, `analytics.py`,
  `pdf_rag.py`, `db.py`, `main.py`), the React console under `frontend/src/`, and
  Supabase migrations under `supabase/`.
- A worked example dataset at `benchmarks/complex_metrics_test.csv` and the
  benchmark material under `benchmarks/`.

Absent, and must not be fabricated: real customers, testimonials, case studies,
press coverage, usage numbers, pricing, or performance benchmarks. Demo content
must be labelled as demo content.

## Product Principles

1. **A claim without a source is a bug.** Answers cite a page or refuse; the
   agent quotes computed statistics instead of doing arithmetic.
2. **One workspace, one session.** Papers, datasets, and outlier detection
   belong together, because the questions people ask span all three.
3. **The trace is the product.** Tool calls, arguments, results, and the report
   are recorded and inspectable, which is what makes the agent trustworthy.
4. **Guardrails live on the server.** Label-leakage exclusion, upload caps, and
   user scoping are enforced in the API, never only in the UI.
5. **Label demo data as demo data.** In a portfolio build, honesty about what is
   real is part of the demonstration.
