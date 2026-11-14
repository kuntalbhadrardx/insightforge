const NAV_LINKS = [
  { label: 'Product', href: '/landing.html#product' },
  { label: 'Capabilities', href: '/landing.html#capabilities' },
  { label: 'How it works', href: '/landing.html#how' },
]

export function Mark({ className = 'size-9' }) {
  return (
    <span
      className={`grid place-items-center rounded-[10px] bg-gradient-to-br from-white via-accent-light to-accent text-[13px] font-bold tracking-tight text-on-accent ${className}`}
    >
      IF
    </span>
  )
}

export default function SiteNav() {
  return (
    <header className="absolute inset-x-0 top-0 z-30">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <a href="/landing.html" className="flex items-center gap-2.5">
          <Mark />
          <span className="text-[15px] font-semibold tracking-tight text-white">InsightForge</span>
        </a>

        <div className="hidden items-center gap-9 text-[13px] text-slate-300/90 md:flex">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="transition hover:text-white">
              {link.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <a
            href="/auth.html"
            className="hidden min-h-11 items-center rounded-full px-4 text-[13px] text-slate-300 transition hover:text-white sm:inline-flex"
          >
            Sign in
          </a>
          <a
            href="/"
            className="inline-flex min-h-11 items-center rounded-full bg-gradient-to-b from-accent-light to-accent px-4 text-[13px] font-semibold text-on-accent shadow-[0_0_28px_-8px_rgba(253, 197, 0,0.4)] transition hover:brightness-105"
          >
            Open the console
          </a>
        </div>
      </nav>
    </header>
  )
}
