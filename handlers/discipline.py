from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import BACK_MENU
from webtop_service import webtop
from formatters import format_discipline


@restricted
async def discipline_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ טוען נתונים...")

    try:
        data = await webtop.get_discipline_events()
        text = format_discipline(data)
    except Exception as exc:
        text = f"שגיאה:\n<code>{exc}</code>"

    if len(text) > 4000:
        text = text[:4000] + "\n<i>...קוצר</i>"

    await query.edit_message_text(text, parse_mode="HTML", reply_markup=BACK_MENU)
