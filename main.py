import subprocess
import requests
import os
import time
import glob
import json
import threading
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================================================
# ⚙️ CONFIG
# ==================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MIXDROP_KEY = os.getenv("MIXDROP_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

USERNAMES_FILE = "usernames.json"

# ==================================================
# 🌐 PLATFORMS
# ==================================================
PLATFORMS = {
    "twitch": "https://twitch.tv/{id}",
    "kick": "https://kick.com/{id}",
    "nimo": "https://www.nimo.tv/{id}",
}

def parse_entry(entry):
    entry = entry.lower().replace("@", "").strip()
    if ":" in entry:
        platform, uid = entry.split(":", 1)
        platform = platform.strip()
        uid = uid.strip()
        if platform not in PLATFORMS:
            platform = "twitch"
    else:
        platform = "twitch"
        uid = entry
    return platform, uid

def make_entry(platform, uid):
    return f"{platform}:{uid}"

def get_url(entry):
    platform, uid = parse_entry(entry)
    return PLATFORMS[platform].format(id=uid)

def get_all_urls(entry):
    platform, uid = parse_entry(entry)
    if platform == "nimo":
        return [
            f"https://www.nimo.tv/{uid}",
            f"https://www.nimo.tv/live/{uid}",
            f"https://m.nimo.tv/live/{uid}",
        ]
    return [get_url(entry)]

def display_name(entry):
    platform, uid = parse_entry(entry)
    return f"@{uid} [{platform}]"

if os.path.exists(USERNAMES_FILE):
    try:
        USERNAMES = json.load(open(USERNAMES_FILE))
        migrated = []
        for u in USERNAMES:
            if ":" not in str(u):
                migrated.append(make_entry("twitch", str(u)))
            else:
                migrated.append(str(u).lower())
        USERNAMES = migrated
    except Exception:
        USERNAMES = []
else:
    USERNAMES = []

RECORDING = set()

def save_usernames():
    with open(USERNAMES_FILE, "w") as f:
        json.dump(USERNAMES, f)

# ==================================================
# 🤖 BOT COMMANDS
# ==================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🎬✨ Welcome to Yoon Auto Recorder ✨🎬\n\n"
        "📌 ─── Commands ─── 📌\n"
        "➕ /add username\n"
        "➕ /add kick:username\n"
        "➕ /add nimo:RoomID\n"
        "📋 /list - Show All Accounts\n"
        "🔴 /status - Recording Status\n\n"
        "🎞️ Quality : 360p\n"
        "📹 Mode : Video + Caption Only\n"
        "☁️ Backup : Mixdrop\n\n"
        "🌐 Platforms : Twitch | Kick | Nimo\n\n"
        "💡 ─── Examples ─── 💡\n"
        "👉 /add yoon_gaming1\n"
        "👉 /add kick:yoon_live\n"
        "👉 /add nimo:818540864"
    )
    await update.message.reply_text(message)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage:\n"
            "/add username\n"
            "/add kick:username\n"
            "/add nimo:RoomID"
        )
        return

    raw = " ".join(context.args).lower().strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)

    if entry not in USERNAMES:
        USERNAMES.append(entry)
        save_usernames()
        await update.message.reply_text(
            f"✅ Added Successfully!\n\n"
            f"🎬 {display_name(entry)}\n"
            f"🔴 Auto Record : ON\n"
            f"🎞️ Quality : 360p"
        )
    else:
        await update.message.reply_text(f"ℹ️ Already Added : {display_name(entry)}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not USERNAMES:
        await update.message.reply_text(
            "📭 No Accounts Added Yet!\n"
            "➕ Use /add to add one."
        )
        return

    text = "👀 ─── Watching Accounts ─── 👀\n\n"
    for user in USERNAMES:
        status = "🔴 REC" if user in RECORDING else "⏳ Waiting"
        text += f"• {display_name(user)} — {status}\n"

    text += "\n🎞️ Quality : 360p\n✂️ Parts : 10 Min Each"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No One Is Live Right Now.")
        return

    text = "🔴 ─── Currently Recording ─── 🔴\n\n"
    for user in RECORDING:
        text += f"🎥 {display_name(user)} — 360p\n"

    await update.message.reply_text(text)

# ==================================================
# ☁️ HELPERS
# ==================================================

def upload_to_mixdrop(file_path):
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                "https://ul.mixdrop.ag/api",
                data={"key": MIXDROP_KEY},
                files={"file": f},
                timeout=3600
            ).json()
        print(f"Mixdrop Response: {response}")
        if response.get("success"):
            return response["result"]["url"]
    except Exception as e:
        print(f"Mixdrop Error: {e}")
    return None

