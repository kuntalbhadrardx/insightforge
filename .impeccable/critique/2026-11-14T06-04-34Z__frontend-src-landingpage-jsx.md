---
target: insightforge landing page
total_score: 19
max_score: 32
na_heuristics: 7,10
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\kunta\\OneDrive\\Documents\\InsightForge AI\\insightforge\\frontend\\src\\LandingPage.jsx"
target_fingerprint: "sha256:9adf2e576ada220ed6184a04c4a3544ec93cc164b1984e14fcbd6b18bc68aa8c"
target_path: "C:\\Users\\kunta\\OneDrive\\Documents\\InsightForge AI\\insightforge\\frontend\\src\\LandingPage.jsx"
timestamp: 2026-11-14T06-04-34Z
slug: frontend-src-landingpage-jsx
---
# Design Critique — InsightForge landing page

Target: `frontend/src/LandingPage.jsx` (served at `/landing.html`). Mode: Persuade.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | No current-section indicator, and nothing tells a visitor the console requires an account |
| 2 | Match System / Real World | 3 | Language is honest and technical, but "Three surfaces" does not match the five rows the mock shows |
| 3 | User Control and Freedom | 3 | Anchors and scroll work; the header scrolls away and there is no back-to-top |
| 4 | Consistency and Standards | 2 | "Try the console" (hero) and "Open the console" (header, closing) are the same destination under two names |
| 5 | Error Prevention | 2 | Both primary CTAs land on a login wall with no prior signal that an account is needed |
| 6 | Recognition Rather Than Recall | 2 | Every nav link disappears below 768px, and no state marks the section you are in |
| 7 | Flexibility and Efficiency | n/a | Persuade surface; no expert fast path to provide |
| 8 | Aesthetic and Minimalist Design | 3 | Genuinely restrained, but large dead bands and three decorative mint accents dilute the readout logic |
| 9 | Error Recovery | 2 | The page promises the console works; if the API is down, nothing here changes or explains it |
| 10 | Help and Documentation | n/a | Persuade surface; the page body is the documentation |
| **Total** | | **19/32** | **Acceptable (59%)** |

## Design Specificity Verdict

**Authored, not interchangeable.** The light shaft striking a product window, the fragment headline ("Ask your papers. / Get the page."), and a mint that only ever means readout or action are specific to an instrument for reading papers. A generic analytics SaaS could not reuse this page unchanged.

**Deterministic scan:** `impeccable detect --json frontend/src/LandingPage.jsx frontend/src/SiteNav.jsx` returned `[]` with exit 0. The scanner has nothing to say here — contrast, token hygiene and the legacy sky/indigo/emerald palette are all clean. A browser contrast scan over the whole page agreed: zero failures, with seven gradient-background false positives (dark `#04120b` ink on the mint gradient, measured against the gradient base colour at 1.05:1; hand-measured 15:1).

**Visual overlays:** not available. The overlay path needs mutable script injection, which this browser surface does not expose; findings come from the CLI scan plus direct DOM measurement in a fresh tab.

## Overall Impression

The first screen is the best thing in the repo: a confident, specific hero with real restraint, and the mint behaves like an instrument readout rather than a brand colour. The page then loses nerve in the middle. The product window — the only proof on the page — is a mock that invents surfaces the console does not have and shows numbers with no label, which undercuts a project whose stated principle is that nothing is claimed without a source. Below 768px the page drops every navigation link, so the same proof is reachable only by scrolling blind.

## What's Working

1. **The hero earns its size.** 68px at a 1.03 line height with -0.03em tracking, two short lines, and the shaft of light landing behind the type. It reads as a measurement instrument lit from above, not a SaaS template.
2. **Mint is spent like a state.** Two CTAs, the mark, and three reassurance icons — nothing else. The restraint is why the "Open the console" button reads as the only thing to press.
3. **The copy takes positions.** "Trust is the feature. The rest is plumbing." and a refusal being described as a first-class answer are the product's actual thesis; they are stated without hedging or invented proof.

## Priority Issues

**[P1] The mock product window invents surfaces and numbers**
- **What:** The window's sidebar lists Documents, Datasets, Reports — none of which is a console surface — beside Research Chat and Outliers & Anomalies. It also shows a green "Online" chip and an "Indexed · 48 pages · 3 datasets" card.
- **Why it matters:** This is the page's only evidence. PRODUCT.md records two working surfaces plus an Overview, and principle 5 says demo data must be labelled. A reviewer who clicks through finds five nav rows advertised and three present.
- **Fix:** Cut the sidebar to Overview / Research Chat / Outliers & Anomalies, add a quiet caption above or below the window ("Console preview — illustrative data"), and either drop the Indexed card or retitle it to what it is.
- **Suggested command:** `$impeccable clarify`

