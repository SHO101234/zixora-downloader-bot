"""zixora video downloader bot — original Gemini bot, host-ready version.

Same behaviour as before: YouTube/TikTok links -> menu (Video resolutions,
MP3, Thumbnail, Subtitle), @zixoravpn channel-join gate, Mon-Sat 09:30-17:30
hours (Sunday closed), 3-min cooldown for non-admins, /stats for admin.

Changes vs the original paste (only these):
  * TOKEN comes from the BOT_TOKEN environment variable (host Secret).
    NEVER paste the token into this file.
  * A tiny Flask health server runs on port 7860 (/health) in a thread,
    so Hugging Face Spaces + keep-alive pings can see the bot is alive.
    The bot itself still uses polling (infinity_polling), as before.
"""
import os
import threading

from flask import Flask

app = Flask(__name__)


@app.route("/health")
def health():
    return {"ok": True}


@app.route("/")
def index():
    return {"ok": True, "bot": "zixora downloader"}


def _serve_health():
    # HF Docker Spaces expect the container on port 7860.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))


threading.Thread(target=_serve_health, daemon=True).start()

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = None

import telebot
from telebot import types
import yt_dlp

# YouTube bot-check avoidance: prefer mobile player clients (android/ios)
# over the web client, which datacenter IPs get challenged on.
YT_EXTRACTOR_ARGS = {'youtube': {'player_client': ['android', 'ios']}}
import time
import json
from datetime import datetime, time as d_time

# ==================== CONFIGURATION ====================
# Token is set in the host's Secrets as BOT_TOKEN. Never hardcode it here.
TOKEN = os.environ.get("BOT_TOKEN", "")
if not TOKEN:
    raise SystemExit("BOT_TOKEN environment variable is not set. Set it in Space Secrets.")
ADMIN_ID = 1702338053         # Telegram User ID
CHANNEL_USERNAME = '@zixoravpn'
CHANNEL_LINK = 'https://t.me/zixoravpn'
COOLDOWN_SECONDS = 180         # Rate Limit (3 minutes)
# =======================================================

telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 60

bot = telebot.TeleBot(TOKEN)
user_links = {}
user_last_action = {}

USERS_FILE = 'users.json'
STATS_FILE = 'stats.json'


