import { useEffect, useRef, useState } from 'react'
import clsx from 'clsx'
import {
  Activity,
  BookOpen,
  ChevronDown,
  Loader2,
  LogOut,
  MessageSquare,
  Send,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { supabase } from './supabase'
import { checkBackend, fetchChatHistory, fetchDocuments, sendQuery } from './api'

const NAV_ITEMS = [
  { id: 'chat', label: 'Research Chat', icon: MessageSquare },
  { id: 'anomalies', label: 'Outliers & Anomalies', icon: Activity },
]

const INPUT_CLASSES =
  'w-full rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20'

function StatusPill({ online }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset',
        online === true && 'bg-emerald-500/10 text-emerald-300 ring-emerald-500/30',
        online === false && 'bg-rose-500/10 text-rose-300 ring-rose-500/30',
        online === null && 'bg-slate-800 text-slate-400 ring-slate-700',
      )}
    >
      <span
        className={clsx(
          'size-1.5 rounded-full',
          online === true && 'bg-emerald-400',
          online === false && 'bg-rose-400',
          online === null && 'animate-pulse bg-slate-500',
        )}
      />
      {online === null ? 'Checking' : online ? 'Online' : 'Offline'}
    </span>
  )
}

function AuthView() {
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const { data, error: authError } =
        mode === 'signin'
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password })

      if (authError) {
        setError(authError.message)
        return
      }
      // Sign-up with email confirmation on: no session until the link is clicked.
      if (mode === 'signup' && !data.session) {
        setNotice('Account created. Confirm your email address, then sign in.')
      }
    } catch (err) {
      setError(
        err?.message ??
          'Could not reach Supabase. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env.',
      )
    } finally {
      setBusy(false)
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
              { id: 'signin', label: 'Sign in' },
              { id: 'signup', label: 'Sign up' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setMode(tab.id)
                  setError(null)
                  setNotice(null)
                }}
                className={clsx(
                  'rounded-md px-3 py-1.5 font-medium transition',
                  mode === tab.id
                    ? 'bg-slate-800 text-slate-50 shadow'
                    : 'text-slate-400 hover:text-slate-200',
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
              <input
                type="password"
                required
                minLength={6}
                autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="••••••••"
                className={INPUT_CLASSES}
              />
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
              {mode === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-xs text-slate-500">
          Every paper, question and answer is scoped to your account.
        </p>
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  if (message.role === 'error') {
    return (
      <div className="mx-auto max-w-full rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-center text-xs text-rose-200">
        {message.content}
      </div>
    )
  }

  const isUser = message.role === 'user'
  const citations = message.citations ?? []

  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'rounded-br-sm bg-sky-600 text-white'
            : 'rounded-bl-sm border border-slate-800 bg-slate-900 text-slate-200',
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
                  'rounded-md px-1.5 py-0.5 text-[11px]',
                  isUser ? 'bg-white/15 text-white/80' : 'bg-slate-800 text-slate-400',
                )}
              >
                p. {citation.page_number}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
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
  )
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
}) {
  const hasDocuments = documents.length > 0
  const hasDocument = Boolean(selectedDocId)
  const canSend = hasDocument && draft.trim().length > 0 && !sending
  const selected = documents.find((doc) => doc.id === selectedDocId)

  function submit(event) {
    event?.preventDefault?.()
    if (canSend) onSend()
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

        <div className="relative">
          <select
            aria-label="Paper"
            value={selectedDocId ?? ''}
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
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-3xl space-y-4">
          {!hasDocuments && (
            <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">
              <BookOpen className="mx-auto size-6 text-slate-500" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-200">No papers indexed yet</p>
              <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-slate-500">
                Upload and index a PDF through the InsightForge API, then reload this page — the
                paper appears in the picker above.
              </p>
            </div>
          )}

          {hasDocuments && !loadingHistory && messages.length === 0 && (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-8 text-center">
              <Sparkles className="mx-auto size-6 text-sky-400" aria-hidden="true" />
              <p className="mt-3 text-sm font-medium text-slate-200">
                Ask about {selected?.filename ?? 'this paper'}
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
              if (event.key === 'Enter' && !event.shiftKey) submit(event)
            }}
            disabled={!hasDocument || sending}
            placeholder={hasDocument ? 'Ask about methods, results, limitations…' : 'Select a paper to start'}
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
  )
}

