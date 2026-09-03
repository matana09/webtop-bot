"""Background polling — sends Telegram alerts for new homework / discipline events."""
import asyncio
import html
import json
import logging
import os
from datetime import date as _date, timedelta

from telegram.ext import ContextTypes

from config import ALLOWED_CHAT_IDS
from webtop_service import webtop
import vacations
import main_screen_state

logger = logging.getLogger(__name__)
_STATE_FILE = "notification_state.json"


# ── state persistence ─────────────────────────────────────────────────────────

def _load() -> dict:
    if os.path.exists(_STATE_FILE):
        try:
            with open(_STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"initialized": False, "discipline": [], "homework": [], "messages": []}


def _save(state: dict):
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.error("Failed to save notification state: %s", exc)


# ── key helpers ───────────────────────────────────────────────────────────────

def _disc_key(ev: dict) -> str:
    return "|".join([
        (ev.get("eventDate") or "")[:10],
        ev.get("eventType") or "",
        ev.get("subjectName") or "",
        ev.get("teacherName") or "",
    ])


def _hw_key(lesson: dict, date_str: str) -> str:
    return "|".join([
        date_str,
        lesson.get("subject_name") or "",
        (lesson.get("homeWork") or "")[:80],
    ])


def _msg_key(msg: dict) -> str:
    return "|".join([
        msg.get("sendingDate") or msg.get("msgTime") or msg.get("date") or "",
        msg.get("subject") or msg.get("title") or "",
        msg.get("student_F_name") or msg.get("senderName") or "",
    ])


# ── formatters ────────────────────────────────────────────────────────────────

def _fmt_discipline(ev: dict) -> str:
    event_type = html.escape(ev.get("eventType") or "")
    subject    = html.escape(ev.get("subjectName") or "")
    teacher    = html.escape(ev.get("teacherName") or "")
    remark     = html.escape((ev.get("remark") or "")[:150])
    raw_date   = (ev.get("eventDate") or "")[:10]
    try:
        from datetime import date as _date
        d = _date.fromisoformat(raw_date)
        date_fmt = d.strftime("%d/%m/%Y")
    except Exception:
        date_fmt = raw_date

    lines = [f"📋 <b>אירוע משמעת חדש!</b> ({date_fmt})"]
    lines.append(f"<b>{event_type}</b>" + (f" — {subject}" if subject else ""))
    if teacher:
        lines.append(f"מורה: {teacher}")
    if remark:
        lines.append(f"<i>{remark}</i>")
    return "\n".join(lines)


def _fmt_message(msg: dict) -> str:
    f_name  = msg.get("student_F_name") or ""
    l_name  = msg.get("student_L_name") or ""
    sender  = html.escape(f"{f_name} {l_name}".strip() or msg.get("senderName") or "לא ידוע")
    subject = html.escape(msg.get("subject") or msg.get("title") or "ללא נושא")
    date_str = html.escape((msg.get("sendingDate") or msg.get("date") or "")[:16])
    lines = [f"📬 <b>הודעה חדשה!</b>"]
    lines.append(f"<b>{subject}</b>")
    lines.append(f"מאת: {sender}")
    if date_str:
        lines.append(f"<i>{date_str}</i>")
    return "\n".join(lines)


def _fmt_homework(lesson: dict, date_str: str) -> str:
    subject = html.escape(lesson.get("subject_name") or "")
    hw      = html.escape((lesson.get("homeWork") or "")[:250])
    lines = [f"📚 <b>שיעורי בית חדשים!</b>"]
    if date_str:
        lines[0] += f" ({date_str})"
    lines.append(f"<b>{subject}</b>")
    lines.append(f"✏️ {hw}")
    return "\n".join(lines)


# ── main polling job ──────────────────────────────────────────────────────────

