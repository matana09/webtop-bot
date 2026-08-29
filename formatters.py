"""Convert raw Webtop API responses to Telegram HTML messages."""
import html
import json
import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

ISRAELI_DAYS = {
    1: "ראשון", 2: "שני", 3: "שלישי",
    4: "רביעי", 5: "חמישי", 6: "שישי",
}


def e(text: Any) -> str:
    return html.escape(str(text) if text is not None else "")


def _raw_dump(data: Any) -> str:
    try:
        return html.escape(json.dumps(data, ensure_ascii=False, indent=2)[:600])
    except Exception:
        return html.escape(str(data)[:600])


# ── Schedule ──────────────────────────────────────────────────────────────────

_DAY_LABELS = {1: "א׳", 2: "ב׳", 3: "ג׳", 4: "ד׳", 5: "ה׳", 6: "ו׳"}
_SKIP_SUBJECTS = {"הפסקה", ""}


def _trunc(text: str, n: int) -> str:
    """Truncate Hebrew string to n chars (for table cells)."""
    return text[:n] if len(text) > n else text


def format_schedule(data: Any, week_index: int = 0) -> str:
    """Table view: rows=hours, columns=days. Falls back to classic on error."""
    label = "השבוע" if week_index == 0 else f"שבוע {week_index:+d}"

    if not isinstance(data, dict) or not data.get("status"):
        err = e(data.get("errorDescription", "שגיאה") if isinstance(data, dict) else data)
        return f"🗓️ <b>מערכת שעות</b>\n\nשגיאה: {err}"

    days = data.get("data") or []
    if not days:
        return f"🗓️ <b>מערכת שעות - {e(label)}</b>\n\nלא נמצאו שיעורים"

    # Build matrix: hour_num -> day_idx -> subject
    matrix: dict[int, dict[int, str]] = {}
    day_indices: set[int] = set()

    for day in days:
        day_idx = day.get("dayIndex", 0)
        if day_idx not in _DAY_LABELS:
            continue
        day_indices.add(day_idx)
        for slot in day.get("hoursData") or []:
            hour_num = slot.get("hour")
            if hour_num is None:
                continue
            schedule = slot.get("scheduale") or []
            for lesson in schedule:
                subject = (lesson.get("subject") or "").strip()
                if subject in _SKIP_SUBJECTS:
                    continue
                matrix.setdefault(hour_num, {})[day_idx] = subject
                break  # first real subject per slot

    if not matrix:
        return format_schedule_classic(data, week_index)

    sorted_days = sorted(day_indices)
    sorted_hours = sorted(matrix.keys())

    # Column width: 5 Hebrew chars + 1 space separator
    CW = 5
    SEP = " "

    # Header: "ש׳  א׳    ב׳    ג׳  ..."
    header = "שע" + SEP + SEP.join(_DAY_LABELS[d].ljust(CW) for d in sorted_days)
    divider = "─" * len(header)

    rows = [header, divider]
    for hour in sorted_hours:
        cells = []
        for d in sorted_days:
            subj = matrix.get(hour, {}).get(d, "")
            cells.append(_trunc(subj, CW).ljust(CW) if subj else "·" * 3 + "  ")
        rows.append(f"{hour:<2}" + SEP + SEP.join(cells))

    table = "\n".join(rows)
    return f"🗓️ <b>מערכת שעות - {e(label)}</b>\n\n<pre>{html.escape(table)}</pre>"


