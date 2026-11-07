---
name: InsightForge
description: A nocturnal research console for cited paper answers, CSV analytics, and anomaly detection.
colors:
  canvas: "#020617"
  surface: "#0f172a"
  surface-raised: "#1e293b"
  line: "#1e293b"
  line-strong: "#334155"
  ink: "#f8fafc"
  ink-secondary: "#e2e8f0"
  ink-muted: "#94a3b8"
  ink-faint: "#64748b"
  accent: "#0ea5e9"
  accent-hover: "#38bdf8"
  accent-deep: "#0284c7"
  accent-partner: "#4f46e5"
  signal-positive: "#10b981"
  signal-negative: "#f43f5e"
typography:
  label:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "10px"
    fontWeight: 500
    letterSpacing: "0.18em"
  meta:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1.4
  body:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  body-large:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  title:
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.3
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
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
    backgroundColor: "{colors.accent-deep}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.accent}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-secondary}"
    typography: "{typography.meta}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item-active:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.xl}"
    padding: "16px"
---

# Design System: InsightForge

## Overview

**Creative North Star: "The Observatory"**

InsightForge is a dark-adapted instrument for looking at things that are hard to see: the passage inside a paper that actually answers the question, the row that does not belong, the count that contradicts the narrative. The surface stays dark so the content carries the light. There is one accent, a sky-blue that leans toward indigo only in the mark, and it is spent almost entirely on the action the user came to take.

The system is quiet and technical. Surfaces are separated by a 1px border and a step of tonal lightness, not by shadow or ornament; a card at rest is a slightly raised piece of the same dark material. Text is a four-step ramp from near-white down to slate-500, and quiet copy is deliberately quiet: the second line of every label, the empty-state explanation, and the metadata all sit at 12px or below, so the numbers and the citations stay dominant.

No light variant exists and none should be invented. The user confirmed the nocturnal, low-glow character and rejected decorative gradients beyond the two-stop mark and the accent pair.

