---
name: InsightForge
description: A nocturnal research console for cited paper answers, CSV analytics, and anomaly detection.
colors:
  canvas: "#04070a"
  surface: "#0a0d10"
  surface-raise: "rgba(255, 255, 255, 0.04)"
  surface-glass: "rgba(255, 255, 255, 0.03)"
  line: "rgba(255, 255, 255, 0.08)"
  line-strong: "rgba(255, 255, 255, 0.12)"
  ink: "#f8fafc"
  ink-secondary: "#cbd5e1"
  ink-muted: "#94a3b8"
  ink-faint: "#7c8ba1"
  accent: "#fdc500"
  accent-light: "#ffe680"
  on-accent: "#0a0800"
  accent-soft: "rgba(253, 197, 0, 0.12)"
  accent-glow: "rgba(253, 197, 0, 0.07)"
  signal-negative: "#f43f5e"
  cutoff: "#cbd5e1"
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "68px"
    fontWeight: 500
    lineHeight: 1.03
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "54px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.03em"
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "15px"
    fontWeight: 500
    lineHeight: 1.3
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.625
  meta:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    letterSpacing: "0.26em"
rounded:
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  panel: "16px"
  glass: "22px"
  auth: "26px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "#fdc500"
    textColor: "{colors.on-accent}"
    typography: "{typography.meta}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.accent-light}"
  button-primary-disabled:
    backgroundColor: "{colors.surface-raise}"
    textColor: "{colors.ink-muted}"
  button-secondary:
    backgroundColor: "{colors.surface-raise}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.meta}"
    rounded: "{rounded.md}"
    padding: "6px 10px"
  input-composer:
    backgroundColor: "{colors.surface-raise}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.xl}"
    padding: "12px 16px"
  nav-item:
    textColor: "{colors.ink-muted}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item-active:
    backgroundColor: "{colors.surface-raise}"
    textColor: "{colors.ink}"
  card:
    backgroundColor: "{colors.surface-glass}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.panel}"
    padding: "16px"
  card-glass:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.glass}"
    padding: "24px"
  chip-online:
    backgroundColor: "{colors.accent-soft}"
    textColor: "{colors.accent}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "4px 10px"
---

# Design System: InsightForge

## Overview

**Creative North Star: "The Observatory"**

InsightForge is a dark-adapted instrument. Its job is to make three hard-to-see things visible in one sitting: the passage inside a paper that actually answers the question, the row that does not belong in a dataset, and the count that contradicts the narrative. The surface stays dark so the content carries the light. There is one signal colour — a sodium yellow that reads as an instrument lamp — and it is spent narrowly: on the action you came to take, the thing you have selected, and the state of the system.

The palette is deliberately two-material. A near-black canvas (`#04070a`) holds glass panels built from white at 2–4.5% opacity, separated by 1px hairlines of white at 8–12%. Nothing in the neutral layer carries hue, which is what lets a saturated yellow survive without shouting. The accent is a gradient (`#ffe680 → #fdc500`) under near-black ink (`#0a0800`); the same gradient lights the logotype. Rose is the only other semantic colour. The anomaly cut-off is deliberately neutral and dashed, because a second warm tone beside this accent would read as a second accent.

The accent is not a hardcoded value. It lives in `frontend/src/index.css` as `--accent`, `--accent-light`, `--on-accent`, `--accent-soft` and `--accent-glow`, exposed both as Tailwind theme colours (`bg-accent`, `text-on-accent`) and as CSS variables for the hand-written stylesheets; `frontend/src/theme.js` mirrors them for Plotly. Re-skinning the console means editing those five lines and nothing else.

The register is quiet and technical, closer to a measurement rig than a SaaS dashboard. Numbers are tabular, labels are small and widely tracked, and secondary copy is achromatic so the readouts stay dominant. The Overview carries the largest type in the product — a 54px "Overview" heading — because it is the one surface where the whole library is the subject.

**Key Characteristics:**
- One dark canvas (`#04070a`); depth comes from white-alpha glass, never from a second background family.
- A single accent, yellow (`#fdc500`), reserved for action, selection, focus and status.
- The accent appears as a light-to-dark gradient under near-black ink; never as a solid fill behind light text.
- 1px white-alpha hairlines do the work shadows usually do; the auth card and chart bars are the only things that glow.
- Small, tracked, uppercase labels for region names; 12px floor for anything a user must read.
- Tabular figures everywhere a column of numbers can appear.

## Colors

A near-black instrument surface, a sodium-yellow readout, and one strictly semantic signal. There is no second accent hue and no light variant.

