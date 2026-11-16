import subprocess
import requests
import os
import time
import glob
import json
import threading
import asyncio
import shutil
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MIXDROP_KEY = os.getenv("MIXDROP_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")

if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN is missing in Railway Variables!")
# ==========================================

USERNAMES_FILE = "usernames.json"
MAX_TELEGRAM_SIZE = 50 * 1024 * 1024

# ================= PLATFORMS - ONLY 3 =================
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

# ================= BOT COMMANDS =================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🎬 Welcome to Yoon Auto Recorder 🎬\n\n"
        "📌 Commands:\n"
        "/add username - ➕ Add Twitch account\n"
        "/add kick:username - ➕ Add Kick\n"
        "/add nimo:RoomID - ➕ Add Nimo (Room ID only!)\n"
        "/remove username - ➖ Remove an account\n"
        "/list - 📋 Show all accounts\n"
        "/status - 🔴 Check recording status\n\n"
        "🎞️ Quality: 360p\n"
        "✂️ Live Upload: Upload when 50MB reached\n"
        "☁️ Upload: Mixdrop + Telegram\n\n"
        "🌐 Platforms: ONLY 3\n"
        "twitch, kick, nimo\n\n"
        "💡 Examples:\n"
        "/add yoon_gaming1\n"
        "/add kick:yoon_live\n"
        "/add nimo:818540864"
    )
    await update.message.reply_text(message)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /add username OR /add kick:username OR /add nimo:RoomID\n💡 Example: /add nimo:818540864")
        return
    raw = " ".join(context.args).lower().strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)
    if entry not in USERNAMES:
        USERNAMES.append(entry)
        save_usernames()
        await update.message.reply_text(
            f"✅ Added: {display_name(entry)}\n"
            f"🔴 Auto Record is now ON - 360p\n"
            f"📁 50MB parts will be uploaded while live."
        )
    else:
        await update.message.reply_text(f"ℹ️ {display_name(entry)} is already added.")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /remove username OR /remove kick:username OR /remove nimo:RoomID\n💡 Example: /remove nimo:818540864")
        return
    raw = " ".join(context.args).lower().strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)
    if entry in USERNAMES:
        USERNAMES.remove(entry)
        save_usernames()
        if entry in RECORDING:
            RECORDING.discard(entry)
        await update.message.reply_text(
            f"🗑️ Removed: {display_name(entry)}\n"
            f"⛔ Auto Record is now OFF for this account."
        )
    else:
        await update.message.reply_text(f"❌ Not Found: {display_name(entry)}\n📋 Use /list to see all accounts.")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not USERNAMES:
        await update.message.reply_text("📭 No accounts added yet.\n➕ Use /add username to add one.")
        return
    text = "👀 Watching Accounts:\n\n"
    for user in USERNAMES:
        status = "🔴 REC" if user in RECORDING else "⏳ Waiting"
        text += f"{display_name(user)} - {status}\n"
    text += "\n🎞️ Quality: 360p\n✂️ Live Upload: 50MB"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No one is live right now.")
        return
    text = "🔴 Currently Recording:\n\n"
    for user in RECORDING:
        text += f"🎥 Live: {display_name(user)} - 360p (Live Upload ON)\n"
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
        if response.get("success"):
            return response["result"]["url"]
    except Exception as e:
        print(f"Mixdrop Error: {e}")
    return None

