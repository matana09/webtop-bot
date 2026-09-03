"""Generate a schedule image (PNG) from Webtop schedule data."""
import io
import os
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display
from schedule_overrides import apply as _apply_overrides
import schedule_times as _sched_times
from schedule_times import HOUR_TIMES as _HOUR_TIMES


def _rtl(text: str) -> str:
    """Prepare Hebrew/RTL text for PIL LTR rendering."""
    return get_display(text)

# ── constants ─────────────────────────────────────────────────────────────────

_DAY_LABELS = {1: "א׳", 2: "ב׳", 3: "ג׳", 4: "ד׳", 5: "ה׳", 6: "ו׳"}
_SKIP_SUBJECTS = {"הפסקה", ""}

# Colors
_C_BG        = (248, 249, 250)
_C_HEADER_BG = (30,  58,  95)
_C_HEADER_FG = (255, 255, 255)
_C_ROW_EVEN  = (255, 255, 255)
_C_ROW_ODD   = (237, 242, 248)
_C_HOUR_BG   = (220, 228, 240)
_C_BORDER    = (190, 205, 220)
_C_SUBJECT   = (15,  30,  60)
_C_TEACHER   = (90,  105, 130)
_C_TOPIC     = (70,  95,  140)
_C_EMPTY     = (200, 210, 225)
_C_TIME      = (70,  90,  130)

# Layout (px)
_HOUR_W   = 90   # wider to fit times
_DAY_W    = 130
_TITLE_H  = 44
_HEADER_H = 52
_ROW_H    = 84
_PADDING  = 6


# ── helpers ───────────────────────────────────────────────────────────────────

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]
    )
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    mid = len(text) // 2
    for delta in range(0, mid + 1):
        for i in [mid - delta, mid + delta]:
            if 0 < i < len(text) and text[i] == " ":
                return [text[:i], text[i + 1:]]
    return [text[:max_chars], text[max_chars:]]


# ── public API ────────────────────────────────────────────────────────────────

