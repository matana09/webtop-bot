"""
/debug command — dumps raw dashboard + session data.
Useful for finding correct field names for encrypted_student_id, class_code, etc.
"""
import html
import json
from telegram import Update
from telegram.ext import ContextTypes
from handlers.auth import restricted
from webtop_service import webtop


@restricted
async def debug_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ מביא נתונים גולמיים...")

    try:
        dashboard = await webtop.get_raw_dashboard()
        raw = json.dumps(dashboard, ensure_ascii=False, indent=2)
        session_info = (
            f"encrypted_student_id = <code>{html.escape(str(webtop.encrypted_student_id))}</code>\n"
            f"class_code = <code>{html.escape(str(webtop.class_code))}</code>\n"
            f"class_number = <code>{html.escape(str(webtop.class_number))}</code>\n"
            f"student_name = <code>{html.escape(str(webtop.student_name))}</code>"
        )

        await update.message.reply_text(
            f"<b>Session fields (auto-detected):</b>\n{session_info}",
            parse_mode="HTML",
        )

        # Send raw dashboard in chunks
        for i in range(0, len(raw), 4000):
            chunk = raw[i : i + 4000]
            await update.message.reply_text(f"<pre>{html.escape(chunk)}</pre>", parse_mode="HTML")

    except Exception as exc:
        await update.message.reply_text(f"שגיאה:\n<code>{html.escape(str(exc))}</code>", parse_mode="HTML")