def format_schedule_classic(data: Any, week_index: int = 0) -> str:
    """Original list-per-day format. Kept as fallback / checkpoint."""
    label = "השבוע" if week_index == 0 else f"שבוע {week_index:+d}"

    if not isinstance(data, dict) or not data.get("status"):
        err = e(data.get("errorDescription", "שגיאה") if isinstance(data, dict) else data)
        return f"🗓️ <b>מערכת שעות</b>\n\nשגיאה: {err}"

    days = data.get("data") or []
    if not days:
        return f"🗓️ <b>מערכת שעות - {e(label)}</b>\n\nלא נמצאו שיעורים"

    lines = [f"🗓️ <b>מערכת שעות - {e(label)}</b>\n"]

    for day in days:
        day_idx = day.get("dayIndex", 0)
        day_name = ISRAELI_DAYS.get(day_idx, f"יום {day_idx}")
        lines.append(f"\n<b>יום {e(day_name)}:</b>")

        has_lessons = False
        for slot in day.get("hoursData") or []:
            schedule = slot.get("scheduale") or []
            if not schedule:
                continue

            hour_num = slot.get("hour", "")
            seen = set()
            for lesson in schedule:
                subject = lesson.get("subject") or ""
                first = lesson.get("teacherPrivateName") or ""
                last = lesson.get("teacherLastName") or ""
                teacher = f"{first} {last}".strip()
                room = lesson.get("room") or ""

                key = (subject, teacher)
                if key in seen:
                    continue
                seen.add(key)

                line = f"  <code>{hour_num}.</code> {e(subject)}"
                if teacher:
                    line += f" — {e(teacher)}"
                if room:
                    line += f" <i>{e(room)}</i>"
                lines.append(line)
                has_lessons = True

        if not has_lessons:
            lines.append("  אין שיעורים")

    return "\n".join(lines)


# ── Homework + Lessons ────────────────────────────────────────────────────────

def format_homework(data: Any) -> str:
    if not isinstance(data, dict) or not data.get("status"):
        err = e(data.get("errorDescription", "שגיאה") if isinstance(data, dict) else data)
        return f"📚 <b>שיעורי בית</b>\n\nשגיאה: {err}"

    days = data.get("data") or []
    if not days:
        return "📚 <b>שיעורי בית ונושאי שיעור</b>\n\nלא נמצא מידע השבוע"

    lines = ["📚 <b>שיעורי בית ונושאי שיעור</b>\n"]

    for day in days:
        day_idx = day.get("dayIndex", 0)
        day_name = ISRAELI_DAYS.get(day_idx, f"יום {day_idx}")
        date_str = (day.get("date") or "")[:10]

        day_lines = []
        entry_num = 0
        for slot in day.get("hoursData") or []:
            for lesson in slot.get("scheduale") or []:
                subject = e(lesson.get("subject_name") or "")
                teacher = e(lesson.get("teacher") or "")
                topic = e(lesson.get("descClass") or "")
                hw = e(lesson.get("homeWork") or "")

                if not topic and not hw:
                    continue

                entry_num += 1
                line = f"  <code>{entry_num}.</code> <b>{subject}</b>"
                if teacher:
                    line += f" <i>({teacher})</i>"
                day_lines.append(line)
                if topic:
                    day_lines.append(f"    📖 <b>נושא שיעור:</b> {topic[:150]}")
                if hw:
                    day_lines.append(f"    ✏️ <b>שיעורי בית:</b> {hw[:200]}")

        if day_lines:
            lines.append(f"\n<b>יום {e(day_name)}</b> {e(date_str)}:")
            lines.extend(day_lines)

    if len(lines) == 1:
        lines.append("\nלא נמצאו נושאי שיעור או שיעורי בית השבוע")

    return "\n".join(lines)


def format_homework_day(data: Any, day_index: int) -> str:
    """Show homework for a single day with clean formatting."""
    if not isinstance(data, dict) or not data.get("status"):
        err = e(data.get("errorDescription", "שגיאה") if isinstance(data, dict) else data)
        return f"📚 <b>שיעורי בית</b>\n\nשגיאה: {err}"

    days = data.get("data") or []
    day_name = ISRAELI_DAYS.get(day_index, f"יום {day_index}")

    # Find the requested day
    day_data = None
    for day in days:
        if day.get("dayIndex") == day_index:
            day_data = day
            break

    if day_data is None:
        return f"📚 <b>שיעורי בית — יום {e(day_name)}</b>\n\nאין נתונים ליום זה"

    # Format date as DD/MM
    raw_date = (day_data.get("date") or "")[:10]
    try:
        d = date.fromisoformat(raw_date)
        date_fmt = d.strftime("%d/%m")
    except Exception:
        date_fmt = raw_date

    lines = [f"📚 <b>שיעורי בית — יום {e(day_name)} {e(date_fmt)}</b>\n"]

    entries = []
    entry_num = 0
    for slot in day_data.get("hoursData") or []:
        for lesson in slot.get("scheduale") or []:
            subject = e(lesson.get("subject_name") or "")
            topic = e(lesson.get("descClass") or "")
            hw = e(lesson.get("homeWork") or "")

            if not topic and not hw:
                continue

            entry_num += 1
            entry_lines = [f"{entry_num}. <b>{subject}</b>"]
            if topic:
                entry_lines.append(f"   📖 <b>נושא שיעור:</b> {topic[:150]}")
            if hw:
                entry_lines.append(f"   ✏️ <b>שיעורי בית:</b> {hw[:200]}")
            entries.append("\n".join(entry_lines))

    if not entries:
        lines.append("אין שיעורי בית או נושאי שיעור ביום זה")
    else:
        lines.append("\n\n".join(entries))

    return "\n".join(lines)


