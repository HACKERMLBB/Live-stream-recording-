import subprocess
import requests
import os
import time
import glob
import json
import threading
import asyncio
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ==================================================
# ⚙️ CONFIG
# ==================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
MIXDROP_KEY = os.getenv("MIXDROP_KEY")
MIXDROP_EMAIL = os.getenv("MIXDROP_EMAIL")
CHANNEL_ID = os.getenv("CHANNEL_ID")

USERNAMES_FILE = "usernames.json"

# ==================================================
# 🌐 PLATFORMS - m.nimo.tv
# ==================================================
PLATFORMS = {
    "twitch": "https://twitch.tv/{id}",
    "kick": "https://kick.com/{id}",
    "nimo": "https://m.nimo.tv/live/{id}",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Referer": "https://m.nimo.tv/",
    "Origin": "https://m.nimo.tv",
    "Accept": "application/json, text/plain, */*",
}

def parse_entry(entry):
    entry = entry.strip()
    low = entry.lower()

    # 🔥 FULL LINK SUPPORT - https://m.nimo.tv/live/12345678
    if "nimo.tv" in low:
        m = re.search(r"nimo\.tv/(?:live/)?(\d+)", low)
        if m:
            return "nimo", m.group(1)
        m2 = re.search(r"nimo\.tv/(?:live/)?([a-z0-9_\-]+)", low)
        if m2:
            return "nimo", m2.group(1)

    if "twitch.tv" in low:
        m = re.search(r"twitch\.tv/([a-z0-9_\-]+)", low)
        if m:
            return "twitch", m.group(1)

    if "kick.com" in low:
        m = re.search(r"kick\.com/([a-z0-9_\-]+)", low)
        if m:
            return "kick", m.group(1)

    entry = low.replace("@", "").strip()
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
            f"https://m.nimo.tv/live/{uid}",
            f"https://m.nimo.tv/{uid}",
            f"https://www.nimo.tv/live/{uid}",
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
        "🎬✨ 𝗬𝗢𝗢𝗡 ✨🎬\n"
        "🤖 Auto Recorder 💜\n"
        "\n"
        "👋 Heyy Welcome Baby 😍🔥\n"
        "\n"
        "🔴🎥 Auto Record Lives\n"
        "🎞️ 480p30 Clear Quality\n"
        "✂️ 10 Min Parts\n"
        "☁️ Mixdrop Backup\n"
        "\n"
        "🌐 Twitch 💜 | Kick 💚 | Nimo 💛\n"
        "\n"
        "💖 Yoon Got You Covered 🚀✨"
    )
    await update.message.reply_text(message)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage:\n"
            "/add https://m.nimo.tv/live/12345678\n"
            "/add nimo:12345678\n"
            "/add kick:username\n"
            "/add username"
        )
        return

    raw = " ".join(context.args).strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)

    if entry not in USERNAMES:
        USERNAMES.append(entry)
        save_usernames()
        await update.message.reply_text(
            f"✅ Added Successfully!\n\n"
            f"🎬 {display_name(entry)}\n"
            f"🔗 Link : {get_url(entry)}\n"
            f"🔴 Auto Record : ON\n"
            f"🎞️ Quality : 480p30"
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

    text += "\n🎞️ Quality : 480p30\n✂️ Parts : 10 Min Each"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No One Is Live Right Now.")
        return

    text = "🔴 ─── Currently Recording ─── 🔴\n\n"
    for user in RECORDING:
        text += f"🎥 {display_name(user)} — 480p30\n"

    await update.message.reply_text(text)

# ==================================================
# 🔥 NIMO API - m.nimo.tv
# ==================================================

def get_nimo_info(room_id):
    urls = [
        f"https://m.nimo.tv/api/v1/live/room?roomId={room_id}",
        f"https://m.nimo.tv/api/live/room?roomId={room_id}",
        f"https://m.nimo.tv/api/v1/room/detail?roomId={room_id}",
        f"https://m.nimo.tv/api/v1/live/detail?roomId={room_id}",
    ]
    for api_url in urls:
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                print(f"Nimo API Fail {r.status_code} : {api_url}")
                continue
            data = r.json()
            print(f"Nimo API : {api_url} -> {str(data)[:500]}")
            d = data.get("data", {})
            if not d:
                d = data
            room = d.get("room", d)
            stream_urls = extract_nimo_stream_urls(room, d)
            if stream_urls:
                return True, stream_urls
            status = room.get("liveStatus", room.get("status", room.get("isLive", 0)))
            if status in [1, "1", True, "live"]:
                return True, stream_urls
        except Exception as e:
            print(f"Nimo API Error {api_url} : {e}")
            continue
    return False, []

def extract_nimo_stream_urls(room, full_data):
    urls = []
    keys = [
        "liveStreamUrl", "streamUrl", "hlsUrl", "m3u8Url",
        "playUrl", "flvUrl", "rtmpUrl", "liveUrl",
        "streamUrls", "playUrls", "urls",
    ]
    for k in keys:
        v = room.get(k) or full_data.get(k)
        if isinstance(v, str) and v.startswith("http"):
            urls.append(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.startswith("http"):
                    urls.append(item)
                elif isinstance(item, dict):
                    for vv in item.values():
                        if isinstance(vv, str) and vv.startswith("http"):
                            urls.append(vv)
        elif isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, str) and vv.startswith("http"):
                    urls.append(vv)

    for key in ["streamInfo", "liveStream", "streams"]:
        obj = room.get(key) or full_data.get(key)
        if isinstance(obj, dict):
            for vv in obj.values():
                if isinstance(vv, str) and vv.startswith("http"):
                    urls.append(vv)
        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    for vv in item.values():
                        if isinstance(vv, str) and vv.startswith("http"):
                            urls.append(vv)

    m3u8 = [u for u in urls if ".m3u8" in u]
    flv = [u for u in urls if ".flv" in u]
    if m3u8:
        return m3u8
    if flv:
        return flv
    return urls

# ==================================================
# ☁️ HELPERS
# ==================================================

def upload_to_mixdrop(file_path):
    try:
        print(f"Mixdrop Upload Start : {file_path}")
        with open(file_path, "rb") as f:
            response = requests.post(
                "https://ul.mixdrop.ag/api",
                data={"email": MIXDROP_EMAIL, "key": MIXDROP_KEY},
                files={"file": f},
                timeout=3600
            ).json()
        print(f"Mixdrop Response : {response}")
        if response.get("success"):
            return response["result"]["url"]
    except Exception as e:
        print(f"Mixdrop Error : {e}")
    return None

def is_live(entry):
    platform, uid = parse_entry(entry)
    if platform == "nimo":
        live, _ = get_nimo_info(uid)
        print(f"Nimo is_live {uid} : {live}")
        return live

    for url in get_all_urls(entry):
        result = subprocess.run(
            ["streamlink", url, "480p30,480p,best", "--stream-url"],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip().startswith("http"):
            return True
        result2 = subprocess.run(
            ["yt-dlp", url, "--skip-download", "--quiet"],
            capture_output=True, timeout=30
        )
        if result2.returncode == 0:
            return True
    return False

def get_stream_url(entry):
    platform, uid = parse_entry(entry)
    if platform == "nimo":
        live, urls = get_nimo_info(uid)
        if urls:
            print(f"Nimo Stream URL Found : {urls[0][:120]}")
            return urls[0]
        for url in get_all_urls(entry):
            result = subprocess.run(
                ["streamlink", url, "480p30,480p,best", "--stream-url"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip().startswith("http"):
                return result.stdout.strip()
        return None

    for url in get_all_urls(entry):
        for quality in ["480p30", "480p", "best"]:
            result = subprocess.run(
                ["streamlink", url, quality, "--stream-url"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip().startswith("http"):
                return result.stdout.strip()
        result = subprocess.run(
            ["yt-dlp", url, "-f", "best[height<=480][fps<=30]", "-g"],
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
            f"🎞️ Quality : 480p30\n"
            f"🔗 Mixdrop Part {index} :\n{mixdrop_link}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"▶️ Part {index} — Watch Here ✨"
        )
    else:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📂 Part : {index}\n"
            f"🎞️ Quality : 480p30\n"
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
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))

    loop = asyncio.get_event_loop()
    threading.Thread(target=check_loop, args=(app, loop), daemon=True).start()
    print("Bot Running - VIDEO + CAPTION ONLY Mode...")
    app.run_polling()

if __name__ == "__main__":
    main()