function AnomaliesView() {
  return (
    <>
      <header className="border-b border-slate-800 px-6 py-4">
        <h1 className="text-sm font-semibold text-slate-100">Outliers &amp; Anomalies</h1>
        <p className="text-xs text-slate-500">Telemetry screening for machine and sensor datasets</p>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-8 sm:px-6">
        <div className="mx-auto max-w-3xl space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: 'Rows screened', value: '—' },
              { label: 'Outliers flagged', value: '—' },
              { label: 'Contamination', value: 'auto' },
            ].map((stat) => (
              <div
                key={stat.label}
                className="rounded-xl border border-slate-800 bg-slate-900/40 px-4 py-3"
              >
                <p className="text-[10px] uppercase tracking-[0.14em] text-slate-500">
                  {stat.label}
                </p>
                <p className="mt-1 text-lg font-semibold text-slate-300">{stat.value}</p>
              </div>
            ))}
          </div>

          <div className="rounded-2xl border border-dashed border-slate-700 bg-slate-900/40 p-10 text-center">
            <ShieldAlert className="mx-auto size-7 text-slate-500" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-slate-200">Anomaly view coming next</p>
            <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-slate-500">
              This panel is a placeholder: it will render IsolationForest scores, flagged rows and
              per-feature contributions for an uploaded telemetry dataset. Nothing is being
              analysed yet.
            </p>
          </div>
        </div>
      </div>
    </>
  )
}

export default function App() {
  const [session, setSession] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [view, setView] = useState('chat')
  const [online, setOnline] = useState(null)
  const [documents, setDocuments] = useState([])
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const bottomRef = useRef(null)

  // Auth gate: restore the stored session, then follow sign-in/sign-out events.
  useEffect(() => {
    let active = true

    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active) setSession(data.session ?? null)
      })
      .catch(() => {
        // Unreachable/placeholder Supabase URL: show the sign-in form rather than a blank page.
      })
      .finally(() => {
        if (active) setAuthChecked(true)
      })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
    })

    return () => {
      active = false
      listener.subscription.unsubscribe()
    }
  }, [])

  // Backend heartbeat for the sidebar status pill.
  useEffect(() => {
    let active = true

    const ping = async () => {
      const ok = await checkBackend()
      if (active) setOnline(ok)
    }

    ping()
    const timer = setInterval(ping, 30000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  // The caller's indexed papers; the chat is scoped to one of them.
  useEffect(() => {
    if (!session) {
      setDocuments([])
      setSelectedDocId(null)
      setMessages([])
      return
    }

    let active = true
    fetchDocuments(session.access_token)
      .then((list) => {
        if (!active) return
        setDocuments(list)
        setSelectedDocId((current) =>
          current && list.some((doc) => doc.id === current) ? current : (list[0]?.id ?? null),
        )
      })
      .catch(() => {
        if (active) setDocuments([])
      })

    return () => {
      active = false
    }
  }, [session])

  // Saved conversation for the selected paper.
  useEffect(() => {
    if (!session || !selectedDocId) {
      setMessages([])
      return
    }

    let active = true
    setLoadingHistory(true)
    fetchChatHistory(selectedDocId, session.access_token)
      .then((payload) => {
        if (!active) return
        setMessages(
          (payload.messages ?? []).map((message) => ({
            role: message.role,
            content: message.content,
            citations: message.citations ?? [],
          })),
        )
      })
      .catch(() => {
        // A paper with no reachable history still works: start from an empty thread.
        if (active) setMessages([])
      })
      .finally(() => {
        if (active) setLoadingHistory(false)
      })

    return () => {
      active = false
    }
  }, [session, selectedDocId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending, loadingHistory])

  async function handleSend() {
    const question = draft.trim()
    if (!question || sending || !selectedDocId || !session) return

    setDraft('')
    setSending(true)
    setMessages((previous) => [...previous, { role: 'user', content: question }])

    try {
      const payload = await sendQuery(selectedDocId, question, session.access_token)
      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          content: payload.answer,
          citations: payload.citations ?? [],
        },
      ])
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        { role: 'error', content: error?.message ?? 'Inference failed' },
      ])
    } finally {
      setSending(false)
    }
  }

  if (!authChecked) {
    return (
      <div className="grid min-h-screen place-items-center text-slate-500">
        <Loader2 className="size-5 animate-spin" aria-label="Loading" />
      </div>
    )
  }

  if (!session) return <AuthView />

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
              aria-current={view === id ? 'page' : undefined}
              className={clsx(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition',
                view === id
                  ? 'bg-slate-800 text-slate-50'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200',
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </nav>

        <div className="mt-auto border-t border-slate-800 p-3">
          <p className="truncate px-2 pb-2 text-xs text-slate-500">
            {session.user?.email ?? 'Signed in'}
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
        {view === 'chat' ? (
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
          />
        ) : (
          <AnomaliesView />
        )}
        <div ref={bottomRef} />
      </main>
    </div>
  )
}