def is_live(entry):
    for url in get_all_urls(entry):
        result = subprocess.run(
            ["streamlink", url, "--json"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and "No playable streams" not in result.stdout and "streams" in result.stdout and '"streams": {}' not in result.stdout:
            print(f"is_live TRUE via streamlink: {url}")
            return True
        result2 = subprocess.run(
            ["yt-dlp", url, "--skip-download", "--quiet"],
            capture_output=True
        )
        if result2.returncode == 0:
            print(f"is_live TRUE via yt-dlp: {url}")
            return True
    print(f"is_live FALSE: {entry}")
    return False

def get_stream_url(entry):
    # Get Direct HLS URL via Streamlink
    for url in get_all_urls(entry):
        for quality in ["360p", "360p30", "best"]:
            result = subprocess.run(
                ["streamlink", url, quality, "--stream-url"],
                capture_output=True, text=True
            )
            stream_url = result.stdout.strip()
            if stream_url.startswith("http"):
                print(f"Got stream URL via streamlink {quality}: {url}")
                return stream_url
        # Get URL via yt-dlp
        result = subprocess.run(
            ["yt-dlp", url, "-f", "best[height<=360]", "-g"],
            capture_output=True, text=True
        )
        stream_url = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        if stream_url.startswith("http"):
            print(f"Got stream URL via yt-dlp: {url}")
            return stream_url
    return None

async def upload_one_part(entry, part_path, index, app):
    # Function to upload one part
    size_mb = os.path.getsize(part_path) / (1024 * 1024)
    await app.bot.send_message(CHANNEL_ID, f"☁️ Uploading Part {index} ({size_mb:.1f} MB)... {display_name(entry)}\n🎥 Next part is recording...")
    mixdrop_link = upload_to_mixdrop(part_path)
    if not mixdrop_link:
        mixdrop_link = "Upload Failed"
        await app.bot.send_message(CHANNEL_ID, f"❌ Mixdrop Failed - Part {index}: {display_name(entry)}")
    else:
        await app.bot.send_message(
            CHANNEL_ID,
            f"✅ Mixdrop Done - Part {index}\n"
            f"{display_name(entry)}\n"
            f"🔗 {mixdrop_link}"
        )
    caption = (
        f"🎬 Live Replay: {display_name(entry)} [360p]\n"
        f"📂 Part {index}\n"
        f"🔗 Mixdrop Part {index}: {mixdrop_link}\n"
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

async def process_stream(entry, app):
    platform, uid = parse_entry(entry)
    base_name = f"{platform}_{uid}_{int(time.time())}"
    await app.bot.send_message(CHANNEL_ID, f"🔴 LIVE Detected!\n{display_name(entry)}\n🎥 Recording Started... [360p]\n⚡ Live Upload ON - Upload when 50MB reached")

    stream_url = get_stream_url(entry)
    if not stream_url:
        await app.bot.send_message(CHANNEL_ID, f"❌ Recording Failed (No Stream URL): {display_name(entry)}")
        RECORDING.discard(entry)
        return

    # Split into 600 sec (10 min) parts with ffmpeg
    # 360p 10 min = approx 35-50MB, fits Telegram 50MB limit
    pattern = f"{base_name}_part%03d.mp4"
    ffmpeg_proc = subprocess.Popen([
        "ffmpeg", "-y", "-i", stream_url,
        "-c", "copy",
        "-f", "segment",
        "-segment_time", "600",
        "-reset_timestamps", "1",
        "-segment_format", "mp4",
        pattern
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    uploaded = 0
    # Upload loop while live is running
    while ffmpeg_proc.poll() is None:
        await asyncio.sleep(30)
        # Skip newest file, upload previous ones
        parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
        # Newest one is still recording, do not upload it
        ready_parts = parts[:-1] if len(parts) > 1 else []
        for part_path in ready_parts:
            # Check if file size is stable, upload only if stable
            size1 = os.path.getsize(part_path)
            await asyncio.sleep(2)
            if not os.path.exists(part_path):
                continue
            size2 = os.path.getsize(part_path)
            if size1 == size2 and size1 > 1000:
                uploaded += 1
                await upload_one_part(entry, part_path, uploaded, app)

    # Upload remaining parts after live ends
    await asyncio.sleep(3)
    parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
    for part_path in parts:
        if os.path.exists(part_path) and os.path.getsize(part_path) > 1000:
            uploaded += 1
            await upload_one_part(entry, part_path, uploaded, app)

    RECORDING.discard(entry)
    await app.bot.send_message(
        CHANNEL_ID,
        f"🎉 Completed: {display_name(entry)}\n"
        f"📂 Total Parts: {uploaded} x ~50MB\n"
        f"🎞️ Quality: 360p\n"
        f"✅ Enjoy!"
    )

def check_loop(app, loop):
    while True:
        for username in list(USERNAMES):
            if username not in RECORDING and is_live(username):
                RECORDING.add(username)
                # FIX: Use bot main loop, do not create new loop with asyncio.run()
                # This fixes "Event loop is closed" error
                asyncio.run_coroutine_threadsafe(process_stream(username, app), loop)
        time.sleep(60)

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing! Check Railway Variables")
        return
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(read_timeout=600, write_timeout=600, connect_timeout=60, pool_timeout=600)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))

    # FIX: Get main loop and pass it to check_loop
    loop = asyncio.get_event_loop()
    threading.Thread(target=check_loop, args=(app, loop), daemon=True).start()

    print("Bot Running - 360p Live Upload Mode... [Streamlink + ffmpeg segment]")
    app.run_polling()

if __name__ == "__main__":
    main()