### Primary
- **Signal Yellow** (`#fdc500`): the only action colour. Primary buttons, status text and dots, active nav icons, focus rings, the flag toggle's pressed state, chart magnitude, and links inside copy. Its 10% and 20% forms mark selection (`bg-accent/10`, `ring-accent/20`); its solid form appears as text weight on the darkest surfaces or as a 1.5px dot.
- **Yellow Light** (`#ffe680`): the light stop of the action gradient, the pressed/hover fill on a solid button, and the highlight end of the logotype. Never a standalone background behind dark text at page scale.
- **Yellow Ink** (`#0a0800`): the near-black brown that sits on yellow — 12.6:1. Button labels, the "IF" mark, user message text, and citation chips inside a user bubble. It is a text colour only, never a surface.
- **Accent Soft / Glow** (`rgba(253, 197, 0, 0.12)` / `0.07`): selection washes and the faint halo behind the sidebar mark. The glow stays at or below 7% because yellow at higher alpha over black turns olive.

### Neutral
- **Canvas Black** (`#04070a`): the page, the composer's sticky footer at 85%, and the mobile header at 95%.
- **Glass Surface** (`rgba(255, 255, 255, 0.03)` / `0.04`): every card, bubble, input, and export bar. Raised states step to `0.06`–`0.07`.
- **Hairline** (`rgba(255, 255, 255, 0.08)`) and **Hairline Strong** (`rgba(255, 255, 255, 0.12)`): the first separates regions at rest, the second outlines interactive controls that must read as touchable.
- **Signal White** (`#f8fafc`) and **Readout Grey** (`#cbd5e1`): headings, answers, and primary values.
- **Annotation** (`#94a3b8`, 7.9:1 on the canvas): secondary text, hints, metadata, axis labels.
- **Whisper** (`#7c8ba1`, 5.8:1): the faintest permitted text — collapsed list meta, chart tick labels, placeholders.

### Secondary
- **Alert Rose** (`#f43f5e`): faults only — offline, error banners, flagged bars, destructive hover. Appears as a 10% fill with 30% ring and 200-level text, never as a large solid.
- **Cut-off Grey** (`#cbd5e1`): exactly one job — the dashed contamination cut-off line and its annotation on the score histogram. It is neutral on purpose: a warm second colour would compete with the accent, and the cut-off is a reference line, not a state.

### Named Rules
**The Yellow-Is-A-State Rule.** The accent marks something the user can do, has selected, or the system is reporting. It is never a decorative accent, a background wash, or a bullet colour. If an accent element is not actionable, selected, or a status, it is wrong.

**The Two-Hue Chart Rule.** A chart uses one hue for magnitude (accent at 30–62% alpha) and rose for anomaly. Never interpolate between accent and rose across a continuous scale — the RGB midpoint between yellow and rose goes muddy brown.

## Typography

**Display Font:** none — the system has no display face.
**Body Font:** system UI stack (`system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`).
**Label/Mono Font:** none; `tabular-nums` stands in for a mono face wherever digits must align, and the landing page uses the system mono stack (`font-mono`) only for step numbers and file metadata.

**Character:** The operating system's own voice, which keeps a data console feeling like a tool rather than a brand. Hierarchy comes from size, weight, tracking, and a four-step grey ramp — never from a second family.

### Hierarchy
- **Display** (500, 68px landing / 42px mobile, 1.03, -0.03em): the landing hero only. Two short lines, balanced wrapping.
- **Headline** (500, 54px desktop / 46px mobile, -0.03em): the Overview title. One per surface.
- **Title** (500–600, 15–19px, 1.3): card and pane headings; 27–30px on the auth card's greeting.
- **Body** (400, 14px, 1.625): chat messages, table cells, form values. Assistant answers cap at `max-w-[85%]` of a 3xl column, holding a 65–75ch measure.
- **Meta** (400, 12px, 1.4): captions, KPI hints, timestamps, upload confirmations.
- **Label** (500, 11px, 0.26em, uppercase): region names ("Research console", "Latest brief", "Jump back in").

### Named Rules
**The 12px Floor Rule.** Anything a user must read is at least 12px. 11px is permitted only for uppercase tracked labels and table headers; nothing below 11px carries information.

**The Tabular Rule.** Any column of numbers — KPI values, table cells, contamination readouts — gets `tabular-nums`. Digits that do not line up vertically are a defect.

## Layout

Two surfaces share one shell. The console is a fixed 256px sidebar (`w-64`, hairline right border) beside a `flex-1 min-w-0` main column that scrolls independently; below `lg` (1024px) the sidebar collapses into a 56px top bar of icon buttons so the main column keeps its width.

Each surface caps its own content: the Overview at `max-w-[1180px]`, chat at `max-w-3xl`, anomalies at `max-w-5xl`, the auth card at `max-w-[520px]`. The composer aligns to the same 3xl column as the conversation so the input never spans the window.

