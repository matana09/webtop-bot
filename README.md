# Webtop Telegram Bot

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.7-26A5E4.svg)](https://python-telegram-bot.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)](#requirements)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/matana09/webtop-bot/pulls)

A Telegram bot that pulls a student's data from the Israeli **SmartSchool / Webtop**
school system and shows it in Telegram: schedule, homework, grades, discipline
events and school messages — plus a daily summary and a weekly schedule image.

Everything runs on your own machine. Your credentials stay in a local `.env`
file that is never committed.

## Features

- 🗓️ **Schedule** — daily and weekly views, rendered as an image
- 📚 **Homework** — browse day by day, moves between weeks automatically
- 📊 **Grades**, 📋 **discipline events**, 📬 **school messages**
- 🔔 **Notifications** — polls every 10 minutes for anything new
- 🕔 **Daily summary** at 17:00, **tomorrow's schedule** at 19:00

## Requirements

- Python 3.11 or newer
- A Telegram bot token
- A Webtop / SmartSchool parent or student account

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Create your config**

Copy `.env.example` to `.env` and fill it in:

```bash
cp .env.example .env
```

- `TELEGRAM_TOKEN` — message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, and copy the token it gives you.
- `WEBTOP_USERNAME` / `WEBTOP_PASSWORD` — the same login you use on the Webtop website.
- `WEBTOP_DATA` — leave empty first. If login fails, open the Webtop site in your browser, press F12 → Network tab → log in → find the login request → copy the `data` field from the request body.
- `ALLOWED_CHAT_IDS` — see step 3.

**3. Lock the bot to your own chat**

Start the bot (`python bot.py`), send it `/myid` in Telegram, and it replies with
your chat ID. Put that number in `ALLOWED_CHAT_IDS` in `.env` and restart.

> **This step is not optional.** Until you set it, the bot refuses every command
> except `/myid`. That is deliberate — without it, anyone who found your bot
> could read the student's data.

**4. Run it**

```bash
python bot.py
```

On Windows you can install it as a background task that starts at login:

```powershell
.\setup_autostart.ps1
```

## Commands

| Command | What it does |
|---|---|
| `/start` | Main menu with today's schedule |
| `/summary` | Today's summary right now |
| `/testschedule` | Tomorrow's schedule right now |
| `/myid` | Show your chat ID (for setup) |
| `/clear` | Delete the bot's messages from the chat |
| `/0` | Reconnect to Webtop |

## Security

- `.env`, `.device_id`, `logs/` and `notification_state.json` are gitignored. **Never commit them** — they contain your credentials and the student's real data.
- Access is **fail-closed**: an empty `ALLOWED_CHAT_IDS` denies everyone rather than allowing everyone.
- Every update passes a single authorization gate before any handler runs, with per-chat rate limiting.
- A random device id is generated on first run and stored in `.device_id`. It is local to your install.

If you fork or share your copy, double-check with `git status` that none of those
files are staged.

## Disclaimer

Not affiliated with or endorsed by SmartSchool. Use it with your own account, for
your own family's data, at your own risk.

## License

MIT — see [LICENSE](LICENSE).
