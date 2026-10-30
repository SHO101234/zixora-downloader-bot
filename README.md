# zixora downloader bot — host version

Personal-use Telegram downloader bot (the old Gemini bot's logic, rebuilt for hosting).
Runs on any Python host with polling. No token is stored in this repo.

## How it works
- `bot.py` — telebot polling bot: YouTube/TikTok links → Video / MP3 / Thumbnail / Subtitle buttons.
- Admin (chat id 1702338053) bypasses the hours gate and cooldown; other users are gated Mon–Sat 09:30–17:30, 3-minute cooldown.
- `BOT_TOKEN` comes from the host's environment/secrets only — never hardcoded.
- At startup the bot deletes any old webhook so polling receives updates.
- ffmpeg comes from the `imageio-ffmpeg` pip package (no apt/Dockerfile needed).

## Deploy on FadeHost (free, no card, always on, polling)
1. FadeHost account (free tier: 1 bot, 256 MB, always on).
2. Apps → host a Telegram bot → connect this GitHub repo.
3. Start command: `python bot.py`
4. Environment: `BOT_TOKEN` = the bot token (masked in the panel).
5. Send /start to the bot in Telegram.

## Files
- `bot.py` — the bot
- `requirements.txt` — pyTelegramBotAPI, yt-dlp, Flask, imageio-ffmpeg
