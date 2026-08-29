"""Stores the last known main-screen message ID per chat (in-memory)."""

# chat_id (int) → message_id (int)
main_screen: dict[int, int] = {}

# chat_id (int) → list of notification message_ids to delete at midnight
notification_msgs: dict[int, list[int]] = {}


def add_notification_msg(chat_id: int, message_id: int) -> None:
    notification_msgs.setdefault(chat_id, []).append(message_id)


def clear_notification_msgs(chat_id: int) -> None:
    notification_msgs.pop(chat_id, None)
