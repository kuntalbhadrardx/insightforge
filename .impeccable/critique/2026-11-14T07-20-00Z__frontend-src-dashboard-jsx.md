---
target: dashboard (frontend/src/Dashboard.jsx)
total_score: 31
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
target_identity: "file:C:\\Users\\kunta\\OneDrive\\Documents\\InsightForge AI\\insightforge\\frontend\\src\\Dashboard.jsx"
timestamp: 2026-11-14T07-20-00Z
slug: frontend-src-dashboard-jsx
previous: 2026-11-09T09-25-04Z (23/40)
---

## Design Health Score

| # | Heuristic | Score | Was | What changed |
|---|-----------|-------|-----|--------------|
| 1 | Visibility of System Status | 3 | 2 | The failure path is now explicit — "Library unavailable", the reason, and a retry — and the status pill distinguishes online from checking. Still no skeleton while `/documents` is in flight, so zeros still flash. |
| 2 | Match System / Real World | 3 | 3 | Unchanged. "pgvector · 384-d MiniLM" and "chunks" remain engineer vocabulary on a researcher's dashboard. |
| 3 | User Control and Freedom | 3 | 3 | Free navigation, exports, sign-out; the retry adds a way out of the one dead end. |
| 4 | Consistency and Standards | 4 | 2 | One accent, documented in DESIGN.md with named exceptions; the detector reports no anti-patterns on this file. The mint-versus-sky-blue split that cost two points is gone. |
| 5 | Error Prevention | 3 | 2 | The ask strip now names the target paper in its placeholder and carries a paper selector, so a question is no longer sent to "whichever paper happens to be selected". |
| 6 | Recognition Rather Than Recall | 4 | 4 | Recent papers, latest brief and explicit re-entry shortcuts still mean nothing must be remembered. |
| 7 | Flexibility and Efficiency | 2 | 2 | Unchanged. No keyboard shortcuts, no command palette, no bulk actions. |
| 8 | Aesthetic and Minimalist Design | 3 | 3 | Hierarchy is strong; three competing calls to action (Add a paper, Open chat, the ask strip) still share the fold. |
| 9 | Error Recovery | 4 | 2 | A failed `/documents` call is now visibly distinct from an empty library, with the retry beside the failure rather than behind a separate screen. |
| 10 | Help and Documentation | 2 | 1 | Placeholders and hints explain what to ask and what the caps are. There is still no help affordance or glossary, which is what keeps this at 2. |
| **Total** | | **31/40** | **23/40** | **Good** |

## Design Specificity Verdict

Unchanged in kind, stronger in execution: the dashboard is specific to this
product because it counts pages and chunks from a user's own library, and the
Library card is driven by real `/documents` figures rather than synthetic bars.
It would still read as somewhat generic without the copy.

## Remaining P1

**No loading skeleton for the library.** On a cold load the stat tiles show `0`
and the Library card shows its empty state before `/documents` answers, so a slow
API reads as "you have nothing". A skeleton keyed on a `loadingDocuments` flag
would remove the misread.

## Method

Re-scored against the same ten heuristics as the 2026-11-09 pass, by reviewing
the current component against the stored critique. `impeccable detect
frontend/src/Dashboard.jsx --json` returns `[]`, which is the mechanical half of
this; the heuristic scores are a review, not a CLI output, and the "Was" column
is what changed in the code rather than a re-reading of the old prose.
