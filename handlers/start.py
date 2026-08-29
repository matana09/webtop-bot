import html
from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import MAIN_MENU
from webtop_service import webtop
from schedule_overrides import OVERRIDES as _SCHEDULE_OVERRIDES
import main_screen_state

ISRAELI_DAYS = {
    1: "ראשון", 2: "שני", 3: "שלישי",
    4: "רביעי", 5: "חמישי", 6: "שישי",
}
_SKIP = {"הפסקה", ""}

# Fixed school bell schedule (hour_num → (start, end))
_HOUR_TIMES = {
    1: ("8:00",  "8:40"),
    2: ("8:40",  "9:25"),
    3: ("10:05", "10:55"),
    4: ("10:55", "11:50"),
    5: ("12:00", "12:45"),
    6: ("12:45", "13:30"),
}

# Breaks inserted AFTER a given hour: (after_hour, start, end, label)
_BREAKS_AFTER = {
    2: [
        ("9:25",  "9:45",  "🍽️ הפסקת אוכל"),
        ("9:45",  "10:05", "🏃 הפסקה"),
    ],
    4: [
        ("11:50", "12:00", "🏃 הפסקה"),
    ],
}

_FRIDAY_IDX = 6


def _hour_times_for_day(day_idx: int) -> dict[int, tuple[str, str]]:
    """Return _HOUR_TIMES adjusted for the given day (Friday ends earlier)."""
    times = dict(_HOUR_TIMES)
    if day_idx == _FRIDAY_IDX:
        times[4] = (times[4][0], "11:40")
    return times


def _breaks_after_for_day(day_idx: int, hour_num: int) -> list[tuple[str, str, str]]:
    """Return breaks after hour_num, adjusted for the given day (no break on Friday after hour 4)."""
    if day_idx == _FRIDAY_IDX and hour_num == 4:
        return []
    return _BREAKS_AFTER.get(hour_num, [])


def _today_day_index() -> int:
    iso = date.today().isoweekday()  # Mon=1…Sun=7
    return iso % 7 + 1              # Sun→1, Mon→2…Fri→6


async def _today_schedule_text() -> str:
    try:
        data = await webtop.get_schedule(week_index=0)
        if not isinstance(data, dict) or not data.get("status"):
            return ""
        today_idx = _today_day_index()
        day_name  = ISRAELI_DAYS.get(today_idx, "")
        today_str = date.today().strftime("%d/%m/%Y")

        for day in data.get("data") or []:
            if day.get("dayIndex") != today_idx:
                continue

            # Build hour→(subject, teacher) map
            hour_lessons: dict[int, tuple[str, str]] = {}
            for slot in day.get("hoursData") or []:
                hour_num = slot.get("hour")
                if not isinstance(hour_num, int):
                    continue
                for lesson in slot.get("scheduale") or []:
                    subject = (lesson.get("subject") or "").strip()
                    if subject in _SKIP:
                        continue
                    first   = lesson.get("teacherPrivateName") or ""
                    last    = lesson.get("teacherLastName") or ""
                    teacher = f"{first} {last}".strip()
                    hour_lessons[hour_num] = (subject, teacher)
                    break

            # Apply manual overrides for this day
            if today_idx in _SCHEDULE_OVERRIDES:
                for hour_num, (subject, teacher) in _SCHEDULE_OVERRIDES[today_idx].items():
                    hour_lessons[hour_num] = (subject, teacher)

            if not hour_lessons:
                return ""

            lines = [f"🗓️ <b>היום {html.escape(today_str)} — יום {html.escape(day_name)}</b>\n"]

            hour_times = _hour_times_for_day(today_idx)
            last_hour = max(hour_lessons.keys())

            for hour_num in sorted(hour_lessons.keys()):
                subject, teacher = hour_lessons[hour_num]
                start, end = hour_times.get(hour_num, ("", ""))
                teacher_str = ""
                time_str = f"{start} – {end}" if start else ""
                lines.append(
                    f"<b>{time_str}</b> שיעור {hour_num} — {html.escape(subject)}{teacher_str}"
                )

                # Insert breaks after this hour
                for b_start, b_end, b_label in _breaks_after_for_day(today_idx, hour_num):
                    lines.append(f"<b>{b_end} – {b_start}</b> {b_label}")

            # End of day
            _, day_end = hour_times.get(last_hour, ("", ""))
            if day_end:
                lines.append(f"\n🔔 <b>סיום היום: {day_end}</b>")

            return "\n".join(lines)

    except Exception:
        pass
    return ""


