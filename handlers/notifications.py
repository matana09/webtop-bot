from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import BACK_MENU
from webtop_service import webtop
from formatters import format_notifications


@restricted
async def notifications_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ טוען התראות...")

    try:
        data = await webtop.get_notifications()
        text = format_notifications(data)
    except Exception as exc:
        text = f"שגיאה בטעינת התראות:\n<code>{exc}</code>"

    if len(text) > 4000:
        text = text[:4000] + "\n<i>...קוצר</i>"
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=BACK_MENU)
