"""Shared menu keyboard."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

MAIN_MENU = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("📬 הודעות", callback_data="messages:0"),
        InlineKeyboardButton("📋 משמעת", callback_data="discipline"),
    ],
    [
        InlineKeyboardButton("🗓️ מערכת שעות", callback_data="schedule:0"),
        InlineKeyboardButton("📊 ציונים", callback_data="grades"),
    ],
    [
        InlineKeyboardButton("📚 שיעורי בית", callback_data="homework:0:0"),
    ],
])

SCHEDULE_NAV = lambda week: InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back")],
])

def HOMEWORK_NAV(week: int, day: int) -> InlineKeyboardMarkup:
    # Previous day: if Sunday (1) → go to previous week Friday (6)
    if day <= 1:
        prev_cb = f"homework:{week - 1}:6"
    else:
        prev_cb = f"homework:{week}:{day - 1}"
    # Next day: if Friday (6) → go to next week Sunday (1)
    if day >= 6:
        next_cb = f"homework:{week + 1}:1"
    else:
        next_cb = f"homework:{week}:{day + 1}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("יום הבא ◀️", callback_data=next_cb),
            InlineKeyboardButton("▶️ יום קודם", callback_data=prev_cb),
        ],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back")],
    ])

BACK_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back")],
])

MESSAGES_NAV = lambda month: InlineKeyboardMarkup([
    [
        InlineKeyboardButton("חודש הבא ◀️", callback_data=f"messages:{month + 1}"),
        InlineKeyboardButton("▶️ חודש קודם", callback_data=f"messages:{month - 1}"),
    ],
    [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back")],
])
