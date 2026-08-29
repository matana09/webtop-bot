from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import BACK_MENU
from webtop_service import webtop
from formatters import format_grades


@restricted
async def grades_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ טוען ציונים...")

    try:
        data = await webtop.get_grades()
        text = format_grades(data)
    except Exception as exc:
        text = f"שגיאה בטעינת ציונים:\n<code>{exc}</code>"

    if len(text) > 4000:
        text = text[:4000] + "\n<i>...קוצר</i>"
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=BACK_MENU)