Spacing is a 4px rhythm with a strong preference for tight groups: 8px between related controls, 12px inside dense controls, 16px card padding, 24–32px between blocks, 40px for empty-state padding. Grids open at `sm` (640px) and `lg`: KPI cards go 1 → 2 → 4 across, Overview panels 1 → 3, chart pairs 1 → 2. The Overview's bar chart shows at most seven papers, and the chat's recent lists stop at five and four rows; both are truncation contracts, not pagination.

## Elevation & Depth

Tonal layering plus one real material: glass. Depth is a stack of white-alpha fills on the near-black canvas — canvas → 3% card → 4–7% raised control — with a 1px hairline wherever two regions meet. The Overview's cards add the only texture in the console: a 180° gradient from 4.5% to 1.4% white, an inset 1px top highlight, and a `blur(14px)` backdrop, so they read as lit panes rather than filled rectangles.

Light, not shadow, does the lifting. The Overview's ambient bloom and the landing page's shaft are achromatic: a yellow wash at that size turns brown, so those fields are built from white at low alpha and the accent is left to the elements that mean something. Shadows are limited to the primary action (`0 0 30px -14px` accent at 55%) and the Overview's solid bar (`0 0 26px` accent at 22%). The auth card no longer carries a glow at all.

### Shadow Vocabulary
- **Auth window glow** (retired): the sign-in card used to float on a 150px halo. It now separates with a neutral hairline, because a yellow halo at that size reads brown.
- **Primary action glow** (`box-shadow: 0 0 30px -14px rgba(253, 197, 0, 0.55)`): the sign-in submit and landing CTAs; grows slightly on hover.
- **Top bar highlight** (`box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05)`): Overview cards, the lit edge of the glass.
- **Bar bloom** (`box-shadow: 0 0 26px rgba(253, 197, 0, 0.22)`): the largest library bar only.

### Named Rules
**The Lit-Edge Rule.** A surface separates itself with a hairline or an inset highlight, never a drop shadow. Glows belong to actions and to the one bar that must win the eye.

**The No-Olive Rule.** A yellow surface at low alpha over near-black reads as brown or olive. Below 12% opacity, glow and wash surfaces are drawn in white instead; the accent only covers pixels it means.

## Shapes

Instrument-like and consistent: 8px on standard buttons and nav rows, 10px on icon buttons, 12px on the composer and auth inputs, 14px on the prompt bar, 16px on cards and empty states, 22px on Overview glass cards, 26px on the auth window. Pill radii (`9999px`) are reserved for status chips, the landing CTAs, and the Overview's "Add a paper" button.

Borders are always 1px, and dashed hairlines are the system's way of saying "nothing here yet" — every empty state and both drop zones use `border-dashed`, so a dashed edge reads as an invitation. The contamination cut-off is dashed for a different reason: it is a reference line, so it uses `strokeDasharray "6 4"` in a neutral grey and never the accent.

Chat bubbles break the radius rule on purpose: a 16px container with one 6px corner (`rounded-br-sm` for the user, `rounded-bl-sm` for the assistant) so the square side points at the speaker. That asymmetry is the only place corners carry meaning.

## Components

### Buttons
- **Shape:** 8px on standard actions, 10px on square icon buttons, full radius on the landing CTAs and the Overview's "Add a paper".
- **Primary:** solid `#fdc500` (or the `#ffe680 → #fdc500` gradient on the landing) with `#0a0800` label, 12–13.5px semibold, `px-4 py-2`. One per region: send, run detection, sign in, add a paper.
- **Hover / Focus:** hover lightens to `#ffe680` or `brightness(1.08)`; focus is the global 2px accent outline at 2px offset, never a colour swap. Disabled drops the fill to a `white/10` surface with `#94a3b8` text and `cursor-not-allowed`.
- **Secondary / Ghost:** `white/[0.04]` fill with a `white/10` hairline and `#cbd5e1` text; hover raises the border to `accent/35` and the text to the accent. Destructive hover on the clear-chat button flips to a rose 10% fill with rose-300 text.

### Chips
- **Style:** pill, 11px medium, 10% semantic fill with a 30% inset ring and the 300-level text of the same family.
- **State:** `Online` is accent, `Offline` rose, `Checking` neutral white-alpha with a pulsing dot. The dot and the label always share the family. The Overview's pill is identical in structure with a 11.5px label and reads "API online" / "API offline" / "Checking API".
- **Citation chips:** 11px, `rounded-md`; `white/6` fill with `#94a3b8` text in an assistant bubble, `#0a0800`/10% fill with `#0a0800`/80% text inside an accent user bubble. They sit in a row under a `white/10` divider, with the similarity score on hover.

