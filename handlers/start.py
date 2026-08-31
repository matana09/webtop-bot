import html
from datetime import date, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import MAIN_MENU
from webtop_service import webtop
import schedule_overrides as _sched_overrides
import schedule_times as _sched_times
import main_screen_state

ISRAELI_DAYS = {
    1: "ראשון", 2: "שני", 3: "שלישי",
    4: "רביעי", 5: "חמישי", 6: "שישי",
}
_SKIP = {"הפסקה", ""}


def _today_day_index() -> int:
    iso = date.today().isoweekday()  # Mon=1…Sun=7
    return iso % 7 + 1              # Sun→1, Mon→2…Fri→6


async def _lessons_for_day(day_idx: int) -> dict[int, tuple[str, str, str]]:
    """hour_num → (subject, teacher, topic) for one school day.

    API data first; the printed timetable in schedule_overrides then wins for
    any day it covers. Webtop blocks the schedule view between school years, so
    the manual sheet has to stand on its own when the API returns nothing.
    """
    hour_lessons: dict[int, tuple[str, str, str]] = {}
    try:
        data = await webtop.get_schedule(week_index=0)
        if isinstance(data, dict) and data.get("status"):
            for day in data.get("data") or []:
                if day.get("dayIndex") != day_idx:
                    continue
                for slot in day.get("hoursData") or []:
                    hour_num = slot.get("hour")
                    if not isinstance(hour_num, int):
                        continue
                    for lesson in slot.get("scheduale") or []:
                        subject = (lesson.get("subject") or "").strip()
                        if subject in _SKIP:
                            continue
                        first = lesson.get("teacherPrivateName") or ""
                        last  = lesson.get("teacherLastName") or ""
                        hour_lessons[hour_num] = (subject, f"{first} {last}".strip(), "")
                        break
    except Exception:
        pass  # the manual sheet below still stands

    manual = _sched_overrides.for_day(day_idx)
    if manual is not None:
        hour_lessons = manual
    return hour_lessons


def _format_day(day_idx: int, hour_lessons: dict[int, tuple[str, str, str]],
                title: str, end_label: str) -> str:
    """Render one day: a line per lesson, breaks between, end-of-day footer."""
    if not hour_lessons:
        return ""

    lines = [f"{title}\n"]
    hour_times = _sched_times.hour_times_for_day(day_idx)
    last_hour  = max(hour_lessons)

    for hour_num in sorted(hour_lessons):
        subject, _, topic = hour_lessons[hour_num]
        start, end = hour_times.get(hour_num, ("", ""))
        time_str = f"{start} – {end}" if start else ""
        subject_str = html.escape(subject)
        if topic:
            subject_str += f" ({html.escape(topic)})"
        lines.append(f"<b>{time_str}</b> שיעור {hour_num} — {subject_str}")
        if hour_num == last_hour:
            continue
        for b_start, b_end, b_label in _sched_times.breaks_after_for_day(day_idx, hour_num):
            lines.append(f"<b>{b_end} – {b_start}</b> {b_label}")

    _, day_end = hour_times.get(last_hour, ("", ""))
    if day_end:
        lines.append(f"\n🔔 <b>{end_label}: {day_end}</b>")

    return "\n".join(lines)


async def _today_schedule_text() -> str:
    today_idx = _today_day_index()
    if today_idx == 7:
        return ""
    today = date.today()
    title = (f"🗓️ <b>היום {html.escape(today.strftime('%d/%m/%Y'))} — "
             f"יום {html.escape(ISRAELI_DAYS.get(today_idx, ''))}</b>")
    return _format_day(today_idx, await _lessons_for_day(today_idx), title, "סיום היום")


async def _tomorrow_schedule_text() -> str:
    """Formatted schedule for tomorrow (used in the 19:00 evening message)."""
    tomorrow     = date.today() + timedelta(days=1)
    tomorrow_idx = tomorrow.isoweekday() % 7 + 1   # Sun=1…Fri=6, Sat=7

    if tomorrow_idx == 7:
        return "✡️ <b>מחר שבת — יום מנוחה 😊</b>"

    title = (f"🗓️ <b>מחר {html.escape(tomorrow.strftime('%d/%m/%Y'))} — "
             f"יום {html.escape(ISRAELI_DAYS.get(tomorrow_idx, ''))}</b>")
    return _format_day(tomorrow_idx, await _lessons_for_day(tomorrow_idx), title, "סיום מחר")


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