# ── Notifications ─────────────────────────────────────────────────────────────

def format_notifications(data: Any) -> str:
    items = []
    if isinstance(data, dict):
        for key in ("data", "notifications", "items", "list"):
            v = data.get(key)
            if isinstance(v, list):
                items = v
                break
    elif isinstance(data, list):
        items = data

    if not items:
        logger.warning("notifications empty. raw=%s", _raw_dump(data))
        return f"🔔 <b>התראות</b>\n\nאין התראות חדשות\n\n<pre>{_raw_dump(data)}</pre>"

    lines = [f"🔔 <b>התראות</b> ({len(items)})\n"]
    for item in items[:15]:
        if not isinstance(item, dict):
            continue
        msg = e(item.get("message") or item.get("text") or item.get("content") or item.get("title") or str(item))
        date_str = e(item.get("date") or item.get("time") or item.get("createdAt") or "")
        lines.append(f"• {msg[:200]}")
        if date_str:
            lines.append(f"  <i>{date_str}</i>")

    return "\n".join(lines)


# ── Messages ──────────────────────────────────────────────────────────────────

_MONTH_NAMES_HE = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}


def _target_month(month_offset: int = 0) -> tuple[int, int]:
    """Return (year, month) for the given offset from today."""
    today = date.today()
    month = today.month + month_offset
    year = today.year
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def _parse_msg_date(msg: dict) -> date | None:
    raw = msg.get("sendingDate") or msg.get("msgTime") or msg.get("date") or ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return date.fromisoformat(raw[:10]) if fmt == "%Y-%m-%d" else \
                   date(*[int(x) for x in raw[:10].replace("/", "-").split("-")][::-1] if "/" in raw[:10] else
                        [int(x) for x in raw[:10].split("-")])
        except Exception:
            continue
    return None


def format_messages(data: Any, month_offset: int = 0) -> str:
    year, month = _target_month(month_offset)
    month_label = f"{_MONTH_NAMES_HE[month]} {year}"

    all_messages = []
    if isinstance(data, dict) and "data" in data:
        d = data["data"]
        if isinstance(d, list):
            all_messages = d
    elif isinstance(data, list):
        all_messages = data

    if not all_messages:
        logger.warning("messages empty. raw=%s", _raw_dump(data))
        return f"📬 <b>הודעות</b>\n\nאין הודעות\n\n<pre>{_raw_dump(data)}</pre>"

    # Filter to target month
    messages = []
    for msg in all_messages:
        if not isinstance(msg, dict):
            continue
        d = _parse_msg_date(msg)
        if d and d.year == year and d.month == month:
            messages.append(msg)
        elif d is None:
            messages.append(msg)  # can't parse date — include anyway

    header = f"📬 <b>הודעות — {e(month_label)}</b>"
    if not messages:
        return f"{header}\n\nאין הודעות בחודש זה"

    lines = [f"{header} ({len(messages)})\n"]
    for msg in messages[:15]:
        f_name = msg.get("student_F_name", "")
        l_name = msg.get("student_L_name", "")
        sender = e(f"{f_name} {l_name}".strip() or msg.get("senderName") or msg.get("sender") or "לא ידוע")
        subject = e(msg.get("subject") or msg.get("title") or "ללא נושא")
        date_str = e(msg.get("sendingDate") or msg.get("msgTime") or msg.get("date") or "")
        is_read = msg.get("hasRead") or msg.get("is_read") or msg.get("read", False)

        icon = "📩" if is_read else "📨"
        lines.append(f"{icon} <b>{subject}</b>")
        lines.append(f"   מאת: {sender}")
        if date_str:
            lines.append(f"   <i>{date_str[:16]}</i>")
        lines.append("")

    return "\n".join(lines)


