@echo off
schtasks /end /tn WebtopBot >nul 2>&1
timeout /t 2 /nobreak >nul
schtasks /run /tn WebtopBot >nul 2>&1
echo WebtopBot restarted successfully!
timeout /t 2 /nobreak >nul