async def check_notifications(context: ContextTypes.DEFAULT_TYPE):
    state = _load()
    seen_disc = set(state.get("discipline", []))
    seen_hw   = set(state.get("homework", []))
    seen_msgs = set(state.get("messages", []))
    first_run = not state.get("initialized", False)

    alerts: list[str] = []

    # ── discipline ────────────────────────────────────────────────────────────
    try:
        disc_data = await webtop.get_discipline_events()
        if isinstance(disc_data, dict) and disc_data.get("status"):
            events = (disc_data.get("data") or {}).get("diciplineEvents") or []
            for ev in events:
                key = _disc_key(ev)
                if key not in seen_disc:
                    seen_disc.add(key)
                    if not first_run:
                        alerts.append(_fmt_discipline(ev))
    except Exception as exc:
        logger.warning("Discipline poll failed: %s", exc)

    await asyncio.sleep(2)  # pause between SmartSchool API calls

    # ── homework ──────────────────────────────────────────────────────────────
    try:
        hw_data = await webtop.get_homework(week_index=0)
        if isinstance(hw_data, dict) and hw_data.get("status"):
            for day in hw_data.get("data") or []:
                date_str = (day.get("date") or "")[:10]
                for slot in day.get("hoursData") or []:
                    for lesson in slot.get("scheduale") or []:
                        if not lesson.get("homeWork"):
                            continue
                        key = _hw_key(lesson, date_str)
                        if key not in seen_hw:
                            seen_hw.add(key)
                            if not first_run:
                                alerts.append(_fmt_homework(lesson, date_str))
    except Exception as exc:
        logger.warning("Homework poll failed: %s", exc)

    await asyncio.sleep(2)  # pause between SmartSchool API calls

    # ── messages ──────────────────────────────────────────────────────────────
    try:
        msg_data = await webtop.get_messages()
        all_messages = []
        if isinstance(msg_data, dict) and "data" in msg_data:
            d = msg_data["data"]
            if isinstance(d, list):
                all_messages = d
        elif isinstance(msg_data, list):
            all_messages = msg_data

        for msg in all_messages:
            if not isinstance(msg, dict):
                continue
            key = _msg_key(msg)
            if key not in seen_msgs:
                seen_msgs.add(key)
                if not first_run:
                    alerts.append(_fmt_message(msg))
    except Exception as exc:
        logger.warning("Messages poll failed: %s", exc)

    # ── save & send ───────────────────────────────────────────────────────────
    state["initialized"] = True
    state["discipline"]  = list(seen_disc)
    state["homework"]    = list(seen_hw)
    state["messages"]    = list(seen_msgs)
    _save(state)

    if first_run:
        logger.info("Notifier initialized — %d discipline, %d homework items tracked",
                    len(seen_disc), len(seen_hw))
        return

    for msg in alerts:
        for chat_id in ALLOWED_CHAT_IDS:
            try:
                sent = await context.bot.send_message(
                    chat_id=chat_id, text=msg, parse_mode="HTML"
                )
                main_screen_state.add_notification_msg(chat_id, sent.message_id)
                await asyncio.sleep(0.4)  # Telegram rate limit: max 30 msg/sec
            except Exception as exc:
                logger.error("Send alert failed (chat %s): %s", chat_id, exc)

    if alerts:
        logger.info("Sent %d alerts", len(alerts))


# ── daily end-of-day summary ──────────────────────────────────────────────────

