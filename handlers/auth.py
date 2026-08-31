"""Authorization for the bot.

Two layers, on purpose:

  * ``auth_gate`` — the primary choke point. Registered once in ``bot.py`` as a
    ``TypeHandler`` in group -1, it sees every update before any handler runs
    and raises ``ApplicationHandlerStop`` for anything unauthorized. A handler
    added later is protected automatically — there is no decorator to forget.
  * ``restricted`` — a second line of defense for handlers that are also called
    directly from Python rather than only dispatched by the Application.

Rate limiting lives only in the gate, so it is charged once per update. A
handler that calls another handler does not spend two slots.

Both layers are fail-closed: an empty or misconfigured ALLOWED_CHAT_IDS denies
everyone rather than allowing everyone.

The gate also logs each accepted update. It is the only place every update is
guaranteed to pass through, so one line here replaces a logging call in every
handler.
"""
import logging
import time
from collections import OrderedDict, defaultdict, deque
from functools import wraps

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from config import ALLOWED_CHAT_IDS

logger = logging.getLogger(__name__)

_DENY_TEXT = "אין לך הרשאה להשתמש בבוט זה."
_DENY_ALERT = "אין הרשאה"
_BUSY_TEXT = "⏳ יותר מדי בקשות. נסה שוב בעוד רגע."
_BUSY_ALERT = "יותר מדי בקשות, נסה שוב בעוד רגע"

# Commands that must work before ALLOWED_CHAT_IDS is configured, so a new
# install can discover its own chat id. These expose nothing about the student.
_OPEN_COMMANDS = {"/myid"}

# ── rate limiting ──────────────────────────────────────────────────────────────
_RATE_MAX = 20          # max updates...
_RATE_WINDOW = 30.0     # ...per this many seconds, per chat
_hits: dict[int, deque] = defaultdict(deque)

# Unauthorized chats are answered at most once per window, and only a bounded
# number of them is remembered, so an unknown sender cannot grow this map.
_DENY_NOTICE_WINDOW = 300.0
_MAX_TRACKED_DENIED = 1000
_denied_at: "OrderedDict[int, float]" = OrderedDict()


def _rate_limited(chat_id: int) -> bool:
    now = time.monotonic()
    q = _hits[chat_id]
    while q and now - q[0] > _RATE_WINDOW:
        q.popleft()
    if len(q) >= _RATE_MAX:
        return True
    q.append(now)
    return False


# ── helpers ────────────────────────────────────────────────────────────────────

def is_authorized(chat_id) -> bool:
    return bool(ALLOWED_CHAT_IDS) and chat_id in ALLOWED_CHAT_IDS


def _is_open_command(update: Update) -> bool:
    msg = update.effective_message
    text = (msg.text or "").strip() if msg else ""
    if not text.startswith("/"):
        return False
    return text.split()[0].split("@")[0] in _OPEN_COMMANDS


def describe_update(update) -> str:
    """Short label for the log: what the user pressed or which command they sent.

    Deliberately excludes free-text message bodies — the log is a trace of what
    the bot was asked to do, not a transcript of the chat.
    """
    if not isinstance(update, Update):
        return "non-update"
    if update.callback_query:
        return f"button {update.callback_query.data!r}"
    msg = update.effective_message
    text = (msg.text or "").strip() if msg else ""
    if text.startswith("/"):
        return f"command {text.split()[0].split('@')[0]}"
    return "message"


async def _respond(update: Update, text: str, alert: str) -> None:
    """Answer on whichever surface the update arrived from."""
    if update.callback_query:
        await update.callback_query.answer(alert, show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text(text)


def _should_notice_denial(chat_id) -> bool:
    """True at most once per window per chat.

    The gate sees every update type, so an unauthorized sender could otherwise
    make the bot emit one reply and one log line per message it receives. Both
    the answer and the warning are throttled to keep that from being an
    outbound-message amplifier and a log flood.
    """
    now = time.monotonic()
    last = _denied_at.get(chat_id)
    if last is not None and now - last < _DENY_NOTICE_WINDOW:
        return False
    _denied_at[chat_id] = now
    _denied_at.move_to_end(chat_id)
    while len(_denied_at) > _MAX_TRACKED_DENIED:
        _denied_at.popitem(last=False)   # bounded: strangers cannot grow this
    return True


async def _deny(update: Update, chat_id) -> None:
    if not _should_notice_denial(chat_id):
        return
    user = update.effective_user
    logger.warning(
        "Unauthorized access blocked: chat_id=%s user_id=%s username=%s",
        chat_id,
        getattr(user, "id", None),
        getattr(user, "username", None),
    )
    await _respond(update, _DENY_TEXT, _DENY_ALERT)


# ── the gate (primary enforcement) ─────────────────────────────────────────────

async def auth_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run before every handler. Raising ApplicationHandlerStop drops the update."""
    chat = update.effective_chat
    chat_id = chat.id if chat else None

    if _is_open_command(update):
        logger.info("Handling %s from chat_id=%s", describe_update(update), chat_id)
        return

    if not is_authorized(chat_id):
        await _deny(update, chat_id)
        raise ApplicationHandlerStop

    if _rate_limited(chat_id):
        logger.warning("Rate limit hit for chat_id=%s", chat_id)
        await _respond(update, _BUSY_TEXT, _BUSY_ALERT)
        raise ApplicationHandlerStop

    # The gate is the one place every accepted update passes through, so the
    # trace lives here rather than in eleven separate handlers.
    logger.info("Handling %s from chat_id=%s", describe_update(update), chat_id)


# ── the decorator (second line of defense) ─────────────────────────────────────

def restricted(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat = update.effective_chat
        chat_id = chat.id if chat else None
        if not is_authorized(chat_id):
            await _deny(update, chat_id)
            return
        return await func(update, context)

    return wrapper
