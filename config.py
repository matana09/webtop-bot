import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
WEBTOP_USERNAME = os.getenv("WEBTOP_USERNAME", "")
WEBTOP_PASSWORD = os.getenv("WEBTOP_PASSWORD", "")
WEBTOP_DATA = os.getenv("WEBTOP_DATA", "")
WEBTOP_BASE_URL = os.getenv("WEBTOP_BASE_URL", "")

_raw_ids = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: list[int] = [int(x) for x in _raw_ids.split(",") if x.strip().isdigit()]

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN is not set in .env")
if not WEBTOP_USERNAME or not WEBTOP_PASSWORD:
    raise ValueError("WEBTOP_USERNAME and WEBTOP_PASSWORD must be set in .env")
