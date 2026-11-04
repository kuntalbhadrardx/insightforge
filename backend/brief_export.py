"""Markdown brief -> PDF rendering for the export endpoints.

This module is the Streamlit-era exporter, lifted out of ``app.py`` so the
headless API can serve the same files. ``build_brief_pdf`` returns
``(pdf_bytes, error_message)`` with exactly one of them set, which keeps the
route free of layout-level try/except blocks.
"""

from __future__ import annotations

import os
import re
from typing import Any

from fpdf import FPDF
from fpdf.fonts import FontFace

#: MIME type for the Markdown download.
MARKDOWN_MIME = "text/markdown"

#: Unicode TrueType fonts, first match wins. A Windows dev box and a Debian
#: container ship different fonts, so the builder probes known locations and
#: falls back to fpdf2's built-in Helvetica (Latin-1).
_PDF_FONT_CANDIDATES: tuple[tuple[str, str], ...] = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
    ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/segoeuib.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ),
)

#: Characters the built-in fonts cannot encode, mapped to ASCII equivalents.
_PDF_ASCII_FALLBACKS = {
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "–": "-",
    "—": "-",
    "…": "...",
    "•": "-",
    "·": "-",
    "→": "->",
    "←": "<-",
    "≥": ">=",
    "≤": "<=",
    "×": "x",
    "÷": "/",
    "≈": "~",
    "✓": "v",
    "⚠": "!",
    "\u00a0": " ",
}

_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")


def _pdf_safe(text: str, unicode_ok: bool) -> str:
    """Make text renderable: Latin-1-safe when only the built-in fonts exist."""
    if unicode_ok:
        return text
    for bad, good in _PDF_ASCII_FALLBACKS.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", "replace").decode("latin-1")


def _strip_inline_markdown(text: str) -> str:
    """Flatten inline emphasis and links so no stray ``*`` or ``_`` reaches the PDF.

    The agent writes identifiers such as ``p_value`` and ``A_B_test``; passing
    those to a Markdown renderer would silently italicise them.
    """
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", text)
    return text.strip()


