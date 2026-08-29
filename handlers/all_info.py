import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import BACK_MENU
from webtop_service import webtop
from formatters import format_schedule, format_homework, format_notifications, format_messages


@restricted
async def all_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ טוען את כל המידע...")

    try:
        schedule_data, homework_data, notif_data, msg_data = await asyncio.gather(
            webtop.get_schedule(),
            webtop.get_homework(),
            webtop.get_notifications(),
            webtop.get_messages(),
            return_exceptions=True,
        )

        sections = []
        for data, formatter, label in [
            (schedule_data, lambda d: format_schedule(d), "לוח שעות"),
            (homework_data, format_homework, "שיעורי בית"),
            (notif_data, format_notifications, "התראות"),
            (msg_data, format_messages, "הודעות"),
        ]:
            if isinstance(data, Exception):
                sections.append(f"❌ <b>{label}</b>: <code>{data}</code>")
            else:
                sections.append(formatter(data))

        text = "\n\n─────────────────\n\n".join(sections)
        # Telegram message limit is 4096 chars
        if len(text) > 4000:
            text = text[:4000] + "\n\n<i>...המשך קוצר</i>"

    except Exception as exc:
        text = f"שגיאה כללית:\n<code>{exc}</code>"

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=BACK_MENU)