def is_live(entry):
    platform, uid = parse_entry(entry)
    for url in get_all_urls(entry):
        result = subprocess.run(
            ["streamlink", url, "360p,best", "--stream-url"],
            capture_output=True, text=True, timeout=30
        )
        stream_url = result.stdout.strip()
        if stream_url.startswith("http"):
            return True

        if platform != "nimo":
            result2 = subprocess.run(
                ["yt-dlp", url, "--skip-download", "--quiet"],
                capture_output=True, timeout=30
            )
            if result2.returncode == 0:
                return True
    return False

def get_stream_url(entry):
    for url in get_all_urls(entry):
        for quality in ["360p", "360p30", "best"]:
            result = subprocess.run(
                ["streamlink", url, quality, "--stream-url"],
                capture_output=True, text=True, timeout=30
            )
            stream_url = result.stdout.strip()
            if stream_url.startswith("http"):
                return stream_url

        platform, _ = parse_entry(entry)
        if platform != "nimo":
            result = subprocess.run(
                ["yt-dlp", url, "-f", "best[height<=360]", "-g"],
                capture_output=True, text=True, timeout=30
            )
            stream_url = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
            if stream_url.startswith("http"):
                return stream_url
    return None

# ==================================================
# 🎬 VIDEO + CAPTION ONLY
# ==================================================

async def upload_one_part(entry, part_path, index, app):
    mixdrop_link = upload_to_mixdrop(part_path)

    if mixdrop_link:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📂 Part : {index}\n"
            f"🎞️ Quality : 360p\n"
            f"🔗 Mixdrop Part {index} :\n{mixdrop_link}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"▶️ Part {index} — Watch Here ✨"
        )
    else:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📂 Part : {index}\n"
            f"🎞️ Quality : 360p\n"
            f"❌ Mixdrop Part {index} : Upload Failed\n"
            f"━━━━━━━━━━━━━━━\n"
            f"▶️ Part {index} — Watch Here ✨"
        )

    with open(part_path, "rb") as video:
        await app.bot.send_video(
            CHANNEL_ID,
            video=video,
            caption=caption,
            supports_streaming=True
        )

    os.remove(part_path)
    print(f"Uploaded Part {index} : {entry}")

async def process_stream(entry, app):
    platform, uid = parse_entry(entry)
    base_name = f"{platform}_{uid}_{int(time.time())}"
    print(f"LIVE Detected : {entry}")

    stream_url = get_stream_url(entry)
    if not stream_url:
        print(f"Recording Failed - No Stream URL : {entry}")
        RECORDING.discard(entry)
        return

    pattern = f"{base_name}_part%03d.mp4"
    log_file = open(f"{base_name}_ffmpeg.log", "w")

    ffmpeg_proc = subprocess.Popen([
        "ffmpeg", "-y", "-i", stream_url,
        "-c", "copy",
        "-f", "segment",
        "-segment_time", "600",
        "-reset_timestamps", "1",
        "-segment_format", "mp4",
        pattern
    ], stdout=log_file, stderr=log_file)

    uploaded = 0

    while ffmpeg_proc.poll() is None:
        await asyncio.sleep(30)
        parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
        ready_parts = parts[:-1] if len(parts) > 1 else []

        for part_path in ready_parts:
            size1 = os.path.getsize(part_path)
            await asyncio.sleep(2)
            if not os.path.exists(part_path):
                continue
            size2 = os.path.getsize(part_path)
            if size1 == size2 and size1 > 1000:
                uploaded += 1
                await upload_one_part(entry, part_path, uploaded, app)

    print(f"ffmpeg exited {ffmpeg_proc.poll()} for {entry}")
    try:
        log_file.close()
    except Exception:
        pass

    await asyncio.sleep(3)
    parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
    for part_path in parts:
        if os.path.exists(part_path) and os.path.getsize(part_path) > 1000:
            uploaded += 1
            await upload_one_part(entry, part_path, uploaded, app)

    RECORDING.discard(entry)
    print(f"Completed : {entry} - Total {uploaded} parts")

# ==================================================
# 🔄 CHECK LOOP
# ==================================================

def check_loop(app, loop):
    while True:
        for username in list(USERNAMES):
            if username not in RECORDING and is_live(username):
                RECORDING.add(username)
                asyncio.run_coroutine_threadsafe(process_stream(username, app), loop)
        time.sleep(60)

# ==================================================
# 🚀 MAIN
# ==================================================

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        read_timeout=600,
        write_timeout=600,
        connect_timeout=60,
        pool_timeout=600
    )

    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))

    loop = asyncio.get_event_loop()
    threading.Thread(target=check_loop, args=(app, loop), daemon=True).start()

    print("Bot Running - VIDEO + CAPTION ONLY Mode...")
    app.run_polling()

if __name__ == "__main__":
    main()
