import { useState } from 'react'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import './landing.css'
import './auth.css'
import { supabase } from './supabase'
import SiteNav, { Mark } from './SiteNav'

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4">
      <path
        fill="#4285F4"
        d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82Z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24Z"
      />
      <path
        fill="#FBBC05"
        d="M5.27 14.29c-.25-.72-.38-1.49-.38-2.29s.14-1.57.38-2.29V6.62H1.29A11.98 11.98 0 0 0 0 12c0 1.94.47 3.77 1.29 5.38l3.98-3.09Z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75Z"
      />
    </svg>
  )
}

function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4" fill="currentColor">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12Z" />
    </svg>
  )
}

// Social sign-in is built but not wired to Supabase yet. Flip this to true once
// the OAuth providers are configured; the buttons, the divider and the note
// come back exactly as they are, and both marks are still defined below.
const SOCIAL_SIGNIN_ENABLED = false

// `embedded` renders the form inside the console shell: no marketing nav, and
// no redirect, because the console's onAuthStateChange picks the session up.
export default function AuthPage({ embedded = false, onAuthenticated }) {
  const [mode, setMode] = useState('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const isSignIn = mode === 'signin'

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const { data, error: authError } = isSignIn
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password })

      if (authError) {
        setError(authError.message)
        return
      }

      // Sign-up with email confirmation on: there is no session until the link is clicked.
      if (!isSignIn && !data.session) {
        setNotice('Account created. Confirm your email address, then sign in.')
        return
      }

      if (embedded) {
        onAuthenticated?.(data.session)
        return
      }

      window.location.assign('/')
    } catch (err) {
      setError(
        err?.message ??
          'Could not reach Supabase. Check VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in .env.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function handleForgot() {
    setError(null)
    setNotice(null)

    if (!email) {
      setError('Enter your email address, then request a reset link.')
      return
    }

    setBusy(true)
    try {
      const { error: resetError } = await supabase.auth.resetPasswordForEmail(email)
      if (resetError) {
        setError(resetError.message)
        return
      }
      setNotice('Reset link sent — check your inbox.')
    } catch (err) {
      setError(err?.message ?? 'Could not reach Supabase to send a reset link.')
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    setMode(isSignIn ? 'signup' : 'signin')
    setError(null)
    setNotice(null)
  }

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#04070a] text-slate-200 antialiased selection:bg-accent/25 selection:text-white">
      {!embedded && <SiteNav secondaryAction />}

      <main
        className={
          embedded
            ? 'relative isolate flex min-h-screen items-center overflow-hidden px-6 py-16'
            : 'relative isolate flex min-h-screen items-center overflow-hidden px-6 py-32'
        }
      >
        <div className="pointer-events-none absolute inset-0 -z-10">
          <div className="lp-shaft-haze" />
          <div className="lp-shaft-core" />
          <div className="auth-dots left-[-3%] top-[16%] hidden h-[520px] w-[320px] sm:block" />
          <div className="auth-dots right-[-3%] bottom-[12%] hidden h-[560px] w-[340px] sm:block" />
          <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-[#04070a] via-[#04070a]/85 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-[#04070a] to-transparent" />
        </div>

        <div className="mx-auto w-full max-w-[520px]">
          <div className="rounded-[26px] bg-gradient-to-b from-white/45 via-white/[0.07] to-white/0 p-px">
            <div className="rounded-[25px] border border-white/[0.04] bg-[#070c0f]/85 px-6 py-9 backdrop-blur-xl sm:px-10 sm:py-10">
              <div className="text-center">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[#94a3b8]">
                  Research console
                </p>
                <h1 className="mt-3 text-[27px] font-medium leading-tight tracking-[-0.02em] text-white sm:text-[30px]">
                  {isSignIn ? 'Welcome back.' : 'Create your account.'}
                </h1>
                <p className="mt-2 text-[13px] text-slate-400">
                  {isSignIn
                    ? 'Sign in to your research console.'
                    : 'One workspace for papers, datasets and outliers.'}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="mt-8">
                <div className="space-y-4">
                  <div>
                    <label htmlFor="email" className="auth-label">
                      Email<span className="auth-required ml-1">*</span>
                    </label>
                    <input
                      id="email"
                      type="email"
                      required
                      autoComplete="email"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="you@example.com"
                      className="auth-input mt-2"
                    />
                  </div>

                  <div>
                    <label htmlFor="password" className="auth-label">
                      Password<span className="auth-required ml-1">*</span>
                    </label>
                    <div className="relative mt-2">
                      <input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        required
                        autoComplete={isSignIn ? 'current-password' : 'new-password'}
                        value={password}
                        onChange={(event) => setPassword(event.target.value)}
                        placeholder="Password"
                        className="auth-input pr-11"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((visible) => !visible)}
                        aria-label={showPassword ? 'Hide password' : 'Show password'}
                        className="absolute right-1.5 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-[#94a3b8] transition hover:bg-white/5 hover:text-slate-300"
                      >
                        {showPassword ? (
                          <EyeOff className="size-4" strokeWidth={1.7} />
                        ) : (
                          <Eye className="size-4" strokeWidth={1.7} />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between gap-4">
                  <label className="flex cursor-pointer items-center gap-2 text-[12.5px] text-slate-400">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(event) => setRemember(event.target.checked)}
                      className="size-3.5 cursor-pointer rounded border-white/20 bg-white/5 [accent-color:var(--accent)]"
                    />
                    Remember me
                  </label>

                  {isSignIn && (
                    <button
                      type="button"
                      onClick={handleForgot}
                      disabled={busy}
                      className="text-[12.5px] text-slate-400 transition hover:text-accent disabled:opacity-60"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>

                {error && (
                  <p
                    role="alert"
                    className="mt-4 rounded-xl border border-rose-400/25 bg-rose-500/10 px-3 py-2 text-[12.5px] leading-relaxed text-rose-200"
                  >
                    {error}
                  </p>
                )}
                {notice && (
                  <p
                    role="status"
                    className="mt-4 rounded-xl border border-accent/25 bg-accent/10 px-3 py-2 text-[12.5px] leading-relaxed text-accent-light"
                  >
                    {notice}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={busy}
                  className="mt-5 flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-accent text-[13.5px] font-semibold text-on-accent shadow-[0_0_30px_-14px_rgba(253, 197, 0,0.55)] transition hover:bg-accent-light disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {busy && <Loader2 className="size-4 animate-spin" />}
                  {isSignIn ? 'Sign in' : 'Create account'}
                </button>
              </form>

              {SOCIAL_SIGNIN_ENABLED && (
                <>
                  <div className="mt-7 flex items-center gap-3">
                <span className="h-px flex-1 bg-white/[0.08]" />
                <span className="text-[10px] uppercase tracking-[0.18em] text-[#7c8ba1]">
                  Or continue with
                </span>
                <span className="h-px flex-1 bg-white/[0.08]" />
              </div>

              <div className="mt-5 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  disabled
                  title="Social sign-in is not enabled yet"
                  className="flex h-11 cursor-not-allowed items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.02] text-[12.5px] font-medium text-slate-400 opacity-70"
                >
                  <GoogleMark />
                  Google
                </button>
                <button
                  type="button"
                  disabled
                  title="Social sign-in is not enabled yet"
                  className="flex h-11 cursor-not-allowed items-center justify-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.02] text-[12.5px] font-medium text-slate-400 opacity-70"
                >
                  <GitHubMark />
                  GitHub
                </button>
              </div>
                  <p className="mt-3 text-center text-[11px] text-[#7c8ba1]">
                    Social sign-in isn&apos;t enabled yet — email and password only.
                  </p>
                </>
              )}

              <p className="mt-7 text-center text-[12.5px] text-[#94a3b8]">
                {isSignIn ? "Don't have an account? " : 'Already have an account? '}
                <button
                  type="button"
                  onClick={switchMode}
                  className="font-medium text-accent transition hover:text-white"
                >
                  {isSignIn ? 'Create one' : 'Sign in'}
                </button>
              </p>
            </div>
          </div>

          {!embedded && (
            <div className="mt-6 flex items-center justify-center gap-2 text-[11.5px] text-[#7c8ba1]">
              <Mark className="size-5 text-[9px]" />
              InsightForge · research console
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
