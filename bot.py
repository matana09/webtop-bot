import logging
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    TypeHandler,
)

from config import TELEGRAM_TOKEN
from webtop_service import webtop
from handlers.start import start_handler, build_start_screen
from handlers.menu import MAIN_MENU
from notifier import check_notifications, send_daily_summary, _build_daily_summary, send_evening_schedule, _build_evening_start_screen
from handlers.schedule import schedule_handler
from handlers.homework import homework_handler
from handlers.notifications import notifications_handler
from handlers.messages import messages_handler
from handlers.discipline import discipline_handler
from handlers.grades import grades_handler
from handlers.all_info import all_info_handler
from handlers.debug import debug_handler
from handlers.auth import auth_gate, describe_update, is_authorized, restricted

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# httpx logs full request URLs, which include the Telegram bot token in clear text.
# Silence its INFO logs so the token never lands in log files.
logging.getLogger("httpx").setLevel(logging.WARNING)

_ERROR_TEXT = "⚠️ משהו השתבש. נסה שוב בעוד רגע."
_ERROR_ALERT = "משהו השתבש, נסה שוב"


async def post_init(app: Application):
    try:
        await webtop._ensure_client()
        logger.info("Webtop session ready. Student: %s", webtop.student_name)
    except Exception as exc:
        logger.error("Failed to init Webtop session: %s", exc)


async def post_shutdown(app: Application):
    await webtop.close()


async def error_handler(update, context):
    """Log any exception a handler raised, and tell the user something broke.

    Without this, a failing button leaves the user staring at a spinner that
    never resolves and no indication of what went wrong.
    """
    logger.error(
        "Handler failed on %s", describe_update(update), exc_info=context.error
    )

    if not isinstance(update, Update):
        return

    # Only ever answer a chat that is allowed to talk to the bot. auth_gate's
    # own reply can raise (a transient RetryAfter, say), and that exception
    # lands here — without this check the failure would be answered a second
    # time, to an unknown sender, bypassing the _DENY_NOTICE_WINDOW throttle
    # that exists so the bot cannot be used as an outbound-message amplifier.
    chat = update.effective_chat
    if not is_authorized(chat.id if chat else None):
        return

    # The notice is best-effort: the send can fail for the same reason the
    # handler did, and a raise here would be swallowed anyway.
    try:
        if update.callback_query:
            await update.callback_query.answer(_ERROR_ALERT, show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(_ERROR_TEXT)
    except Exception:
        logger.warning("Could not deliver the error notice to the user")


def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    @restricted
    async def stop_handler(update, context):
        await update.message.reply_text("🔄 מאפס חיבור, מתחבר מחדש...")
        try:
            await webtop.reset()
            await webtop._ensure_client()
        except Exception as exc:
            logger.error("Reset failed: %s", exc)
            await update.message.reply_text("⚠️ ההתחברות מחדש נכשלה. נסה שוב בעוד רגע.")
            return
        text = build_start_screen(prefix="✅ מחובר מחדש!")
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

    async def myid_handler(update, context):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        await update.message.reply_text(
            f"Chat ID שלך: <code>{chat_id}</code>\nUser ID שלך: <code>{user_id}</code>\n\nהעתק את המספר הזה ל-ALLOWED_CHAT_IDS ב-.env",
            parse_mode="HTML",
        )

    @restricted
    async def clear_handler(update, context):
        """Delete all reachable bot messages then show a fresh start screen."""
        chat_id = update.effective_chat.id
        msg_id  = update.message.message_id

        # Telegram lets bots delete only their own messages.
        # We scan every message ID from current down to 1 in batches of 100.
        # delete_messages silently ignores IDs that don't exist or can't be deleted.
        status_msg = await update.message.reply_text("🗑️ מנקה היסטוריה...")

        bottom = max(1, msg_id - 10000)  # cover up to 10,000 past message IDs
        all_ids = list(range(msg_id, bottom - 1, -1))

        for i in range(0, len(all_ids), 100):
            batch = all_ids[i : i + 100]
            try:
                await context.bot.delete_messages(chat_id=chat_id, message_ids=batch)
            except Exception:
                # Fallback: delete one by one
                for mid in batch:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                    except Exception:
                        pass

        # Send fresh start screen
        await start_handler(update, context)

    @restricted
    async def summary_handler(update, context):
        msg = await update.message.reply_text("⏳ מכין סיכום יום...")
        text = await _build_daily_summary()
        await msg.edit_text(text, parse_mode="HTML")

    @restricted
    async def testschedule_handler(update, context):
        msg = await update.message.reply_text("⏳ טוען...")
        text = await _build_evening_start_screen()
        await msg.edit_text(text, parse_mode="HTML", reply_markup=MAIN_MENU)

    # Single choke point: every update passes auth + rate limiting here first,
    # so a handler added later is protected without needing a decorator.
    app.add_handler(TypeHandler(Update, auth_gate), group=-1)

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("1", start_handler))
    app.add_handler(CommandHandler("0", stop_handler))
    app.add_handler(CommandHandler("myid", myid_handler))
    app.add_handler(CommandHandler("debug", debug_handler))
    app.add_handler(CommandHandler("clear", clear_handler))
    app.add_handler(CommandHandler("summary", summary_handler))
    app.add_handler(CommandHandler("testschedule", testschedule_handler))

    app.add_handler(CallbackQueryHandler(schedule_handler, pattern=r"^schedule:"))
    app.add_handler(CallbackQueryHandler(homework_handler, pattern=r"^homework:"))
    app.add_handler(CallbackQueryHandler(notifications_handler, pattern="^notifications$"))
    app.add_handler(CallbackQueryHandler(messages_handler, pattern=r"^messages"))
    app.add_handler(CallbackQueryHandler(discipline_handler, pattern="^discipline$"))
    app.add_handler(CallbackQueryHandler(grades_handler, pattern="^grades$"))
    app.add_handler(CallbackQueryHandler(all_info_handler, pattern="^all$"))
    app.add_handler(CallbackQueryHandler(start_handler, pattern="^back$"))

    app.add_error_handler(error_handler)

    # Poll for new homework / discipline every 10 minutes
    app.job_queue.run_repeating(check_notifications, interval=600, first=60)

    import datetime
    _IL = datetime.timezone(datetime.timedelta(hours=3))  # Israel UTC+3

    # Daily end-of-school summary at 17:00 (Sun-Fri)
    app.job_queue.run_daily(
        send_daily_summary,
        time=datetime.time(hour=17, minute=0, tzinfo=_IL),
    )

    # Evening schedule at 19:00 — sent after the 17:00 daily summary
    app.job_queue.run_daily(
        send_evening_schedule,
        time=datetime.time(hour=19, minute=0, tzinfo=_IL),
    )


    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