async def _tomorrow_schedule_text() -> str:
    """Return formatted schedule for tomorrow (used in 19:00 evening message)."""
    try:
        tomorrow     = date.today() + timedelta(days=1)
        tomorrow_iso = tomorrow.isoweekday()          # Mon=1…Sun=7
        tomorrow_idx = tomorrow_iso % 7 + 1           # Sun=1…Fri=6, Sat=7

        # No school tomorrow
        if tomorrow_idx == 7:
            return "✡️ <b>מחר שבת — יום מנוחה 😊</b>"

        day_name     = ISRAELI_DAYS.get(tomorrow_idx, "")
        tomorrow_str = tomorrow.strftime("%d/%m/%Y")

        data = await webtop.get_schedule(week_index=0)
        if not isinstance(data, dict) or not data.get("status"):
            return ""

        for day in data.get("data") or []:
            if day.get("dayIndex") != tomorrow_idx:
                continue

            hour_lessons: dict[int, tuple[str, str]] = {}
            for slot in day.get("hoursData") or []:
                hour_num = slot.get("hour")
                if not isinstance(hour_num, int):
                    continue
                for lesson in slot.get("scheduale") or []:
                    subject = (lesson.get("subject") or "").strip()
                    if subject in _SKIP:
                        continue
                    first   = lesson.get("teacherPrivateName") or ""
                    last    = lesson.get("teacherLastName") or ""
                    hour_lessons[hour_num] = (f"{first} {last}".strip() and subject or subject, "")
                    break

            # Apply manual overrides
            if tomorrow_idx in _SCHEDULE_OVERRIDES:
                for hour_num, (subject, teacher) in _SCHEDULE_OVERRIDES[tomorrow_idx].items():
                    hour_lessons[hour_num] = (subject, teacher)

            if not hour_lessons:
                return ""

            lines = [f"🗓️ <b>מחר {html.escape(tomorrow_str)} — יום {html.escape(day_name)}</b>\n"]
            hour_times = _hour_times_for_day(tomorrow_idx)
            last_hour = max(hour_lessons.keys())

            for hour_num in sorted(hour_lessons.keys()):
                subject, _ = hour_lessons[hour_num]
                start, end = hour_times.get(hour_num, ("", ""))
                time_str = f"{start} – {end}" if start else ""
                lines.append(f"<b>{time_str}</b> שיעור {hour_num} — {html.escape(subject)}")
                for b_start, b_end, b_label in _breaks_after_for_day(tomorrow_idx, hour_num):
                    lines.append(f"<b>{b_end} – {b_start}</b> {b_label}")

            _, day_end = hour_times.get(last_hour, ("", ""))
            if day_end:
                lines.append(f"\n🔔 <b>סיום מחר: {day_end}</b>")

            return "\n".join(lines)

    except Exception:
        pass
    return ""


def build_start_screen(schedule_text: str = "", prefix: str = "") -> str:
    """Canonical start-screen text: greeting + optional schedule + menu prompt.

    The single source of this wording — bot.py (/0) and notifier.py (19:00)
    build the same screen through here rather than repeating the string.
    """
    name = webtop.student_name or "התלמיד"
    text = f"{prefix}\n\n" if prefix else ""
    text += f"👋 שלום! בוט בית הספר של <b>{html.escape(name)}</b>\n"
    if schedule_text:
        text += f"\n{schedule_text}\n"
    text += "\nבחר מה לראות:"
    return text


@restricted
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Saturday check (isoweekday=6 → Israeli day 7) — show tomorrow's (Sunday) schedule instead
    if date.today().isoweekday() == 6:
        today_text = await _tomorrow_schedule_text()
    else:
        today_text = await _today_schedule_text()

    text = build_start_screen(today_text)

    if update.message:
        sent = await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)
        main_screen_state.main_screen[update.effective_chat.id] = sent.message_id
    elif update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.message.photo:
            await query.message.delete()
            sent = await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=MAIN_MENU,
            )
            main_screen_state.main_screen[query.message.chat_id] = sent.message_id
        else:
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)
            main_screen_state.main_screen[query.message.chat_id] = query.message.message_id