**Key Characteristics:**
- One dark canvas (#020617) with tonal layering, never a second background colour family.
- A single accent pair: sky (#0ea5e9) for action, indigo (#4f46e5) only inside the logo mark.
- 1px slate borders (#1e293b / #334155) do the work shadows usually do.
- Small type for anything secondary; large type reserved for the one thing that matters in the panel.
- Instrument-like radii: 8px on controls, 12–16px on containers, never pill-shaped except status chips.

## Colors

A near-black slate world with a single cool accent, plus two semantic signals that only ever appear as translucent fills and 300-level text.

### Primary
- **Instrument Sky** (#0ea5e9): the only action colour. Filled primary buttons (`bg-sky-600` at rest, `hover:bg-sky-500`), the send button, focus borders (`focus:border-sky-500`), and active/selected control fills at 10% opacity (`bg-sky-500/10` with `text-sky-300`). Its transparent forms mark state; its solid form is reserved for the one primary action per region.
- **Instrument Sky Deep** (#0284c7): the filled button background, one step darker than the accent so white text clears contrast.
- **Mark Indigo** (#4f46e5): exists only as the second stop of the `from-sky-500 to-indigo-600` gradient on the "IF" mark. Never used as a surface, border, or text colour.

### Neutral
- **Observation Black** (#020617): the page canvas and the recessed well behind inputs, tabs, and segmented controls (`bg-slate-950/60`).
- **Deck Slate** (#0f172a): the default card and panel fill, usually at partial opacity (`bg-slate-900/40`, `bg-slate-900/50` for the sidebar) so the canvas shows through.
- **Raised Slate** (#1e293b): the active navigation item and any control that is currently engaged.
- **Hairline** (#1e293b) and **Hairline Strong** (#334155): 1px borders. The first separates regions at rest; the second is for interactive controls (inputs, selects, icon buttons) that must read as touchable.
- **Signal White** (#f8fafc) and **Readout** (#e2e8f0): primary text.
- **Annotation** (#94a3b8) and **Whisper** (#64748b): secondary text, inactive nav, placeholders, and the small explanatory lines under empty states.

### Secondary
- **Verified Green** (#10b981): positive state only — the `Online` status dot and its 10% fill with `emerald-300` text.
- **Alert Rose** (#f43f5e): negative and destructive state only — `Offline`, error banners, the clear-chat action, and destructive hover.

### Named Rules
**The One Accent Rule.** Sky is the only colour allowed to indicate "do this". At most one solid sky element is visible per region; everything else that wants attention uses a hairline, a 10% sky fill, or a step of slate lightness.

**The Gradient Quarantine Rule.** A gradient may appear only inside the "IF" mark. No button, card, header, or background may carry one.

## Typography

**Display Font:** none — the system has no display face.
**Body Font:** system UI stack (`system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
**Label/Mono Font:** none; tabular figures (`tabular-nums`) stand in for a mono face where numbers must line up.

**Character:** Invisible and utilitarian by design. The type is the operating system's own voice, which keeps a data-heavy console feeling like a tool rather than a brand. Hierarchy is carried by size, weight, and colour step — never by a second family.

### Hierarchy
- **Title** (600, 18px, 1.3): pane and section headings, e.g. the anomalies pane heading. Used sparingly; most panels open with an eyebrow instead.
- **Body** (400, 14px, 1.5): chat messages, form values, table cells, button labels. The default size for anything a user reads at length.
- **Body Large** (400, 16px, 1.5): auth screen product name and the largest inline copy.
- **Meta** (500, 11px, 1.4): the status pill text, secondary readouts, and dense table meta.
- **Label** (500, 10px, 0.18em, uppercase): the "Research console" eyebrow. Always uppercase with wide tracking, always `Whisper` (#64748b); it names a region without competing with its content.

### Named Rules
**The Small-Text Rule.** Anything that is not the primary content of its panel is 12px or smaller and sits at `Annotation` or `Whisper`. If secondary text needs to grow to be legible, the panel has too much in it.

**The Tabular Rule.** Any column of numbers gets `tabular-nums`. Digits that do not line up vertically are a defect, not a style choice.

## Layout

A full-height two-column shell: a fixed 256px sidebar (`w-64`, hairline right border, `bg-slate-900/50`) holding the mark, product name, status pill, and the two navigation items, beside a `flex-1` main column that scrolls independently (`overflow-y-auto`, `px-4 py-6 sm:px-6`).

Content inside the main column is centred and width-capped per surface: `max-w-3xl` for the research chat, `max-w-5xl` for the anomalies pane, `max-w-sm` for the centred auth card. The chat composer sits at the bottom of the column as a `max-w-3xl` row, so the input aligns with the conversation above it rather than the full window.

Spacing is a 4px rhythm: 8px between related controls, 12px inside dense controls, 16px for card padding, 24px between blocks, 32px for empty-state padding. Dense grids open up at breakpoints — `sm:grid-cols-2` for KPI cards, `lg:grid-cols-4` for the stat row, `lg:grid-cols-2` for chart pairs.

The sidebar has no mobile collapse: below roughly 768px it keeps its 256px width and squeezes the main column. That is a known gap in the incumbent implementation, not a rule to preserve.

## Elevation & Depth

Tonal layering, not shadow. Depth is expressed by stacking translucent fills on the canvas — canvas (#020617) → card (#0f172a at 40–70%) → engaged control (#1e293b) — and by a 1px hairline wherever two regions meet. Almost nothing lifts.

The single exception is the auth card, the one piece of UI that floats over nothing: `shadow-2xl shadow-black/40` with `backdrop-blur`. That is the only ambient shadow in the system, and it exists because a sign-in card on an empty page needs a boundary the border alone cannot hold.

### Shadow Vocabulary
- **Floating panel** (`box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.4)` with `backdrop-filter: blur(8px)`): auth card only.
- **Focus ring** (`ring-2` with `ring-sky-500/20` and `border-sky-500`): the focus state on any text field or textarea. This is a state, not elevation.

### Named Rules
**The Border-Not-Shadow Rule.** If a surface needs to separate from what is behind it, add a 1px hairline or step the slate lightness. A shadow is only permitted on a panel that floats over an otherwise empty page.

## Shapes

Small, consistent, instrument-like. Controls carry 8px corners (`rounded-lg`), the raised controls inside a panel carry 12px (`rounded-xl`), and containers carry 16px (`rounded-2xl`). The only full-radius element is the status pill, whose shape is what tells you it is a readout and not a button.

Borders are always 1px. Dashed hairlines (`border-dashed border-slate-700`) are the system's way of saying "nothing here yet" — every empty state and the drop zone use them, so a dashed edge reads as an invitation, never as decoration.

Chat bubbles break the radius rule deliberately: a 16px container with one 6px corner (`rounded-br-sm` for the user, `rounded-bl-sm` for the assistant) so the side that belongs to the speaker points at them. That asymmetry is the only place where corners carry meaning.

## Components

### Buttons
- **Shape:** 8px radius (`rounded-lg`) for standard buttons, 12px (`rounded-xl`) for the square send button and icon buttons in the composer.
- **Primary:** solid `#0284c7` (`bg-sky-600`), white text, 14px semibold, `px-4 py-2.5`. One per region.
- **Hover / Focus:** `bg-sky-500` on hover; focus is the field treatment, not a button outline. Disabled drops to 60% opacity with `cursor-not-allowed`, or to a `bg-slate-800` / `text-slate-500` fill for the send button.
- **Secondary / Ghost:** hairline `#334155` border on `#0f172a` with `Annotation` text; hover raises text to `Readout` (#e2e8f0). Engaged state flips to a 10% sky fill with a `border-sky-500/50` border.
- **Destructive:** rose text on a 10% rose fill with a `border-rose-500/30` hairline. Never a solid rose fill.

### Chips
- **Style:** rounded-full, 11px medium, 10% semantic fill plus a matching 30% ring (`ring-1 ring-inset`), semantic 300-level text — the status pill is the canonical chip.
- **State:** `Checking` uses the neutral slate fill with a pulsing dot; `Online` is emerald; `Offline` is rose. The dot and the text always share the semantic family.
- **Segmented controls:** a `bg-slate-950/60` well with 8px radius and 4px padding, holding two equal tabs; the active tab is a raised slate block, not an underline.

### Cards / Containers
- **Corner Style:** 16px (`rounded-2xl`).
- **Background:** `#0f172a` at 40% for panels that sit inside the main column, 70% for the auth card.
- **Shadow Strategy:** none, per Elevation & Depth.
- **Border:** 1px `#1e293b`; dashed `#334155` for empty states and the drop zone.
- **Internal Padding:** 16px standard (`p-4`), 24px for the auth card (`p-6`), 32–40px for empty states.

### Inputs / Fields
- **Style:** 1px `#334155` border, `#020617` at 60% fill (or `#0f172a` solid for the composer), 8px radius, 14px text, `Whisper` placeholder.
- **Focus:** border shifts to `#0ea5e9` plus a `ring-2 ring-sky-500/20` glow. No outline, no shadow.
- **Error / Disabled:** errors are text on a 10% rose fill inside a `border-rose-500/30` container, never a red input border; disabled is 60% opacity.

### Navigation
- **Style:** a vertical list in the 256px sidebar, 8px radius rows, 14px text, 12px horizontal padding, icon plus label with a 12px gap.
- **Default / Hover / Active:** `Annotation` text at rest; hover raises to `Readout` on a `bg-slate-800/60` fill; active is `bg-slate-800` with `Signal White` text and `aria-current="page"`.
- **Mobile treatment:** none — the sidebar stays fixed. The one gap worth fixing before any mobile work.

### Signature: The Citation Readout
The answer block is the component that defines the product. Assistant messages are 14px at 1.5 line-height on a 16px container with `max-w-[85%]`, citations inline as `[page N]`, and the claim is never separated from its source. Anything that would hide a citation — truncation, a collapsed panel, an ellipsis over the page numbers — breaks the system's core promise.

## Do's and Don'ts

### Do:
- **Do** keep the canvas at #020617 and build depth from translucent `#0f172a` fills plus 1px hairlines.
- **Do** spend the accent deliberately: one solid sky action per region, everything else at 10% sky or slate.
- **Do** use dashed `#334155` borders for empty states and drop zones, so "nothing here yet" always looks the same.
- **Do** reach for `tabular-nums` on any numeric column and on the stat readouts.
- **Do** keep secondary copy at 12px or below in `Annotation` or `Whisper`.

### Don't:
- **Don't** introduce a light theme, a second background hue, or a warm neutral.
- **Don't** put a gradient anywhere except the "IF" mark.
- **Don't** use indigo (#4f46e5) outside that gradient, including as a link or hover colour.
- **Don't** add shadows to cards, buttons, or the sidebar; the auth card is the only floating surface.
- **Don't** use a solid rose or a solid emerald fill for anything larger than a status dot or chip.
- **Don't** go above 16px radius outside the pill, and don't use pill shapes for anything except chips and status readouts.