async def _build_daily_summary() -> str:
    """Build today's summary text: lessons + topics + homework + מילות טוב."""
    today = _date.today()
    today_str = today.isoformat()
    _DAYS = {1: "ראשון", 2: "שני", 3: "שלישי", 4: "רביעי", 5: "חמישי", 6: "שישי", 7: "שבת"}
    day_name = _DAYS.get(today.isoweekday() % 7 + 1, "")
    lines = [f"📋 <b>סיכום יום {day_name} {today.strftime('%d/%m/%Y')}</b>\n"]

    # ── lessons + topics + homework ───────────────────────────────────────────
    try:
        hw_data = await webtop.get_homework(week_index=0)
        entries = []
        if isinstance(hw_data, dict) and hw_data.get("status"):
            for day in hw_data.get("data") or []:
                if (day.get("date") or "")[:10] != today_str:
                    continue
                for slot in day.get("hoursData") or []:
                    for lesson in slot.get("scheduale") or []:
                        subject = html.escape(lesson.get("subject_name") or "")
                        topic   = html.escape((lesson.get("descClass") or "").strip())
                        hw      = html.escape((lesson.get("homeWork") or "").strip())
                        if not subject:
                            continue
                        if not topic and not hw:
                            continue
                        block = [f"📘 <b>{subject}</b>"]
                        if topic:
                            block.append(f"   📖 נושא: {topic[:200]}")
                        if hw:
                            block.append(f"   ✏️ שיעורי בית: {hw[:200]}")
                        entries.append("\n".join(block))

        if entries:
            lines.append("\n".join(entries))
        else:
            lines.append("📚 אין שיעורי בית או נושאי שיעור להיום 🎉")
    except Exception as exc:
        logger.warning("Daily summary homework failed: %s", exc)
        lines.append("📚 שגיאה בטעינת שיעורי בית")

    # ── מילות טוב ────────────────────────────────────────────────────────────
    try:
        disc_data = await webtop.get_discipline_events()
        good_words = []
        if isinstance(disc_data, dict) and disc_data.get("status"):
            events = (disc_data.get("data") or {}).get("diciplineEvents") or []
            for ev in events:
                if (ev.get("eventDate") or "")[:10] != today_str:
                    continue
                event_type = ev.get("eventType") or ""
                if "טוב" in event_type or "מילה" in event_type or "חיובי" in event_type:
                    subject = html.escape(ev.get("subjectName") or "")
                    remark  = html.escape((ev.get("remark") or "").strip())
                    entry   = f"  🌟 <b>{html.escape(event_type)}</b>"
                    if subject:
                        entry += f" — {subject}"
                    if remark:
                        entry += f"\n     <i>{remark[:150]}</i>"
                    good_words.append(entry)
        if good_words:
            lines.append("\n⭐ <b>מילות טוב היום:</b>")
            lines.extend(good_words)
    except Exception as exc:
        logger.warning("Daily summary discipline failed: %s", exc)

    return "\n".join(lines)


async def send_daily_summary(context: ContextTypes.DEFAULT_TYPE):
    """Send today's summary at 17:00, on teaching days only.

    Summarising a day with no lessons produced a message whose whole content
    was "no homework today" — so Shabbat and every vacation day are skipped.
    """
    if not vacations.is_school_day(_date.today()):
        return
    text = await _build_daily_summary()
    for chat_id in ALLOWED_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.error("Daily summary send failed (chat %s): %s", chat_id, exc)


# ── evening schedule (19:00) ──────────────────────────────────────────────────

async def _build_evening_start_screen() -> str:
    """Build start-screen with TOMORROW's schedule for the 19:00 message."""
    from handlers.start import _tomorrow_schedule_text, build_start_screen

    return build_start_screen(await _tomorrow_schedule_text())


async def send_evening_schedule(context: ContextTypes.DEFAULT_TYPE):
    """At 19:00 send full start screen — appears after the 17:00 daily summary."""
    from handlers.menu import MAIN_MENU
    today    = _date.today()
    tomorrow = today + timedelta(days=1)

    if not vacations.is_school_day(tomorrow):
        # Announce a vacation once, on the last teaching day before it, so a
        # two-week break does not send the same notice fourteen times. The
        # ordinary weekly rest day is never announced — that was already the
        # rule for Friday evenings and it needs no reminder.
        starts_tomorrow = vacations.vacation_for(tomorrow) and vacations.is_school_day(today)
        if not starts_tomorrow:
            return
    text = await _build_evening_start_screen()
    for chat_id in ALLOWED_CHAT_IDS:
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode="HTML", reply_markup=MAIN_MENU,
            )
        except Exception as exc:
            logger.error("Evening schedule send failed (chat %s): %s", chat_id, exc)