def _split_table_row(line: str) -> list[str]:
    """Split a pipe-table row into trimmed cells."""
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def parse_markdown_blocks(markdown_text: str) -> list[tuple[Any, ...]]:
    """Split a brief into renderable blocks: headings, bullets, tables, code…"""
    lines = (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    blocks: list[tuple[Any, ...]] = []
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith("```"):
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            blocks.append(("code", "\n".join(code)))
            continue

        if _TABLE_SEPARATOR.match(stripped):
            # Separator with no header row above it: nothing to render.
            index += 1
            continue

        if (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and _TABLE_SEPARATOR.match(lines[index + 1].strip())
        ):
            rows = [_split_table_row(stripped)]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(_split_table_row(lines[index]))
                index += 1
            blocks.append(("table", rows))
            continue

        heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if heading:
            blocks.append(("heading", len(heading.group(1)), heading.group(2).strip()))
            index += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            blocks.append(("rule",))
            index += 1
            continue

        if re.match(r"^[-*+]\s+", stripped):
            blocks.append(("bullet", re.sub(r"^[-*+]\s+", "", stripped)))
            index += 1
            continue

        numbered = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
        if numbered:
            blocks.append(("numbered", numbered.group(1), numbered.group(2).strip()))
            index += 1
            continue

        if stripped.startswith(">"):
            blocks.append(("quote", stripped.lstrip(">").strip()))
            index += 1
            continue

        paragraph: list[str] = [stripped]
        index += 1
        while index < len(lines):
            following = lines[index].strip()
            if (
                not following
                or following.startswith(("#", "- ", "* ", "+ ", ">", "```", "|"))
                or _TABLE_SEPARATOR.match(following)
                or re.match(r"^\d+[.)]\s+", following)
            ):
                break
            paragraph.append(following)
            index += 1
        blocks.append(("paragraph", " ".join(paragraph)))

    return blocks


class _BriefPDF(FPDF):
    """A4 brief with a page footer; font choice is carried on the instance."""

    brief_title = "InsightForge brief"
    font_family = "Helvetica"
    unicode_ok = False

    def footer(self) -> None:
        self.set_y(-14)
        self.set_font(self.font_family, "", 8)
        self.set_text_color(130, 138, 150)
        label = _pdf_safe(self.brief_title, self.unicode_ok)
        self.cell(0, 6, f"{label[:80]} - page {self.page_no()}/{{nb}}", align="C")


def _register_pdf_font(pdf: FPDF) -> tuple[str, bool]:
    """Register a Unicode TTF when one exists; otherwise keep core Helvetica."""
    for regular, bold in _PDF_FONT_CANDIDATES:
        if not os.path.exists(regular):
            continue
        try:
            pdf.add_font("Brief", "", regular)
            pdf.add_font("Brief", "B", bold if os.path.exists(bold) else regular)
            return "Brief", True
        except Exception:
            continue
    return "Helvetica", False


def _table_column_widths(rows: list[list[str]], total: float) -> list[float]:
    """Size columns by their longest cell so wide text gets the room."""
    columns = max((len(row) for row in rows), default=1)
    weights: list[float] = []
    for column in range(columns):
        longest = max(
            (len(row[column]) for row in rows if column < len(row)), default=1
        )
        weights.append(float(max(4, min(longest, 34))))
    scale = total / sum(weights)
    return [weight * scale for weight in weights]


def build_brief_pdf(
    markdown_text: str, title: str = "InsightForge brief"
) -> tuple[bytes | None, str | None]:
    """Render a Markdown brief to PDF bytes.

    Returns ``(pdf_bytes, error_message)``: exactly one of them is ``None``, so
    the caller can answer with an error instead of raising mid-render.
    """
    if not (markdown_text or "").strip():
        return None, "There is nothing to export yet."

    try:
        pdf = _BriefPDF(format="A4", unit="mm")
        family, unicode_ok = _register_pdf_font(pdf)
        pdf.font_family = family
        pdf.unicode_ok = unicode_ok
        pdf.brief_title = title

        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.set_margins(18, 16, 18)
        pdf.alias_nb_pages()
        pdf.add_page()

        body_color = (31, 36, 48)
        accent_color = (176, 96, 26)
        muted_color = (110, 118, 132)

        pdf.set_font(family, "B", 17)
        pdf.set_text_color(*body_color)
        pdf.multi_cell(0, 8, _pdf_safe(_strip_inline_markdown(title), unicode_ok))
        pdf.ln(2)
        pdf.set_draw_color(220, 224, 232)
        pdf.set_line_width(0.4)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(4)

        for block in parse_markdown_blocks(markdown_text):
            kind = block[0]
            pdf.set_x(pdf.l_margin)

            if kind == "heading":
                level, text = int(block[1]), str(block[2])
                size = {1: 15.5, 2: 13.0, 3: 11.8}.get(level, 11.0)
                pdf.ln(3.0 if level > 1 else 1.0)
                pdf.set_font(family, "B", size)
                pdf.set_text_color(*accent_color)
                pdf.multi_cell(
                    0,
                    size * 0.42,
                    _pdf_safe(_strip_inline_markdown(text), unicode_ok),
                    align="L",
                )
                pdf.set_text_color(*body_color)
                pdf.ln(1.4)

            elif kind in ("bullet", "numbered"):
                text = str(block[-1])
                if kind == "bullet":
                    marker = "•" if unicode_ok else "-"
                else:
                    marker = f"{block[1]}."
                pdf.set_font(family, "", 10.2)
                pdf.set_text_color(*body_color)
                indent = 5.0
                pdf.set_x(pdf.l_margin + indent)
                pdf.multi_cell(
                    pdf.epw - indent,
                    5.4,
                    _pdf_safe(f"{marker} {_strip_inline_markdown(text)}", unicode_ok),
                    align="L",
                )
                pdf.ln(0.8)

            elif kind == "table":
                rows = [
                    [
                        _pdf_safe(_strip_inline_markdown(cell), unicode_ok)
                        for cell in row
                    ]
                    for row in block[1]
                ]
                columns = max(len(row) for row in rows)
                rows = [row + [""] * (columns - len(row)) for row in rows]
                pdf.set_font(family, "", 9.0)
                pdf.set_text_color(*body_color)
                pdf.ln(1.2)
                with pdf.table(
                    width=pdf.epw,
                    col_widths=_table_column_widths(rows, pdf.epw),
                    text_align="LEFT",
                    line_height=5.0,
                    headings_style=FontFace(
                        emphasis="BOLD",
                        fill_color=(240, 242, 246),
                        color=body_color,
                    ),
                    borders_layout="HORIZONTAL_LINES",
                    first_row_as_headings=True,
                ) as table:
                    for row in rows:
                        table_row = table.row()
                        for cell in row:
                            table_row.cell(cell)
                pdf.ln(2.5)

            elif kind == "code":
                pdf.set_font("Courier", "", 8.6)
                pdf.set_text_color(*body_color)
                pdf.set_fill_color(244, 246, 249)
                pdf.multi_cell(
                    pdf.epw,
                    4.6,
                    _pdf_safe(str(block[1]), False),
                    align="L",
                    fill=True,
                )
                pdf.ln(1.8)

            elif kind == "quote":
                pdf.set_font(family, "", 10.0)
                pdf.set_text_color(*muted_color)
                pdf.set_x(pdf.l_margin + 5)
                pdf.multi_cell(
                    pdf.epw - 5,
                    5.4,
                    _pdf_safe(_strip_inline_markdown(str(block[1])), unicode_ok),
                    align="L",
                )
                pdf.set_text_color(*body_color)
                pdf.ln(1.5)

            elif kind == "rule":
                pdf.ln(1.5)
                pdf.set_draw_color(220, 224, 232)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
                pdf.ln(2.5)

            else:  # paragraph
                pdf.set_font(family, "", 10.2)
                pdf.set_text_color(*body_color)
                pdf.multi_cell(
                    0,
                    5.5,
                    _pdf_safe(_strip_inline_markdown(str(block[1])), unicode_ok),
                    align="L",
                )
                pdf.ln(1.8)

        return bytes(pdf.output()), None
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"PDF export failed: {exc}"


__all__ = ["MARKDOWN_MIME", "build_brief_pdf", "parse_markdown_blocks"]
