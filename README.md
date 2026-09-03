# Webtop Telegram Bot

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-22.7-26A5E4.svg)](https://python-telegram-bot.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)](#requirements)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/matana09/webtop-bot/pulls)

A Telegram bot that pulls a student's data from **SmartSchool / Webtop**
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

> מדריך התקנה מפורט בעברית: [INSTALL.he.md](INSTALL.he.md)

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Create your settings file**

All your logins live in one file on your own computer, called `.env`. Nothing is
typed into Telegram, and nothing is sent anywhere except to the school's own
website when the bot logs in for you.

Make the file by copying the example:

```
copy .env.example .env
```

On macOS or Linux use `cp .env.example .env` instead.

**3. Put your details in that file**

Open `.env` in a text editor (Notepad is fine). You'll see a line for each
setting. Type your value straight after the `=` sign — no quotes, no spaces
around the `=`.

| Line in the file | What to type there | Where to get it |
|---|---|---|
| `TELEGRAM_TOKEN=` | Your bot's token | Message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, follow the prompts, copy the long code it gives you |
| `WEBTOP_USERNAME=` | **Your Webtop username** | Exactly what you type on the Webtop/SmartSchool website when you log in |
| `WEBTOP_PASSWORD=` | **Your Webtop password** | The same password you use on that website |
| `ALLOWED_CHAT_IDS=` | Leave empty for now | Filled in at step 5 |
| `WEBTOP_DATA=` | Leave empty | Only needed if login fails — see below |
| `WEBTOP_BASE_URL=` | Leave empty | Only for schools on a non-default server |

So a finished file looks something like this:

```
TELEGRAM_TOKEN=paste_the_token_from_BotFather_here
WEBTOP_USERNAME=your_webtop_username
WEBTOP_PASSWORD=your_webtop_password
WEBTOP_DATA=
WEBTOP_BASE_URL=
ALLOWED_CHAT_IDS=
```

Save and close the file.

> **Windows tip:** Notepad likes to save as `.env.txt`. In the Save dialog set
> *Save as type* to **All Files**, or the bot won't find your settings.

> **If login fails** with a message about credentials: your school may need an
> extra key. Open the Webtop site in your browser, press `F12` → **Network**
> tab → log in normally → click the `LoginByUserNameAndPassword` request →
> copy the `data` value from the request body into `WEBTOP_DATA=`.

**4. Start the bot for the first time**

```
python bot.py
```

Leave this window open. If your username and password are right, it prints
`Login OK` with the student's name.

**5. Lock the bot to your own chat**

With the bot running, open Telegram, find your bot, and send it `/myid`.
It replies with your chat ID — a number like `123456789`.

Put that number after `ALLOWED_CHAT_IDS=` in your `.env` file, save it, then
stop the bot (`Ctrl+C`) and start it again.

> **This step is not optional.** Until you set it, the bot refuses every command
> except `/myid`. That is deliberate — without it, anyone who found your bot
> could read the student's data.

**6. Run it for real**

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

- **The bot never asks for your password in Telegram.** It is read once from
  `.env` on your own machine. If anything claiming to be this bot asks you to
  type a password into a chat, it is not this bot.
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
