import { Activity, ArrowRight, Check, Code2, FileText, Paperclip, Send, Sigma } from 'lucide-react'
import SiteNav, { Mark } from './SiteNav'

const TRUST = [
  { icon: FileText, label: 'Page-cited answers, or a refusal' },
  { icon: Sigma, label: 'Statistics computed server-side' },
  { icon: Activity, label: 'Outliers with a contamination dial' },
]

const PROMPTS = [
  'Summarise section 3',
  'Which rows look like outliers?',
  'Compare the two runs',
  'Where is the attention score defined?',
]

const NAV_ITEMS = ['Research Chat', 'Outliers & Anomalies', 'Documents', 'Datasets', 'Reports']

const RECENT = ['attention.pdf', 'detector_readings.csv', 'contamination sweep · 0.08']

const CAPABILITIES = [
  {
    icon: FileText,
    title: 'Answers with a page number',
    body:
      'Chunks are page-tagged and embedded, so every answer cites [page N] with the pages it drew from and how close the match was. When nothing clears the similarity cut-off, the console says the paper does not cover it instead of inventing a passage.',
  },
  {
    icon: Sigma,
    title: 'Counting, not guessing',
    body:
      'The agent never sees raw rows. It receives the pandas summary — row and column counts, missing rate, numeric ranges — as computed JSON, so the numbers in a report are the numbers in your file.',
  },
  {
    icon: Activity,
    title: 'Outliers you can defend',
    body:
      'IsolationForest across numeric columns with a 0.01–0.20 contamination control, median imputation, duplicate removal, and a leakage guard that drops label-like fields before it scores anything.',
  },
]

const STEPS = [
  { step: '01', title: 'Ingest', body: 'Drop in a PDF or CSV. Type, size and row caps are checked before anything is stored.' },
  { step: '02', title: 'Ask', body: 'Question the paper, or hand a goal to the tool-calling agent and let it choose.' },
  { step: '03', title: 'Trace', body: 'Read the citation, the statistic, or the report — every claim points back at its source.' },
]