# ── Discipline ────────────────────────────────────────────────────────────────

def _week_range() -> tuple[date, date]:
    """Return (sunday, saturday) of current Israeli week."""
    today = date.today()
    # weekday(): Mon=0 … Sun=6
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday


def format_discipline(data: Any) -> str:
    if not isinstance(data, dict) or not data.get("status"):
        err = e(data.get("errorDescription", "שגיאה") if isinstance(data, dict) else data)
        return f"📋 <b>אירועי שיעור</b>\n\nשגיאה: {err}"

    inner = data.get("data") or {}
    all_events = inner.get("diciplineEvents") or []

    # Filter to current week only
    week_start, week_end = _week_range()
    events = []
    for ev in all_events:
        raw_date = (ev.get("eventDate") or "")[:10]
        try:
            ev_date = date.fromisoformat(raw_date)
            if week_start <= ev_date <= week_end:
                events.append((ev_date, ev))
        except ValueError:
            pass

    events.sort(key=lambda x: x[0])

    week_str = f"{week_start.strftime('%d/%m/%Y')} – {week_end.strftime('%d/%m/%Y')}"
    lines = [f"📋 <b>אירועי שיעור השבוע</b>\n<i>{week_str}</i>\n"]

    if not events:
        lines.append("לא נמצאו אירועים השבוע")
        return "\n".join(lines)

    for ev_date, ev in events:
        day_name = ISRAELI_DAYS.get(ev_date.isoweekday() % 7 + 1, "")
        date_fmt = ev_date.strftime("%d/%m/%Y")
        event_type = e(ev.get("eventType") or "")
        subject = e(ev.get("subjectName") or "")
        teacher = e(ev.get("teacherName") or "")
        remark = e(ev.get("remark") or "")

        study_group = f"{subject} - {teacher}" if subject and teacher else subject or teacher

        lines.append(f"• <b>{event_type}</b> — יום {e(day_name)}, {date_fmt}")
        if study_group:
            lines.append(f"  {study_group}")
        if remark:
            lines.append(f"  <i>{remark[:150]}</i>")

    return "\n".join(lines)


# ── Grades ────────────────────────────────────────────────────────────────────

def format_grades(data: Any) -> str:
    if not isinstance(data, dict) or not data.get("status"):
        err = e(data.get("errorDescription", "שגיאה") if isinstance(data, dict) else data)
        return f"📊 <b>ציונים</b>\n\nשגיאה: {err}"

    items = data.get("data") or []
    if not items:
        return "📊 <b>ציונים</b>\n\nלא נמצאו ציונים"

    # Group by subject
    by_subject: dict[str, list] = {}
    for item in items:
        if item.get("isDeleted"):
            continue
        subj = item.get("subject") or "כללי"
        by_subject.setdefault(subj, []).append(item)

    lines = ["📊 <b>ציונים</b>\n"]

    for subject, evals in sorted(by_subject.items()):
        lines.append(f"<b>{e(subject)}</b>")
        for ev in sorted(evals, key=lambda x: x.get("date") or ""):
            title     = e(ev.get("title") or "")
            ev_type   = e(ev.get("type") or "")
            raw_date  = (ev.get("date") or "")[:10]
            grade     = ev.get("grade")
            grade_tr  = ev.get("gradeTranslation")
            assessment = ev.get("assessment")
            remark    = e(ev.get("remark") or "")

            try:
                d = date.fromisoformat(raw_date)
                date_fmt = d.strftime("%d/%m/%Y")
            except Exception:
                date_fmt = raw_date

            # Grade display
            if grade is not None:
                grade_str = f"<b>{e(str(grade))}</b>"
            elif grade_tr:
                grade_str = f"<b>{e(grade_tr)}</b>"
            elif assessment:
                grade_str = f"<b>{e(assessment)}</b>"
            else:
                grade_str = "<i>טרם נמסר</i>"

            line = f"  • {e(title)}"
            if ev_type:
                line += f" <i>({ev_type})</i>"
            line += f" — {date_fmt} → {grade_str}"
            lines.append(line)
            if remark:
                lines.append(f"    💬 <i>{remark[:150]}</i>")
        lines.append("")

    return "\n".join(lines).rstrip()
