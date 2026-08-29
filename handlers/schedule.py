import io
from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from handlers.auth import restricted
from handlers.menu import SCHEDULE_NAV, BACK_MENU
from webtop_service import webtop
from formatters import format_schedule_classic

try:
    from schedule_image import generate_schedule_image
    _IMAGE_SUPPORT = True
except ImportError:
    _IMAGE_SUPPORT = False


@restricted
async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        week_index = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        week_index = 0

    week_label = "השבוע" if week_index == 0 else f"שבוע {week_index:+d}"
    chat_id = query.message.chat_id
    is_photo = bool(query.message.photo)

    # Show loading without sending a new message
    if is_photo:
        try:
            await query.message.edit_caption(f"⏳ טוען מערכת שעות - {week_label}...")
        except Exception:
            pass
    else:
        try:
            await query.edit_message_text(f"⏳ טוען מערכת שעות - {week_label}...")
        except Exception:
            pass

    try:
        data = await webtop.get_schedule(week_index=week_index)

        if _IMAGE_SUPPORT and isinstance(data, dict) and data.get("status"):
            img_bytes = generate_schedule_image(data, week_label=week_label)
            if is_photo:
                # Replace existing photo in-place — no delete, no duplicate
                await context.bot.edit_message_media(
                    chat_id=chat_id,
                    message_id=query.message.message_id,
                    media=InputMediaPhoto(media=io.BytesIO(img_bytes)),
                    reply_markup=SCHEDULE_NAV(week_index),
                )
            else:
                # First time: text → delete it, send photo
                try:
                    await query.message.delete()
                except Exception:
                    pass
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=io.BytesIO(img_bytes),
                    reply_markup=SCHEDULE_NAV(week_index),
                )
        else:
            text = format_schedule_classic(data, week_index=week_index)
            if len(text) > 4000:
                text = text[:4000] + "\n<i>...קוצר</i>"
            if is_photo:
                try:
                    await query.message.edit_caption(text, parse_mode="HTML", reply_markup=SCHEDULE_NAV(week_index))
                except Exception:
                    await query.message.edit_text(text, parse_mode="HTML", reply_markup=SCHEDULE_NAV(week_index))
            else:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=SCHEDULE_NAV(week_index))

    except Exception as exc:
        err = f"שגיאה בטעינת מערכת שעות:\n<code>{exc}</code>"
        try:
            if is_photo:
                await query.message.edit_caption(err, parse_mode="HTML", reply_markup=BACK_MENU)
            else:
                await query.message.edit_text(err, parse_mode="HTML", reply_markup=BACK_MENU)
        except Exception:
            await context.bot.send_message(chat_id, err, parse_mode="HTML", reply_markup=BACK_MENU)