**[P1] No navigation at all below 768px**
- **What:** `NAV_LINKS` is `hidden md:flex`, "Sign in" is `hidden sm:block`. At 390px the header is a logo and one CTA; the footer links are the only section access on the page.
- **Why it matters:** Mobile visitors cannot jump to Capabilities or How it works, and have no visible sign-in door. The page's argument lives in sections they must scroll past blind.
- **Fix:** Keep a compact trigger below md (a two-line menu button at 44px that opens a full-width panel with the three links and Sign in), or at minimum keep "Sign in" visible at every width.
- **Suggested command:** `$impeccable adapt`

**[P1] The mock window is read aloud, in full, with no context**
- **What:** The `#product` section has no heading, no `aria-label`, and no `aria-hidden` on the decorative chrome. A screen reader user moving past the hero hears the nav rows, four prompt chips, the question, the answer and "attention.pdf · pages 3–5 · similarity 0.81" as page content.
- **Why it matters:** Roughly forty lines of fabricated interface text arrive between the hero and the capabilities — the exact content the page has not labelled as a mock. It is also untethered: there is no heading saying what it is.
- **Fix:** Give the section a real heading ("The console, in one screen") and mark the mock `aria-hidden="true"` with that heading carrying the meaning, or add a `<figure>`/`<figcaption>` pair naming it as a preview.
- **Suggested command:** `$impeccable harden`

**[P2] "How it works" has no heading**
- **What:** The `#how` section opens on a hairline and then three `h3`s (Ingest / Ask / Trace). The nav link and the hero's secondary CTA both jump to an untitled region.
- **Why it matters:** Two entry points land the visitor on an unlabelled block of three columns; the heading outline also skips from the Capabilities `h2` straight into step `h3`s, so assistive tech reads the steps as part of Capabilities.
- **Fix:** Add an `h2` ("Three steps, no black boxes" or simply "How it works") and keep the step titles as `h3` beneath it.
- **Suggested command:** `$impeccable clarify`

**[P2] Two names for one destination**
- **What:** Hero primary says "Try the console"; header and closing say "Open the console". Both point at `/`.
- **Why it matters:** On a page whose argument is precision, the same door under two labels reads as two different offers, and "Try" quietly promises something the login wall does not deliver.
- **Fix:** Pick one verb and use it in all three places; if "Try" stays, the destination or the microcopy must say an account is needed.
- **Suggested command:** `$impeccable clarify`

## Persona Red Flags

**Jordan (First-Timer)**: Reaches the console via "Try the console" and hits a sign-in form with no warning on the landing page that an account is required. Encounters "contamination dial", "similarity 0.81" and "median imputation" without a single plain-language gloss. The only clue that the mock is a mock is that it looks too clean.

**Casey (Mobile)**: At 390px the header offers a logo and one button; the section links and Sign in are gone. The product window drops its sidebar entirely (`hidden md:block`), so the mock shows a lone chat pane with no indication a sidebar exists. The header CTA is 36px tall against a 44px touch floor.

**Riley (Stress Tester)**: Counts five nav rows in the mock and finds three in the console. Notices "Three surfaces, one rule" above a window showing five. Scrolls the footer and finds 18px-tall links. Tabs through the page and finds the mint focus ring only inside `main` — header and footer fall back to the browser's default ring, since `index.css` scopes `:focus-visible` to `:is(main, aside)`.

## Minor Observations

- The "What it does" eyebrow is 10px, under the 11px floor DESIGN.md sets for uppercase labels, and it is mint — decorative, which the Mint-Is-A-State rule forbids.
- Capability icons and the 01/02/03 step numbers are also mint for decoration rather than state.
- Footer links are 18px tall; the header CTA is 36px.
- Between the product window and "What it does" there is roughly 150px of empty black; between the steps and the closing CTA, close to 180px. At 1024 the page reads as padded rather than paced.
- No skip link, no back-to-top; `scroll-behavior: smooth` correctly degrades under `prefers-reduced-motion`.
- `Mark` in `SiteNav` uses `white → #eafff2 → #9bf7c4`; the mock's own "IF" uses `#eafff3 → #9bf7c4`. Two gradients for one mark.

## Questions to Consider

- If the product window is the proof, why is it the one thing on the page that is not true?
- Should the page admit the login wall before the click, the way it admits the similarity cut-off?
- What would the middle of the page look like if the mock had a caption and a heading? Would it need the 150px of silence around it?