def generate_schedule_image(data: Any, week_label: str = "השבוע") -> bytes | None:
    days_raw = (data.get("data") or []) if isinstance(data, dict) else []

    # Build matrix: hour_num -> day_idx -> (subject, teacher, topic)
    matrix: dict[int, dict[int, tuple[str, str, str]]] = {}
    day_indices: set[int] = set()

    for day in days_raw:
        day_idx = day.get("dayIndex", 0)
        if day_idx not in _DAY_LABELS:
            continue
        day_indices.add(day_idx)
        for slot in day.get("hoursData") or []:
            hour = slot.get("hour")
            if hour is None:
                continue
            for lesson in slot.get("scheduale") or []:
                subject = (lesson.get("subject") or "").strip()
                if subject in _SKIP_SUBJECTS:
                    continue
                first   = lesson.get("teacherPrivateName") or ""
                last    = lesson.get("teacherLastName")    or ""
                teacher = f"{first} {last}".strip()
                # Third slot is the unit topic, which only the manual sheet
                # supplies. It has to be present all the same: the renderer
                # unpacks three values, and schedule_overrides pads to three.
                matrix.setdefault(hour, {})[day_idx] = (subject, teacher, "")
                break

    _apply_overrides(matrix, day_indices)

    # RTL layout: days sorted descending → ו׳ leftmost, א׳ rightmost (before hour col)
    # Hour column on the RIGHT (x = n_days * _DAY_W)
    if not matrix:
        return None

    sorted_days  = sorted(day_indices, reverse=True)  # [6,5,4,3,2,1]
    sorted_hours = sorted(matrix.keys())

    n_days  = len(sorted_days)
    n_hours = len(sorted_hours)

    W = _DAY_W * n_days + _HOUR_W
    H = _TITLE_H + _HEADER_H + _ROW_H * n_hours

    img  = Image.new("RGB", (W, H), _C_BG)
    draw = ImageDraw.Draw(img)

    f_title   = _font(22, bold=True)
    f_header  = _font(20, bold=True)
    f_hour    = _font(18, bold=True)
    f_time    = _font(11, bold=False)
    f_subject = _font(15, bold=True)
    f_teacher = _font(13, bold=False)
    f_topic   = _font(12, bold=False)

    DAYS_W = _DAY_W * n_days   # x where hour column starts (rightmost)

    # ── title bar ─────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, _TITLE_H], fill=_C_HEADER_BG)
    draw.text((W // 2, _TITLE_H // 2), _rtl("מערכת שעות"),
              fill=_C_HEADER_FG, font=f_title, anchor="mm")

    # ── column header row ─────────────────────────────────────────────────────
    y0, y1 = _TITLE_H, _TITLE_H + _HEADER_H
    draw.rectangle([0, y0, W, y1], fill=_C_HEADER_BG)

    # Day headers (left portion)
    for i, d in enumerate(sorted_days):
        x  = i * _DAY_W
        cx = x + _DAY_W // 2
        draw.text((cx, (y0 + y1) // 2), _rtl(_DAY_LABELS[d]),
                  fill=_C_HEADER_FG, font=f_header, anchor="mm")
        if i > 0:
            draw.line([x, y0, x, y1], fill=(55, 85, 130), width=1)

    # Divider before hour column
    draw.line([DAYS_W, y0, DAYS_W, y1], fill=(55, 85, 130), width=2)

    # "ש׳" header (rightmost)
    hx = DAYS_W + _HOUR_W // 2
    draw.text((hx, (y0 + y1) // 2), _rtl("ש׳"),
              fill=_C_HEADER_FG, font=f_header, anchor="mm")

    # ── data rows ─────────────────────────────────────────────────────────────
    for r, hour in enumerate(sorted_hours):
        y      = _TITLE_H + _HEADER_H + r * _ROW_H
        row_bg = _C_ROW_EVEN if r % 2 == 0 else _C_ROW_ODD

        draw.rectangle([0, y, W, y + _ROW_H], fill=row_bg)

        # Hour cell (rightmost)
        draw.rectangle([DAYS_W, y, W, y + _ROW_H], fill=_C_HOUR_BG)
        start_t, end_t = _HOUR_TIMES.get(hour, ("", ""))
        # Hour number in upper area
        draw.text((hx, y + 24), str(hour),
                  fill=_C_SUBJECT, font=f_hour, anchor="mm")
        # Times below
        if start_t and end_t:
            draw.text((hx, y + 46), f"{start_t}",
                      fill=_C_TIME, font=f_time, anchor="mm")
            draw.text((hx, y + 60), f"{end_t}",
                      fill=_C_TIME, font=f_time, anchor="mm")

        # Divider before hour column
        draw.line([DAYS_W, y, DAYS_W, y + _ROW_H], fill=_C_BORDER, width=2)

        # Day cells
        for i, d in enumerate(sorted_days):
            x  = i * _DAY_W
            cx = x + _DAY_W // 2

            if i > 0:
                draw.line([x, y, x, y + _ROW_H], fill=_C_BORDER, width=1)

            # Friday's last lesson ends early — say so instead of naming the teacher
            friday_note = (d == _sched_times.FRIDAY_IDX
                           and hour == _sched_times.FRIDAY_LAST_HOUR
                           and _sched_times.FRIDAY_ENDS_AT)

            cell = matrix.get(hour, {}).get(d)
            if cell:
                subject, teacher, topic = cell
                # (text, font, colour, line height) stacked and centred in the cell
                stack = [(ln, f_subject, _C_SUBJECT, 17) for ln in _wrap(subject, 8)]
                if topic:
                    stack += [(ln, f_topic, _C_TOPIC, 14) for ln in _wrap(topic, 20)]
                if teacher and not friday_note:
                    stack.append((teacher, f_teacher, _C_TEACHER, 15))
                if friday_note:
                    stack.append((f"עד {_sched_times.FRIDAY_ENDS_AT}",
                                  f_time, _C_TIME, 14))

                block_h = sum(lh for *_, lh in stack)
                ty = y + (_ROW_H - block_h) // 2
                for text, font, colour, lh in stack:
                    draw.text((cx, ty + lh // 2), _rtl(text),
                              fill=colour, font=font, anchor="mm")
                    ty += lh
            else:
                draw.text((cx, y + _ROW_H // 2), "—",
                          fill=_C_EMPTY, font=f_subject, anchor="mm")

        draw.line([0, y + _ROW_H, W, y + _ROW_H], fill=_C_BORDER, width=1)

    draw.rectangle([0, 0, W - 1, H - 1], outline=_C_BORDER, width=2)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
