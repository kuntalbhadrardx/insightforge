---
target: dashboard (frontend/src/Dashboard.jsx)
total_score: 23
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\kunta\\OneDrive\\Documents\\InsightForge AI\\insightforge\\frontend\\src\\Dashboard.jsx"
target_fingerprint: "sha256:24e6790cc08bb18584fc5d0bfb15a276484239ae54ad8481c06bf8a4c7ee74e9"
target_path: "C:\\Users\\kunta\\OneDrive\\Documents\\InsightForge AI\\insightforge\\frontend\\src\\Dashboard.jsx"
timestamp: 2026-11-09T09-25-04Z
slug: frontend-src-dashboard-jsx
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No loading state: zeros and "No papers indexed yet" render before `/documents` answers |
| 2 | Match System / Real World | 3 | "API online", "pgvector · 384-d MiniLM", "chunks" — acceptable for the engineer audience, cryptic for the researcher one |
| 3 | User Control and Freedom | 3 | Free navigation, exports, sign-out; nothing traps the user |
| 4 | Consistency and Standards | 2 | Mint dashboard next to sky-blue chat/anomalies; 22px radii and gradients contradict DESIGN.md |
| 5 | Error Prevention | 2 | The "explore next" bar sends a question to whichever paper happens to be selected |
| 6 | Recognition Rather Than Recall | 4 | Recent papers, latest brief, and explicit re-entry shortcuts mean nothing must be remembered |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts, no command palette, no bulk actions |
| 8 | Aesthetic and Minimalist Design | 3 | Hierarchy is strong; the empty Library card and repeated CTAs waste the fold |
| 9 | Error Recovery | 2 | A failed `/documents` call is indistinguishable from "no papers" — no message, no retry |
| 10 | Help and Documentation | 1 | No contextual help, no explanation of chunks/pages, no help affordance |
| **Total** | | **23/40** | **Acceptable** |

## Design Specificity Verdict

**LLM assessment**: The shell is category-interchangeable — KPI row, one big chart card, right rail, list cards — and it is recognisably the reference composition. What makes it InsightForge is the data: papers, pages, chunks, briefs, API status. The mint world is borrowed from the landing page rather than derived from the console's job, and the chart plots a provenance number (pages per paper) that no researcher acts on. Structure is borrowed; content is authored.

**Deterministic scan**: `impeccable detect` over Dashboard.jsx, App.jsx, auth.css, dashboard.css returned 2 findings, both in the pre-existing sky-blue chat panel of App.jsx (gray-on-color send button, bounce easing) and none in the new dashboard. The browser overlay, however, found 13 anti-patterns on the rendered page: one radial-spotlight glow, one eyebrow chip, two undersized-text flags at 10.5px, and nine low-contrast flags — 4.1:1 and 4.0:1 for `text-slate-500`, and 2.5-2.6:1 for `text-slate-600` on the card gradient.

## Overall Impression

A confident first screen that now belongs to the same product as the landing and auth pages. The single biggest opportunity is honesty of affordance: the dashboard presents a question bar that looks like it understands your workspace, but it hands the question to whichever paper was last selected, and it reports "0 papers" while the list is still loading.

## What's Working

- **The hierarchy is decisive.** A 3.4rem "Overview", a four-up KPI row, then the Library card. Nothing competes with the headline number of each card, and `tabular-nums` keeps every figure aligned.
- **Real data, honestly labelled.** Every KPI derives from `/documents` or `/reports`, and the empty states say what will appear rather than inventing a demo number.
- **Hover tooltips carry the second dimension.** "42 pages · 1,180 chunks" per bar is exactly the density an Operate surface wants.

## Priority Issues

