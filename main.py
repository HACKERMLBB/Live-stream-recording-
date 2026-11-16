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

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MIXDROP_KEY = os.getenv("MIXDROP_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")
# ==========================================

USERNAMES_FILE = "usernames.json"

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
    except:
        USERNAMES = []
else:
    USERNAMES = []

RECORDING = set()

def save_usernames():
    with open(USERNAMES_FILE, "w") as f:
        json.dump(USERNAMES, f)

# ================= BOT COMMANDS - මේවා Bot එකට විතරයි, Channel එකට යන්නේ නෑ =================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🎬 Welcome to Yoon Auto Recorder 🎬\n\n"
        "📌 Commands:\n"
        "/add username - ➕ Add Twitch\n"
        "/add kick:username - ➕ Add Kick\n"
        "/add nimo:RoomID - ➕ Add Nimo\n"
        "/remove username - ➖ Remove\n"
        "/list - 📋 Show all\n"
        "/status - 🔴 Status\n\n"
        "🎞️ Quality: 360p\n"
        "📹 Channel එකට Video + Caption විතරයි යන්නේ"
    )
    await update.message.reply_text(message)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /add username OR /add kick:username OR /add nimo:RoomID")
        return
    raw = " ".join(context.args).lower().strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)
    if entry not in USERNAMES:
        USERNAMES.append(entry)
        save_usernames()
        await update.message.reply_text(f"✅ Added: {display_name(entry)}")
    else:
        await update.message.reply_text(f"ℹ️ {display_name(entry)} is already added.")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /remove username")
        return
    raw = " ".join(context.args).lower().strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)
    if entry in USERNAMES:
        USERNAMES.remove(entry)
        save_usernames()
        if entry in RECORDING:
            RECORDING.discard(entry)
        await update.message.reply_text(f"🗑️ Removed: {display_name(entry)}")
    else:
        await update.message.reply_text(f"❌ Not Found: {display_name(entry)}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not USERNAMES:
        await update.message.reply_text("📭 No accounts added yet.")
        return
    text = "👀 Watching:\n\n"
    for user in USERNAMES:
        status = "🔴 REC" if user in RECORDING else "⏳ Waiting"
        text += f"{display_name(user)} - {status}\n"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No one is live right now.")
        return
    text = "🔴 Currently Recording:\n\n"
    for user in RECORDING:
        text += f"🎥 {display_name(user)}\n"
    await update.message.reply_text(text)

# ================= HELPERS =================

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

# ================= VIDEO + CAPTION ONLY =================
# Channel එකට යන්නේ මේක විතරයි. වෙන කිසිම Message එකක් නෑ.

async def upload_one_part(entry, part_path, index, app):
    mixdrop_link = upload_to_mixdrop(part_path)

    # Video එකත් එක්ක එන Caption එක - මේකෙන් තමයි Part එක, Mixdrop එක හොයාගන්නේ
    if mixdrop_link:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"📂 Part {index}\n"
            f"🔗 Mixdrop Part {index}: {mixdrop_link}\n"
            f"▶️ Part {index} - Watch Here"
        )
    else:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"📂 Part {index}\n"
            f"❌ Mixdrop Part {index}: Upload Failed\n"
            f"▶️ Part {index} - Watch Here"
        )

    with open(part_path, "rb") as video:
        await app.bot.send_video(
            CHANNEL_ID,
            video=video,
            caption=caption,
            supports_streaming=True
        )
    os.remove(part_path)
    print(f"Uploaded Part {index} - Video + Caption Only: {entry}")

async def process_stream(entry, app):
    platform, uid = parse_entry(entry)
    base_name = f"{platform}_{uid}_{int(time.time())}"
    # ❌ LIVE Detected Message අයින් කරා - Log එකේ විතරයි
    print(f"LIVE Detected (Log only): {entry}")

    stream_url = get_stream_url(entry)
    if not stream_url:
        print(f"Recording Failed - No Stream URL: {entry}")
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
    except:
        pass

    await asyncio.sleep(3)
    parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
    for part_path in parts:
        if os.path.exists(part_path) and os.path.getsize(part_path) > 1000:
            uploaded += 1
            await upload_one_part(entry, part_path, uploaded, app)

    RECORDING.discard(entry)
    # ❌ Completed Message අයින් කරා - Log එකේ විතරයි
    print(f"Completed (Log only): {entry} - Total {uploaded} parts")

def check_loop(app, loop):
    while True:
        for username in list(USERNAMES):
            if username not in RECORDING and is_live(username):
                RECORDING.add(username)
                asyncio.run_coroutine_threadsafe(process_stream(username, app), loop)
        time.sleep(60)

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(read_timeout=600, write_timeout=600, connect_timeout=60, pool_timeout=600)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))

    loop = asyncio.get_event_loop()
    threading.Thread(target=check_loop, args=(app, loop), daemon=True).start()

    print("Bot Running - VIDEO + CAPTION ONLY Mode...")
    app.run_polling()

if __name__ == "__main__":
    main()