function Hero() {
  return (
    <section id="top" className="relative isolate overflow-hidden px-6 pt-36 pb-16 sm:pt-44">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="lp-shaft-haze" />
        <div className="lp-shaft-core" />
        <div className="lp-shaft-filament" />
        {/* Keeps the nav and the top edge of the page out of the light. */}
        <div className="absolute inset-x-0 top-0 h-32 bg-gradient-to-b from-[#04070a] via-[#04070a]/85 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-b from-transparent to-[#04070a]/80" />
      </div>

      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-balance text-[42px] font-medium leading-[1.03] tracking-[-0.03em] text-white sm:text-[58px] lg:text-[68px]">
          Ask your papers.
          <br />
          Get the page.
        </h1>

        <p className="mx-auto mt-7 max-w-xl text-pretty text-[15px] leading-relaxed text-slate-300/85">
          One workspace for page-cited answers from your PDFs, honest statistics from your CSVs,
          and the rows that don&apos;t belong — with nothing computed behind your back.
        </p>

        <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <a
            href="/"
            className="group inline-flex items-center justify-center gap-2 rounded-full bg-gradient-to-b from-white to-[#a7f3d0] px-6 py-3 text-sm font-semibold text-[#04120b] shadow-[0_0_40px_-8px_rgba(167,243,208,0.7)] transition hover:shadow-[0_0_54px_-6px_rgba(167,243,208,0.9)]"
          >
            Try the console
            <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
          </a>
          <a
            href="#how"
            className="inline-flex items-center justify-center rounded-full border border-white/15 bg-white/[0.03] px-6 py-3 text-sm font-medium text-slate-200 transition hover:border-white/25 hover:bg-white/[0.06] hover:text-white"
          >
            How it works
          </a>
        </div>

        <ul className="mt-10 flex flex-wrap items-center justify-center gap-x-7 gap-y-3 text-[12.5px] text-slate-400">
          {TRUST.map(({ icon: Icon, label }) => (
            <li key={label} className="flex items-center gap-2">
              <Icon className="size-[14px] text-[#9bf7c4]" strokeWidth={1.6} />
              {label}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function ProductWindow() {
  return (
    <section id="product" className="relative px-4 pb-8 sm:px-6">
      <div className="relative mx-auto max-w-5xl">
        <div className="lp-bloom" aria-hidden="true" />
        {/* Where the shaft meets the window, the light spills along its top edge. */}
        <div
          className="pointer-events-none absolute left-1/2 top-0 h-28 w-[62%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[#c8ffe0]/25 blur-3xl"
          aria-hidden="true"
        />

        {/* Gradient hairline acts as the lit top edge of the window. */}
        <div className="relative rounded-[22px] bg-gradient-to-b from-[#eafff2]/60 via-white/10 to-white/0 p-px shadow-[0_0_140px_-30px_rgba(200,255,224,0.75)]">
          <div className="overflow-hidden rounded-[21px] border border-white/[0.06] bg-[#05090c]">
            <div className="grid md:grid-cols-[200px_1fr] lg:grid-cols-[212px_1fr]">
              <Sidebar />
              <ChatSurface />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function Sidebar() {
  return (
    <aside className="hidden border-r border-white/[0.06] bg-[#070c10]/80 px-3 py-4 md:block">
      <div className="mb-6 flex items-center gap-2.5 px-1">
        <span className="grid size-7 place-items-center rounded-lg bg-gradient-to-br from-sky-500 to-indigo-600 text-[11px] font-bold text-white">
          IF
        </span>
        <span className="text-[13px] font-semibold tracking-tight text-white">InsightForge</span>
      </div>

      <nav className="space-y-0.5">
        {NAV_ITEMS.map((item, index) => (
          <div
            key={item}
            className={
              index === 0
                ? 'relative flex items-center gap-2 rounded-lg bg-gradient-to-r from-white/[0.09] to-transparent px-2.5 py-2 text-[12.5px] font-medium text-white'
                : 'flex items-center gap-2 rounded-lg px-2.5 py-2 text-[12.5px] text-slate-500'
            }
          >
            {index === 0 && <span className="absolute left-0 h-4 w-[2px] rounded-full bg-[#9bf7c4]" />}
            {item}
          </div>
        ))}
      </nav>

      <p className="mt-7 px-2.5 text-[10px] uppercase tracking-[0.18em] text-slate-600">Recent</p>
      <ul className="mt-2 space-y-1.5 px-2.5">
        {RECENT.map((entry) => (
          <li key={entry} className="truncate text-[12px] text-slate-500">
            {entry}
          </li>
        ))}
      </ul>

      <div className="mt-8 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
        <p className="text-[10px] uppercase tracking-[0.18em] text-slate-600">Indexed</p>
        <p className="mt-1.5 font-mono text-[12px] tabular-nums text-slate-300">
          48 pages · 3 datasets
        </p>
      </div>
    </aside>
  )
}

function ChatSurface() {
  return (
    <div className="min-h-[430px] px-4 py-4 sm:px-6">
      <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
        <p className="text-[13px] font-medium text-slate-200">Research Chat</p>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
            <span className="size-1.5 rounded-full bg-emerald-400" />
            Online
          </span>
          <span className="size-6 rounded-full bg-gradient-to-br from-slate-600 to-slate-800" />
        </div>
      </div>

      <div className="mx-auto max-w-xl py-8 text-center">
        <p className="text-[17px] font-medium tracking-tight text-white">Ask the paper</p>
        <p className="mt-1.5 text-[13px] text-slate-500">
          I answer from your uploaded PDFs and cite the page — or tell you it isn&apos;t there.
        </p>

        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {PROMPTS.map((prompt) => (
            <span
              key={prompt}
              className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-2.5 py-1.5 text-[11.5px] text-slate-400"
            >
              {prompt}
            </span>
          ))}
        </div>
      </div>

      <div className="mx-auto max-w-xl space-y-4">
        <div className="flex justify-end">
          <p className="max-w-[85%] rounded-2xl rounded-br-md border border-white/[0.08] bg-white/[0.05] px-3.5 py-2.5 text-[12.5px] leading-relaxed text-slate-200">
            How does multi-head attention differ from a single head?
          </p>
        </div>

        <div className="max-w-[92%]">
          <p className="text-[12.5px] leading-relaxed text-slate-300">
            Multi-head attention projects queries, keys and values into several subspaces and
            attends to them in parallel, so the model can track different relationships at the same
            time.
            <span className="ml-1.5 rounded border border-[#9bf7c4]/30 bg-[#9bf7c4]/10 px-1.5 py-0.5 font-mono text-[10.5px] text-[#c8ffe0]">
              [page 4]
            </span>
          </p>
          <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-600">
            attention.pdf · pages 3–5 · similarity 0.81
          </p>
        </div>
      </div>

      <div className="mx-auto mt-6 max-w-xl rounded-xl border border-white/[0.08] bg-[#0a1014] px-3 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[12px] text-slate-600">Ask a question about your papers…</p>
          <div className="flex items-center gap-1.5">
            <span className="grid size-6 place-items-center rounded-md text-slate-600">
              <Paperclip className="size-3.5" strokeWidth={1.7} />
            </span>
            <span className="grid size-6 place-items-center rounded-md bg-gradient-to-b from-white to-[#a7f3d0] text-[#04120b]">
              <Send className="size-3" strokeWidth={2} />
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

function Capabilities() {
  return (
    <section id="capabilities" className="px-6 py-24">
      <div className="mx-auto max-w-5xl">
        <p className="text-[10px] uppercase tracking-[0.2em] text-[#9bf7c4]">What it does</p>
        <h2 className="mt-4 max-w-2xl text-balance text-[30px] font-medium leading-[1.15] tracking-[-0.02em] text-white sm:text-[38px]">
          Trust is the feature. The rest is plumbing.
        </h2>
        <p className="mt-4 max-w-xl text-[14px] leading-relaxed text-slate-400">
          Three surfaces, one rule: nothing is stated that cannot be pointed at.
        </p>

        <div className="mt-12 grid gap-3 md:grid-cols-3">
          {CAPABILITIES.map(({ icon: Icon, title, body }) => (
            <article
              key={title}
              className="rounded-2xl border border-white/[0.07] bg-white/[0.015] p-6 transition hover:border-white/[0.12] hover:bg-white/[0.025]"
            >
              <span className="grid size-9 place-items-center rounded-xl border border-[#9bf7c4]/20 bg-[#9bf7c4]/[0.07] text-[#9bf7c4]">
                <Icon className="size-4" strokeWidth={1.6} />
              </span>
              <h3 className="mt-5 text-[15px] font-medium tracking-tight text-white">{title}</h3>
              <p className="mt-2.5 text-[13px] leading-relaxed text-slate-400">{body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section id="how" className="px-6 pb-16">
      <div className="mx-auto max-w-5xl">
        <div className="grid gap-8 border-t border-white/[0.07] pt-12 md:grid-cols-3">
          {STEPS.map(({ step, title, body }) => (
            <div key={step}>
              <p className="font-mono text-[11px] tabular-nums text-[#9bf7c4]">{step}</p>
              <h3 className="mt-3 text-[15px] font-medium tracking-tight text-white">{title}</h3>
              <p className="mt-2 text-[13px] leading-relaxed text-slate-400">{body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function ClosingCta() {
  return (
    <section className="relative isolate overflow-hidden px-6 pt-8 pb-24">
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 h-[420px] w-[840px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(200,255,224,0.26),rgba(52,211,153,0.1),transparent)] blur-2xl"
        aria-hidden="true"
      />
      <div className="relative mx-auto max-w-2xl text-center">
        <h2 className="text-balance text-[30px] font-medium leading-[1.12] tracking-[-0.025em] text-white sm:text-[42px]">
          One workspace for papers, data and the outliers in both.
        </h2>
        <p className="mx-auto mt-4 max-w-md text-[14px] leading-relaxed text-slate-400">
          Sign in, ingest, ask, analyse, and read a report whose every claim can be traced back.
        </p>
        <a
          href="/"
          className="group mt-9 inline-flex items-center gap-2 rounded-full bg-gradient-to-b from-white to-[#a7f3d0] px-6 py-3 text-sm font-semibold text-[#04120b] shadow-[0_0_40px_-8px_rgba(167,243,208,0.7)] transition hover:shadow-[0_0_54px_-6px_rgba(167,243,208,0.9)]"
        >
          Open the console
          <ArrowRight className="size-4 transition group-hover:translate-x-0.5" />
        </a>
        <p className="mt-4 flex items-center justify-center gap-1.5 text-[11.5px] text-slate-600">
          <Check className="size-3.5 text-[#9bf7c4]" strokeWidth={2} />
          Bring your own data — nothing leaves the pipeline you run
        </p>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="border-t border-white/[0.06] px-6 py-8">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 text-[12px] text-slate-600 sm:flex-row">
        <div className="flex items-center gap-2.5">
          <Mark className="size-6 text-[10px]" />
          <span>InsightForge · research console</span>
        </div>
        <div className="flex items-center gap-6">
          <a href="#capabilities" className="transition hover:text-slate-300">
            Capabilities
          </a>
          <a href="#how" className="transition hover:text-slate-300">
            How it works
          </a>
          <a
            href="https://github.com/kuntalbhadrdx/insightforge"
            className="flex items-center gap-1.5 transition hover:text-slate-300"
          >
            <Code2 className="size-3.5" strokeWidth={1.7} />
            Source
          </a>
        </div>
      </div>
    </footer>
  )
}

export default function Landing() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-[#04070a] text-slate-200 antialiased selection:bg-[#9bf7c4]/25 selection:text-white">
      <SiteNav />
      <main>
        <Hero />
        <ProductWindow />
        <Capabilities />
        <HowItWorks />
        <ClosingCta />
      </main>
      <Footer />
    </div>
  )
}
