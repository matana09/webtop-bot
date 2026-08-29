@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
python bot.py >> logs\bot.log 2>&1
