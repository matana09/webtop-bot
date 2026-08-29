from datetime import date as _date
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import HOMEWORK_NAV
from webtop_service import webtop
from formatters import format_homework_day


def _today_day_index() -> int:
    """Return Israeli day index: Sun=1, Mon=2 ... Fri=6."""
    iso = _date.today().isoweekday()  # Mon=1 ... Sun=7
    day = iso % 7 + 1                # Sun→1, Mon→2 ... Fri→6
    return max(1, min(6, day))


@restricted
async def homework_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    try:
        week_index = int(parts[1])
    except (IndexError, ValueError):
        week_index = 0

    try:
        day_index = int(parts[2])
        if day_index == 0:  # 0 = today
            day_index = _today_day_index()
    except (IndexError, ValueError):
        day_index = _today_day_index()

    day_index = max(1, min(6, day_index))

    await query.edit_message_text("⏳ טוען שיעורי בית...")

    try:
        data = await webtop.get_homework(week_index=week_index)
        text = format_homework_day(data, day_index)
    except Exception as exc:
        text = f"שגיאה בטעינת שיעורי בית:\n<code>{exc}</code>"

    if len(text) > 4000:
        text = text[:4000] + "\n<i>...קוצר</i>"
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=HOMEWORK_NAV(week_index, day_index))
