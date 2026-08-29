from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import MESSAGES_NAV
from webtop_service import webtop
from formatters import format_messages


@restricted
async def messages_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        month_offset = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        month_offset = 0

    await query.edit_message_text("⏳ טוען הודעות...")

    try:
        data = await webtop.get_messages()
        text = format_messages(data, month_offset=month_offset)
    except Exception as exc:
        text = f"שגיאה בטעינת הודעות:\n<code>{exc}</code>"

    if len(text) > 4000:
        text = text[:4000] + "\n<i>...קוצר</i>"
    await query.edit_message_text(
        text, parse_mode="HTML", reply_markup=MESSAGES_NAV(month_offset)
    )