def load_data(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except Exception:
                return default_value
    return default_value


def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def track_user(user_id):
    users = load_data(USERS_FILE, [])
    if user_id not in users:
        users.append(user_id)
        save_data(USERS_FILE, users)


def add_download_stat():
    stats = load_data(STATS_FILE, {"total_downloads": 0})
    stats["total_downloads"] += 1
    save_data(STATS_FILE, stats)


def check_membership(user_id):
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
        return False
    except Exception as e:
        print(f"Membership Check Error: {e}")
        return True


def is_bot_active(user_id):
    if user_id == ADMIN_ID:
        return True
    now = datetime.now()
    weekday = now.weekday()
    if weekday == 6:
        return False
    current_time = now.time()
    start_time = d_time(9, 30)
    end_time = d_time(17, 30)
    return start_time <= current_time <= end_time


def send_join_request(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_join = types.InlineKeyboardButton("📢 Join Zixora Channel", url=CHANNEL_LINK)
    btn_confirm = types.InlineKeyboardButton("✅ Joined (အတည်ပြုရန်)", callback_data="check_join")
    markup.add(btn_join, btn_confirm)
    bot.send_message(
        chat_id,
        "⚠️ **Bot ကို အသုံးပြုရန် Zixora Channel သို့ အရင် Join ပေးပါ။**\n\nChannel Join ပြီးပါက အောက်ပါ **Joined (အတည်ပြုရန်)** ခလုတ်ကို နှိပ်ပါ။",
        reply_markup=markup,
        parse_mode="Markdown"
    )


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.chat.id
    track_user(user_id)
    if not is_bot_active(user_id):
        bot.reply_to(message, "🔴 **Bot ခေတ္တပိတ်ထားပါသည်!**\n\n🕒 **အလုပ်ချိန် -** တနင်္လာမှ စနေ (မနက် ၉:၃၀ မှ ညနေ ၅:၃၀ ထိ)\n🔴 **တနင်္ဂနွေနေ့ -** ပိတ်ပါသည်။\n\nသတ်မှတ်ထားသော အလုပ်ချိန်အတွင်း ပြန်လည်လာရောက် အသုံးပြုပေးပါရန် မေတ္တာရပ်ခံအပ်ပါသည်။", parse_mode="Markdown")
        return
    if not check_membership(user_id):
        send_join_request(user_id)
        return
    bot.reply_to(message, "မင်္ဂလာပါ။ YouTube သို့မဟုတ် TikTok လင့်ခ် ပို့ပေးပါ။\nVideo၊ Audio (MP3)၊ Subtitle နှင့် Thumbnail များကို ဒေါင်းလုဒ်ဆွဲနိုင်ပါသည်။")


@bot.message_handler(commands=['stats'])
def show_stats(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ ဒီ Command ကို Admin သာ အသုံးပြုနိုင်ပါတယ်။")
        return
    users = load_data(USERS_FILE, [])
    stats = load_data(STATS_FILE, {"total_downloads": 0})
    total_users = len(users)
    total_downloads = stats.get("total_downloads", 0)
    text = (
        f"📊 **Bot Statistics Panel**\n\n"
        f"👥 အသုံးပြုသူ စုစုပေါင်း: `{total_users}` ယောက်\n"
        f"📥 စုစုပေါင်း ဒေါင်းလုဒ်ဆွဲမှု: `{total_downloads}` ကြိမ်"
    )
    bot.reply_to(message, text, parse_mode="Markdown")


@bot.message_handler(func=lambda message: True)
def handle_link(message):
    user_id = message.chat.id
    track_user(user_id)
    if not is_bot_active(user_id):
        bot.reply_to(message, "🔴 **Bot ခေတ္တပိတ်ထားပါသည်!**\n\n🕒 **အလုပ်ချိန် -** တနင်္လာမှ စနေ (မနက် ၉:၃၀ မှ ညနေ ၅:၃၀ ထိ)\n🔴 **တနင်္ဂနွေနေ့ -** ပိတ်ပါသည်။", parse_mode="Markdown")
        return
    if not check_membership(user_id):
        send_join_request(user_id)
        return
    if user_id != ADMIN_ID:
        last_time = user_last_action.get(user_id, 0)
        time_passed = time.time() - last_time
        if time_passed < COOLDOWN_SECONDS:
            time_left = int(COOLDOWN_SECONDS - time_passed)
            mins, secs = divmod(time_left, 60)
            bot.reply_to(message, f"⏳ စနစ်ကြန့်ကြာမှုကို ကာကွယ်ရန် Rate Limit သတ်မှတ်ထားပါသည်။ နောက်ထပ် **{mins} မိနစ် {secs} စက္ကန့်** နေမှ လင့်ခ်အသစ် ထပ်ပို့ပေးပါ။")
            return
    url = message.text.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        bot.reply_to(message, "ကျေးဇူးပြု၍ မှန်ကန်သော Link ပို့ပေးပါ။")
        return
    user_links[message.chat.id] = url
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_video = types.InlineKeyboardButton("🎬 Video (Resolution ရွေးရန်)", callback_data="menu_video")
    btn_audio = types.InlineKeyboardButton("🎵 MP3 (Audio)", callback_data="audio")
    btn_thumb = types.InlineKeyboardButton("🖼 Thumbnail", callback_data="thumbnail")
    btn_sub = types.InlineKeyboardButton("📝 Subtitle", callback_data="subtitle")
    markup.add(btn_video, btn_audio)
    markup.add(btn_thumb, btn_sub)
    bot.reply_to(message, "ပြုလုပ်လိုသည့် ပုံစံကို ရွေးချယ်ပါ 👇", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    if not is_bot_active(chat_id):
        bot.answer_callback_query(call.id, "🔴 အလုပ်ချိန်မဟုတ်တော့ပါ သို့မဟုတ် ပိတ်ရက်ဖြစ်နေပါသည်။", show_alert=True)
        return
    if call.data == "check_join":
        if check_membership(chat_id):
            bot.answer_callback_query(call.id, "✅ Channel Join ထားမှု အတည်ပြုပြီးပါပြီ!")
            bot.send_message(chat_id, "ကျေးဇူးတင်ပါသည်။ အခု YouTube သို့မဟုတ် TikTok Link ပို့ပြီး ဒေါင်းလုဒ်ဆွဲနိုင်ပါပြီ။")
        else:
            bot.answer_callback_query(call.id, "❌ Channel မ join ရသေးပါ။ ကျေးဇူးပြု၍ အရင် Join ပေးပါ။", show_alert=True)
        return
    if not check_membership(chat_id):
        send_join_request(chat_id)
        return
    url = user_links.get(chat_id)
    if not url:
        bot.answer_callback_query(call.id, "Link သက်တမ်းကုန်သွားပါပြီ။ Link အသစ်ပြန်ပို့ပါ။")
        return
    if call.data == "menu_video":
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("360p", callback_data="vid_360"),
            types.InlineKeyboardButton("480p", callback_data="vid_480"),
            types.InlineKeyboardButton("720p (HD)", callback_data="vid_720"),
            types.InlineKeyboardButton("1080p (FHD)", callback_data="vid_1080"),
            types.InlineKeyboardButton("🔙 နောက်သို့", callback_data="back_main")
        )
        bot.edit_message_text("🎬 ဗီဒီယို အရည်အသွေး (Resolution) ရွေးပါ 👇", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
        return
    if call.data == "back_main":
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_video = types.InlineKeyboardButton("🎬 Video (Resolution ရွေးရန်)", callback_data="menu_video")
        btn_audio = types.InlineKeyboardButton("🎵 MP3 (Audio)", callback_data="audio")
        btn_thumb = types.InlineKeyboardButton("🖼 Thumbnail", callback_data="thumbnail")
        btn_sub = types.InlineKeyboardButton("📝 Subtitle", callback_data="subtitle")
        markup.add(btn_video, btn_audio)
        markup.add(btn_thumb, btn_sub)
        bot.edit_message_text("ပြုလုပ်လိုသည့် ပုံစံကို ရွေးချယ်ပါ 👇", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
        return
    if chat_id != ADMIN_ID:
        user_last_action[chat_id] = time.time()
    start_time = time.time()
    file_prefix = f"file_{chat_id}_{int(start_time)}"
    try:
        if call.data == "thumbnail":
            bot.edit_message_text("⏳ Thumbnail ရယူနေပါပြီ...", chat_id=chat_id, message_id=call.message.message_id)
            ydl_opts = {'quiet': True, 'noplaylist': True, 'extractor_args': YT_EXTRACTOR_ARGS}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                thumb_url = info.get('thumbnail')
                if thumb_url:
                    bot.send_photo(chat_id, thumb_url, caption=f"🖼 **{info.get('title', 'Thumbnail')}**", parse_mode="Markdown")
                    add_download_stat()
                    bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
                else:
                    bot.edit_message_text("❌ Thumbnail ရှာမတွေ့ပါ။", chat_id=chat_id, message_id=call.message.message_id)
            return
        if call.data == "subtitle":
            bot.edit_message_text("⏳ Subtitle ရှာဖွေနေပါပြီ...", chat_id=chat_id, message_id=call.message.message_id)
            sub_template = f"sub_{file_prefix}"
            ydl_opts = {
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en'],
                'outtmpl': sub_template,
                'noplaylist': True,
                'extractor_args': YT_EXTRACTOR_ARGS,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            sent_any = False
            for file in os.listdir('.'):
                if file.startswith(sub_template):
                    with open(file, 'rb') as sub_file:
                        bot.send_document(chat_id, sub_file, caption="📝 ဤသည်မှာ ရရှိသော Subtitle ဖိုင် ဖြစ်ပါသည်။")
                    os.remove(file)
                    sent_any = True
            if sent_any:
                add_download_stat()
                bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
            else:
                bot.edit_message_text("❌ ဤ Link တွင် Subtitle ဖိုင် မရှိပါ။", chat_id=chat_id, message_id=call.message.message_id)
            return
        bot.edit_message_text("⏳ ဒေါင်းလုဒ် ဆွဲနေပါပြီ... ခဏစောင့်ပါ။", chat_id=chat_id, message_id=call.message.message_id)
        if call.data.startswith("vid_"):
            res = call.data.split("_")[1]
            out_filename = f"video_{file_prefix}.mp4"
            ydl_opts = {
                'ffmpeg_location': FFMPEG_EXE,
                'format': f'bestvideo[height<={res}]+bestaudio/best[height<={res}]',
                'outtmpl': out_filename,
                'noplaylist': True,
                'merge_output_format': 'mp4',
                'extractor_args': YT_EXTRACTOR_ARGS,
                'postprocessor_args': [
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-movflags', '+faststart'
                ],
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                download_time = int(time.time() - start_time)
                bot.edit_message_text(f"📤 Telegram သို့ Video တင်နေပါပြီ... (ကြာချိန်: {download_time} စက္ကန့်)", chat_id=chat_id, message_id=call.message.message_id)
                file_size_mb = os.path.getsize(out_filename) / (1024 * 1024)
                if file_size_mb > 50:
                    bot.edit_message_text(
                        f"❌ ဖိုင်ဆိုဒ် ({file_size_mb:.1f}MB) ကြီးလွန်းသဖြင့် Video အနေဖြင့် တင်၍ မရပါ။ (Telegram Bot API Limit: 50MB)\n\n"
                        f"💡 **အကြံပြုချက် -** 720p သို့မဟုတ် 1080p အစား Resolution အနိမ့် (`360p` သို့မဟုတ် `480p`) ကို ရွေးချယ်ပြီး ပြန်လည်ဒေါင်းလုဒ်ဆွဲပါ။",
                        chat_id=chat_id,
                        message_id=call.message.message_id,
                        parse_mode="Markdown"
                    )
                else:
                    with open(out_filename, 'rb') as video_file:
                        bot.send_video(chat_id, video_file, timeout=300)
                    bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
                    add_download_stat()
            finally:
                if os.path.exists(out_filename):
                    os.remove(out_filename)
        elif call.data == "audio":
            out_filename = f"audio_{file_prefix}.mp3"
            ydl_opts = {
                'ffmpeg_location': FFMPEG_EXE,
                'format': 'bestaudio/best',
                'outtmpl': out_filename,
                'noplaylist': True,
                'extractor_args': YT_EXTRACTOR_ARGS,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception:
                out_filename = f"audio_{file_prefix}.m4a"
                ydl_opts_fallback = {
                    'format': 'm4a/bestaudio/best',
                    'outtmpl': out_filename,
                    'noplaylist': True,
                    'extractor_args': YT_EXTRACTOR_ARGS,
                }
                with yt_dlp.YoutubeDL(ydl_opts_fallback) as ydl:
                    ydl.download([url])
            try:
                download_time = int(time.time() - start_time)
                bot.edit_message_text(f"📤 Telegram သို့ Audio တင်နေပါပြီ... (ကြာချိန်: {download_time} စက္ကန့်)", chat_id=chat_id, message_id=call.message.message_id)
                with open(out_filename, 'rb') as audio_file:
                    bot.send_audio(chat_id, audio_file, timeout=300)
                bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
                add_download_stat()
            finally:
                if os.path.exists(out_filename):
                    os.remove(out_filename)
    except Exception as e:
        bot.edit_message_text(f"❌ Error ဖြစ်သွားပါသည်:\n{str(e)}", chat_id=chat_id, message_id=call.message.message_id)


if __name__ == "__main__":
    try:
        bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        print(f"delete_webhook: {e}")
    bot.set_my_commands([
        types.BotCommand("start", "🚀 Bot စတင်ရန် / Menu ကြည့်ရန်"),
        types.BotCommand("stats", "📊 Bot အသုံးပြုမှု စာရင်းကြည့်ရန် (Admin Only)")
    ])
    print("🚀 Bot စတင် အလုပ်လုပ်နေပါပြီ...")
    bot.infinity_polling()