**[P1] Two visual languages in one console.** The dashboard, sidebar, auth and landing are mint on near-black; the chat and anomalies panes are still sky-blue on slate, and DESIGN.md still documents the sky system as binding ("gradient only inside the IF mark", 16px radius cap, no pills). Why it matters: a reviewer moving from Overview to Research Chat sees two products, and the documented system is now false. Fix: commit to the mint world in DESIGN.md and retheme the two panes, or pull the dashboard back to sky. Suggested command: `$impeccable document`, then `$impeccable colorize`.

**[P1] Secondary text fails WCAG AA everywhere it repeats.** `text-slate-600` at 2.5-2.6:1 (dates, "0 total", empty-state explanations, brief copy) and `text-slate-500` at 4.0-4.1:1 (card sublines, axis labels). Why it matters: the dates and counts are the content a visitor is scanning; at 2.5:1 they are decoration. Fix: lift secondary text to `#94a3b8` (7.4:1) and faint to `#7c8ba1` (5.3:1), keeping the four-step ramp. Suggested command: `$impeccable audit`.

**[P1] The "explore next" bar can ask the wrong paper.** Submitting sets the draft and switches to Research Chat, but the paper stays whatever was selected before, so a question about the brief lands in another document's thread with no visible warning. Why it matters: the product's core promise is that every claim is traceable to a source; routing a question to the wrong source silently breaks it. Fix: make the bar choose a paper (or default to the most recent and label it "asking <filename>"), or drop the bar and put the question in the chat where the paper selector lives. Suggested command: `$impeccable harden`.

**[P2] The chart plots a vanity number.** Pages per paper answers "how big is my library", not "what should I do next"; every bar is the same fact in different sizes, and its labels truncate to "retrieval_augmented_gen…" on desktop and "retrieval_…" on mobile. Why it matters: it occupies the largest card on the landing surface of the console and yields no decision. Fix: plot something with a shape — chunks per paper, papers added per week, or briefs over time — and give labels a second line instead of truncating. Suggested command: `$impeccable shape`.

**[P2] First run and loading look identical.** Because `documents` starts as `[]`, the page paints "No papers indexed yet" and four zeros before the request resolves, then jumps. Why it matters: the portfolio's first impression is a skeleton flashing "empty", and a failed fetch is indistinguishable from an empty account. Fix: add an explicit loading state for the KPI row and Library card, and an error line with a retry when the fetch rejects. Suggested command: `$impeccable harden`.

## Persona Red Flags

**Alex (Power User)**: No keyboard path — the prompt bar is a form but there is no shortcut to focus it, no ⌘K, no way to open a paper from the dashboard without a mouse. The "Open chat" pill, the "Research chat" shortcut and the sidebar item all do the same thing, so muscle memory has three targets for one action.

**Sam (Accessibility)**: Nine text runs below 4.5:1, the worst at 2.5:1. The bar tooltip is hover-only, so the chunks figure never reaches a keyboard or screen-reader user. The chart is a set of divs with no `role="img"` or accessible summary, so the single visualization is invisible to assistive tech.

**Jordan (First-Timer)**: "Embedded chunks", "pgvector · 384-d MiniLM" and "API online" are unexplained. "Pages indexed" implies the paper's PDF was fully read; nothing explains what a brief is or who wrote it. On an empty account the largest card is an empty plot, so the first screen teaches nothing about the upload → ask → brief loop.

## Minor Observations

- Three entry points to chat and three to upload dilute the one primary action.
- The sidebar holds a ~500px void between navigation and the account block.
- `+ 2,706` style formatting is applied to counts but dates sit in a different mono-less style; a single numeric voice would read more instrument-like.
- The mint CTA is the only gradient surface; the same button in the chat pane is solid sky.
- Bar caps and the baseline are good; the hatch bars could carry a 1px mint top edge to match the solid bar's weight.

## Questions to Consider

- If the dashboard's job is "what do I do next", why does the largest card describe the past?
- Would the console feel more like one product if the chat pane adopted the mint world, or if the dashboard had stayed sky?
- What would a version look like where the prompt bar knows which paper it is asking?
