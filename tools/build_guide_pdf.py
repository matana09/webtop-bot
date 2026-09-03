#!/usr/bin/env python3
"""Render the Webtop bot install guide as an RTL Hebrew A4 PDF.

The bundled skill script covers invoices and receipts only, so this builds a
multi-page technical document instead: headings, wrapped Hebrew paragraphs,
LTR code blocks, RTL tables and callout boxes.

The one rule that matters throughout: wrap the text while it is still in
LOGICAL order, then run get_display() on each finished visual line. Doing it
the other way round — bidi first, wrap second — reorders whole paragraphs and
then slices them at the wrong points, which is what produces the scrambled
Hebrew PDFs this file exists to avoid.
"""
import os
import sys

from bidi.algorithm import get_display
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ── fonts ─────────────────────────────────────────────────────────────────────

_FONTS = {
    "he":   ("C:/Windows/Fonts/arial.ttf",    "HeBody"),
    "heb":  ("C:/Windows/Fonts/arialbd.ttf",  "HeBold"),
    # Courier New, not Consolas: the code samples contain Hebrew string
    # literals, and Consolas ships no Hebrew glyphs — they came out blank.
    "mono": ("C:/Windows/Fonts/cour.ttf",     "Mono"),
}

for path, name in _FONTS.values():
    if not os.path.exists(path):
        sys.exit(
            f"Missing font: {path}\n"
            "These are Windows system fonts. On another platform, point the "
            "_FONTS table at local files instead — the Hebrew faces need the "
            "U+0590-U+05FF range, and the mono face needs it too (see below)."
        )
    pdfmetrics.registerFont(TTFont(name, path))

BODY, BOLD, MONO = "HeBody", "HeBold", "Mono"

# ── palette (matches the bot's own schedule image) ────────────────────────────

C_NAVY   = colors.Color(30 / 255, 58 / 255, 95 / 255)
C_TEXT   = colors.Color(20 / 255, 30 / 255, 45 / 255)
C_MUTED  = colors.Color(90 / 255, 105 / 255, 130 / 255)
C_RULE   = colors.Color(190 / 255, 205 / 255, 220 / 255)
C_CODEBG = colors.Color(243 / 255, 246 / 255, 250 / 255)
C_WARNBG = colors.Color(255 / 255, 244 / 255, 224 / 255)
C_WARNFG = colors.Color(150 / 255, 95 / 255, 20 / 255)
C_TABHDR = colors.Color(237 / 255, 242 / 255, 248 / 255)

# ── geometry ──────────────────────────────────────────────────────────────────

W, H = A4
M_SIDE = 18 * mm
M_TOP = 20 * mm
M_BOT = 20 * mm
RIGHT = W - M_SIDE          # RTL text starts here
LEFT = M_SIDE
CONTENT_W = W - 2 * M_SIDE


LRM = "‎"          # LEFT-TO-RIGHT MARK


def ltr(token):
    """Pin an LTR token inside Hebrew text.

    A filename, flag or setting carries neutral characters at its edges — the
    dot of ".env", the slash of "/myid", the "=" of "TOKEN=". Left alone,
    those neutrals inherit the surrounding RTL direction and jump to the far
    side of the token: ".env" renders as "env.", "TOKEN=" as "=TOKEN".
    Fencing the token between LRM marks holds it together.

    This version of python-bidi rejects the isolate characters (LRI/PDI), so
    LRM is what there is; it works for every case in this document.
    """
    return f"{LRM}{token}{LRM}"


def rtl(text):
    """Visual order for one already-wrapped line.

    The marks have done their job once the reordering is resolved, so they
    are dropped rather than handed to a font that has no glyph for them.
    """
    return get_display(text, base_dir="R").replace(LRM, "")


def _measure(text, font, size):
    return pdfmetrics.stringWidth(text.replace(LRM, ""), font, size)


def wrap(text, font, size, max_w):
    """Greedy wrap in LOGICAL order — bidi is applied later, per line."""
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if _measure(trial, font, size) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