### Cards / Containers
- **Corner Style:** 16px standard, 22px for Overview glass, 26px for auth.
- **Background:** `white/[0.03]` inside the console; a 4.5%→1.4% white gradient with `blur(14px)` on the Overview.
- **Shadow Strategy:** lit edge only, per Elevation & Depth.
- **Border:** 1px `white/[0.08]`; dashed `white/10` for empty states and drop zones; `accent/50` while a drop zone is armed.
- **Internal Padding:** 16px standard, 20–24px for Overview cards, 32–40px for empty states.

### Inputs / Fields
- **Style:** 1px `white/10` border, `white/[0.04]` fill, 12px radius, 14px text, `#7c8ba1` placeholder. The auth inputs are 44px tall at 13.5px with a 12px radius and the same `#7c8ba1` placeholder (5.6:1 on the input fill).
- **Focus:** border to `accent/55`, fill to `white/[0.045]`, plus a 3px `accent/12` glow. Console inputs additionally take the global focus outline; either the border shift or the outline is sufficient, both appear on the same control.
- **Error / Disabled:** errors are text on a rose 10% fill inside a `rose/30` hairline, stated as an alert with a recovery action. Disabled is 50–60% opacity with `cursor-not-allowed`.

### Navigation
- **Style:** vertical list in the 256px sidebar, 8px rows, 14px text, 12px horizontal padding, icon + label with a 12px gap. Icon-only rows (mobile bar) carry both `aria-label` and `title`.
- **Default / Hover / Active:** `#94a3b8` at rest; hover raises to `#e2e8f0` on `white/4`; active is `white/[0.07]` with a `ring-1` inset `accent/20`, white text, and an accent icon, plus `aria-current="page"`.
- **Mobile treatment:** below `lg` the sidebar is replaced by a single sticky row: the accent mark, three 36px icon buttons (the same active treatment), and a sign-out button pushed right.

### Signature: The Citation Readout
The answer block defines the product. Assistant messages are 14px at 1.625 on a 16px glass bubble capped at 85% width; the claim is never separated from its source, and every citation renders as a chip carrying its page number with the cosine similarity on hover. A refusal is a first-class answer: when nothing clears the similarity cut-off the console says the paper does not cover the question. Truncation, collapsing, or an ellipsis over page numbers breaks the system's core promise.

### Signature: The Overview Plot
Real figures only. Pages-per-paper comes from `/documents`; the tallest paper is a solid accent gradient (`#ffe680 → #fdc500`) with a bloom, the rest are hatched accent (`repeating-linear-gradient(-45deg, accent/50 0 1px, transparent 1px 6px)`) with a 1px bright top edge. Bars sit on a `white/9` baseline over faint `white/5.5` gridlines, show their value above the bar, and reveal a dark tooltip on hover. The plot is a `role="img"` with every value restated in its `aria-label`, and the tooltip is `aria-hidden`.

## Do's and Don'ts

### Do:
- **Do** keep the canvas at `#04070a` and build depth from white-alpha fills plus 1px hairlines.
- **Do** spend the accent on action, selection, focus and status — one solid accent action per region.
- **Do** put near-black `#0a0800` ink on yellow; light text on yellow fails contrast.
- **Do** reach for `bg-accent`, `text-on-accent`, `accent/10` and `ring-accent/20` rather than a hex value, so the hue stays changeable in `index.css`.
- **Do** use dashed `white/10` borders for every empty state and drop zone, so "nothing here yet" always looks the same.
- **Do** reach for `tabular-nums` on any numeric column and on the KPI readouts.
- **Do** keep the 12px floor and use `#94a3b8` / `#7c8ba1` for secondary text rather than a tinted grey.
- **Do** label every figure with its source, and describe an empty state by what will appear — never with placeholder numbers.
- **Do** truncate long filenames and titles with a `title` attribute carrying the full value.

### Don't:
- **Don't** reintroduce `sky`, `indigo`, `slate-900`, or any hued neutral surface; the neutral layer is achromatic white-alpha.
- **Don't** use yellow as a decorative fill, a background wash, or gradient text.
- **Don't** paint a large low-alpha yellow wash: over near-black it reads olive. Use white below 12% opacity.
- **Don't** interpolate a colour scale between the accent and rose; use one hue for magnitude and rose only for flagged data.
- **Don't** colour the anomaly cut-off with a warm tone — it is `#cbd5e1`, dashed `6 4`, and never the accent.
- **Don't** use a solid rose fill for anything larger than a chip, a bar, or an error panel.
- **Don't** add drop shadows to cards, buttons, or the sidebar; the primary action is the only glowing surface.
- **Don't** go above 26px radius, and don't pill anything except chips, status readouts, and the landing CTAs.
- **Don't** hide, collapse, or ellipsize a citation.