class Doc:
    def __init__(self, path):
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setTitle("Webtop Bot - Hebrew install guide")
        self.page = 0
        self.y = 0
        self._new_page(first=True)

    # ── page furniture ────────────────────────────────────────────────────────

    def _footer(self):
        if self.page == 1:
            return
        self.c.setFont(BODY, 8)
        self.c.setFillColor(C_MUTED)
        self.c.drawRightString(RIGHT, 11 * mm, rtl("מדריך התקנה — בוט Webtop"))
        self.c.drawString(LEFT, 11 * mm, str(self.page))
        self.c.setStrokeColor(C_RULE)
        self.c.setLineWidth(0.5)
        self.c.line(LEFT, 15 * mm, RIGHT, 15 * mm)

    def _new_page(self, first=False):
        if not first:
            self._footer()
            self.c.showPage()
        self.page += 1
        self.y = H - M_TOP
        self.c.setFillColor(C_TEXT)

    def space(self, mm_amount):
        self.y -= mm_amount * mm

    def _need(self, height):
        if self.y - height < M_BOT + 6 * mm:
            self._new_page()

    # ── blocks ────────────────────────────────────────────────────────────────

    def title_page(self, title, subtitle, meta):
        self.c.setFillColor(C_NAVY)
        self.c.rect(0, H - 78 * mm, W, 78 * mm, fill=1, stroke=0)
        self.c.setFillColor(colors.white)
        self.c.setFont(BOLD, 30)
        self.c.drawRightString(RIGHT, H - 40 * mm, rtl(title))
        self.c.setFont(BODY, 14)
        self.c.drawRightString(RIGHT, H - 54 * mm, rtl(subtitle))
        self.y = H - 100 * mm
        self.c.setFillColor(C_TEXT)
        for line in meta:
            self.para(line, size=11)
        self.space(4)

    def h1(self, text):
        # Enough room for the rule and a few lines under it, so a heading is
        # never left stranded alone at the foot of a page.
        self._need(42 * mm)
        self.space(5)
        self.c.setFillColor(C_NAVY)
        self.c.rect(RIGHT - 3 * mm, self.y - 1.5 * mm, 3 * mm, 8 * mm,
                    fill=1, stroke=0)
        self.c.setFont(BOLD, 16)
        self.c.drawRightString(RIGHT - 6 * mm, self.y + 0.5 * mm, rtl(text))
        self.y -= 7 * mm
        self.c.setStrokeColor(C_RULE)
        self.c.setLineWidth(0.7)
        self.c.line(LEFT, self.y, RIGHT, self.y)
        self.y -= 6 * mm
        self.c.setFillColor(C_TEXT)

    def h2(self, text):
        self._need(16 * mm)
        self.space(3)
        self.c.setFillColor(C_NAVY)
        self.c.setFont(BOLD, 12)
        self.c.drawRightString(RIGHT, self.y, rtl(text))
        self.y -= 6 * mm
        self.c.setFillColor(C_TEXT)

    def para(self, text, size=10.5, indent=0, colour=None, font=None):
        font = font or BODY
        lead = size * 1.75
        max_w = CONTENT_W - indent
        for line in wrap(text, font, size, max_w):
            self._need(lead)
            self.c.setFillColor(colour or C_TEXT)
            self.c.setFont(font, size)
            self.c.drawRightString(RIGHT - indent, self.y, rtl(line))
            self.y -= lead
        self.c.setFillColor(C_TEXT)

    def bullet(self, text, size=10.5):
        """A bullet whose marker lives INSIDE the RTL run.

        The marker is PREPENDED in logical order: the first logical character
        of an RTL line is the rightmost one on the page. Appending it — or
        drawing it outside the run, the way a markdown list does — strands it
        on the left, which is how Hebrew bullets usually come out wrong.

        Continuation lines hang clear of the marker instead of running back
        under it.
        """
        lead = size * 1.75
        first_indent = 4 * mm
        hang = first_indent + 5 * mm
        lines = wrap(text, BODY, size, CONTENT_W - hang)
        for n, line in enumerate(lines):
            self._need(lead)
            self.c.setFillColor(C_TEXT)
            self.c.setFont(BODY, size)
            if n == 0:
                self.c.drawRightString(RIGHT - first_indent, self.y,
                                       rtl(f"•  {line}"))
            else:
                self.c.drawRightString(RIGHT - hang, self.y, rtl(line))
            self.y -= lead
        self.space(0.8)

    def code(self, lines, caption=None):
        pad = 3 * mm
        size = 9.5
        lead = size * 1.5
        box_h = len(lines) * lead + 2 * pad
        self._need(box_h + 6 * mm)
        self.space(1.5)
        top = self.y + 3 * mm
        self.c.setFillColor(C_CODEBG)
        self.c.setStrokeColor(C_RULE)
        self.c.setLineWidth(0.6)
        self.c.rect(LEFT, top - box_h, CONTENT_W, box_h, fill=1, stroke=1)
        self.c.setFillColor(C_NAVY)
        self.c.rect(RIGHT - 1.2 * mm, top - box_h, 1.2 * mm, box_h,
                    fill=1, stroke=0)
        # Code is LTR and drawn from the left edge. A Hebrew string literal
        # inside it still needs reordering, but with an LTR base direction so
        # only the Hebrew run flips and the surrounding syntax stays put.
        self.c.setFillColor(C_TEXT)
        self.c.setFont(MONO, size)
        ty = top - pad - size
        for line in lines:
            if any("֐" <= ch <= "׿" for ch in line):
                line = get_display(line, base_dir="L")
            self.c.drawString(LEFT + pad, ty, line)
            ty -= lead
        self.y = top - box_h - 6 * mm
        if caption:
            self.para(caption, size=8.5, colour=C_MUTED)
        self.space(2)

    def note(self, text, kind="note"):
        size = 10
        lead = size * 1.7
        pad = 3 * mm
        lines = wrap(text, BODY, size, CONTENT_W - 2 * pad - 4 * mm)
        box_h = len(lines) * lead + 2 * pad
        self._need(box_h + 6 * mm)
        self.space(1.5)
        top = self.y + 3 * mm
        bg = C_WARNBG if kind == "warn" else C_TABHDR
        edge = C_WARNFG if kind == "warn" else C_NAVY
        self.c.setFillColor(bg)
        self.c.setStrokeColor(bg)
        self.c.rect(LEFT, top - box_h, CONTENT_W, box_h, fill=1, stroke=1)
        self.c.setFillColor(edge)
        self.c.rect(RIGHT - 1.5 * mm, top - box_h, 1.5 * mm, box_h,
                    fill=1, stroke=0)
        self.c.setFillColor(C_WARNFG if kind == "warn" else C_TEXT)
        self.c.setFont(BODY, size)
        ty = top - pad - size
        for line in lines:
            self.c.drawRightString(RIGHT - pad - 2 * mm, ty, rtl(line))
            ty -= lead
        self.y = top - box_h - 3.5 * mm
        self.c.setFillColor(C_TEXT)

    def table(self, header, rows, widths):
        """RTL table: the first column is drawn at the RIGHT edge."""
        size = 9.5
        lead = size * 1.55
        pad = 2 * mm

        def row_h(cells):
            n = 1
            for cell, w in zip(cells, widths):
                n = max(n, len(wrap(cell, BODY, size, w - 2 * pad)))
            return n * lead + 2.5 * mm

        def draw_row(cells, y_top, bold=False, shade=None):
            h = row_h(cells)
            if shade:
                self.c.setFillColor(shade)
                self.c.rect(LEFT, y_top - h, CONTENT_W, h, fill=1, stroke=0)
            x_right = RIGHT
            for cell, w in zip(cells, widths):
                self.c.setFillColor(C_TEXT)
                self.c.setFont(BOLD if bold else BODY, size)
                ty = y_top - pad - size * 0.9
                for line in wrap(cell, BODY, size, w - 2 * pad):
                    self.c.drawRightString(x_right - pad, ty, rtl(line))
                    ty -= lead
                x_right -= w
            self.c.setStrokeColor(C_RULE)
            self.c.setLineWidth(0.5)
            self.c.line(LEFT, y_top - h, RIGHT, y_top - h)
            return h

        self.space(2)
        # Keep the header with a few rows rather than stranding it at a page
        # foot with one line under it.
        self._need(row_h(header) + 34 * mm)
        self.y -= draw_row(header, self.y, bold=True, shade=C_TABHDR)
        for row in rows:
            if self.y - row_h(row) < M_BOT + 6 * mm:
                self._new_page()
                self.y -= draw_row(header, self.y, bold=True, shade=C_TABHDR)
            self.y -= draw_row(row, self.y)
        self.space(3)

    def save(self):
        self._footer()
        self.c.save()
