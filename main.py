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
# 🌐 PLATFORMS - Twitch / Kick / Nimo / 17Live
# ==================================================
PLATFORMS = {
    "twitch": "https://twitch.tv/{id}",
    "kick": "https://kick.com/{id}",
    "nimo": "https://m.nimo.tv/live/{id}",
    "17live": "https://17.live/en/live/{id}",
    "17": "https://17.live/en/live/{id}",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Referer": "https://m.nimo.tv/",
    "Origin": "https://m.nimo.tv",
    "Accept": "application/json, text/plain, */*",
}

HEADERS_17 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://17.live/",
    "Origin": "https://17.live",
    "Accept": "application/json, text/plain, */*",
}

def parse_entry(entry):
    entry = entry.strip()
    low = entry.lower()

    # 🔥 17LIVE FULL LINK - https://17.live/en/live/123456 / https://17.live/live/123456
    if "17.live" in low or "17live" in low:
        m = re.search(r"17\.live/(?:en/)?(?:live/)?([a-z0-9_\-]+)", low)
        if m:
            return "17live", m.group(1)
        m = re.search(r"17live[: ]+([a-z0-9_\-]+)", low)
        if m:
            return "17live", m.group(1)

    # 🔥 NIMO FULL LINK - https://m.nimo.tv/live/12345678
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
        # 17 -> 17live normalize
        if platform == "17":
            platform = "17live"
        if platform not in PLATFORMS:
            platform = "twitch"
    else:
        platform = "twitch"
        uid = entry
    return platform, uid

def make_entry(platform, uid):
    if platform == "17":
        platform = "17live"
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
    if platform == "17live":
        return [
            f"https://17.live/en/live/{uid}",
            f"https://17.live/live/{uid}",
            f"https://17.live/en/streams/{uid}",
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
                migrated.append(str(u).lower().replace("17:", "17live:"))
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
        "🎞️ 360p30 Clear Quality\n"
        "✂️ 10 Min Parts\n"
        "☁️ Mixdrop Backup\n"
        "\n"
        "🌐 Twitch 💜 | Kick 💚 | Nimo 💛 | 17Live 💖\n"
        "\n"
        "💖 Yoon Got You Covered 🚀✨"
    )
    await update.message.reply_text(message)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage:\n"
            "/add https://m.nimo.tv/live/12345678\n"
            "/add https://17.live/en/live/123456\n"
            "/add nimo:12345678\n"
            "/add 17live:username\n"
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
            f"🎞️ Quality : 360p30"
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

    text += "\n🎞️ Quality : 360p30\n✂️ Parts : 10 Min Each"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No One Is Live Right Now.")
        return

    text = "🔴 ─── Currently Recording ─── 🔴\n\n"
    for user in RECORDING:
        text += f"🎥 {display_name(user)} — 360p30\n"

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
# 🔥 17LIVE API
# ==================================================

def get_17live_info(uid):
    # 17Live - Try API + yt-dlp / streamlink fallback in get_stream_url
    urls = [
        f"https://wap-api.17app.co/api/v1/liveStreams/getLiveStreamInfo?liveStreamID={uid}",
        f"https://api.17.live/api/v1/liveStreams/getLiveStreamInfo?liveStreamID={uid}",
        f"https://wap-api.17app.co/api/v1/lives/{uid}",
        f"https://api.17.live/api/v1/users/{uid}/liveStream",
    ]
    for api_url in urls:
        try:
            r = requests.get(api_url, headers=HEADERS_17, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            print(f"17Live API : {api_url} -> {str(data)[:500]}")
            d = data.get("data", data)
            if not isinstance(d, dict):
                continue
            # Look for stream urls inside
            found = []
            def scan(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and v.startswith("http") and (".m3u8" in v or ".flv" in v or ".mp4" in v):
                            found.append(v)
                        else:
                            scan(v)
                elif isinstance(obj, list):
                    for it in obj:
                        scan(it)
            scan(d)
            if found:
                # Prefer m3u8
                m3u8 = [u for u in found if ".m3u8" in u]
                return True, m3u8 if m3u8 else found
            # isLive check
            if d.get("isLive") in [1, True, "1"] or d.get("liveStatus") in [1, True]:
                return True, []
        except Exception as e:
            print(f"17Live API Error {api_url} : {e}")
            continue
    return False, []

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
    if platform == "17live":
        live, urls = get_17live_info(uid)
        if live:
            return True
        # Fallback to streamlink / yt-dlp - 17Live works with these too
        for url in get_all_urls(entry):
            r = subprocess.run(["streamlink", url, "360p30,360p,best", "--stream-url"], capture_output=True, text=True, timeout=30)
            if r.stdout.strip().startswith("http"):
                return True
            r2 = subprocess.run(["yt-dlp", url, "--skip-download", "--quiet"], capture_output=True, timeout=30)
            if r2.returncode == 0:
                return True
        return False

    for url in get_all_urls(entry):
        result = subprocess.run(
            ["streamlink", url, "360p30,360p,best", "--stream-url"],
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
                ["streamlink", url, "360p30,360p,best", "--stream-url"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip().startswith("http"):
                return result.stdout.strip()
        return None

    if platform == "17live":
        live, urls = get_17live_info(uid)
        if urls:
            print(f"17Live Stream URL Found : {urls[0][:120]}")
            return urls[0]

    for url in get_all_urls(entry):
        for quality in ["360p30", "360p", "best"]:
            result = subprocess.run(
                ["streamlink", url, quality, "--stream-url"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout.strip().startswith("http"):
                return result.stdout.strip()
        result = subprocess.run(
            ["yt-dlp", url, "-f", "best[height<=360][fps<=30]/best[height<=360]/best", "-g"],
            capture_output=True, text=True, timeout=30
        )
        stream_url = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        if stream_url.startswith("http"):
            return stream_url
    return None

# ==================================================
# 🎬 VIDEO + CAPTION ONLY - PART FIX
# ==================================================

async def upload_one_part(entry, part_path, index, app):
    mixdrop_link = upload_to_mixdrop(part_path)

    if mixdrop_link:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📂 Part : {index}\n"
            f"🎞️ Quality : 360p30\n"
            f"🔗 Mixdrop Part {index} :\n{mixdrop_link}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"▶️ Part {index} — Watch Here ✨"
        )
    else:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📂 Part : {index}\n"
            f"🎞️ Quality : 360p30\n"
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

def is_file_ready(part_path):
    # File is ready if size stable for 3 sec AND not modified in last 5 sec
    try:
        if not os.path.exists(part_path):
            return False
        if os.path.getsize(part_path) < 1000:
            return False
        mtime = os.path.getmtime(part_path)
        if time.time() - mtime < 5:
            return False
        size1 = os.path.getsize(part_path)
        time.sleep(2)
        if not os.path.exists(part_path):
            return False
        size2 = os.path.getsize(part_path)
        return size1 == size2
    except Exception:
        return False

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

    # 🔥 FIX : break_non_keyframes + segment_time works even with -c copy
    ffmpeg_proc = subprocess.Popen([
        "ffmpeg", "-y", "-i", stream_url,
        "-c", "copy",
        "-f", "segment",
        "-segment_time", "600",
        "-segment_format", "mp4",
        "-reset_timestamps", "1",
        "-break_non_keyframes", "1",
        pattern
    ], stdout=log_file, stderr=log_file)

    uploaded = 0
    uploaded_files = set()

    # 🔥 While recording - upload any READY file, not just parts[:-1]
    while ffmpeg_proc.poll() is None:
        await asyncio.sleep(20)
        parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
        for part_path in parts:
            if part_path in uploaded_files:
                continue
            # If ffmpeg still running, skip the newest file ONLY if it is still growing
            # Old files will be ready even if they are last in list
            if is_file_ready(part_path):
                uploaded += 1
                uploaded_files.add(part_path)
                await upload_one_part(entry, part_path, uploaded, app)

    print(f"ffmpeg exited {ffmpeg_proc.poll()} for {entry}")
    try:
        log_file.close()
    except Exception:
        pass

    await asyncio.sleep(3)
    # 🔥 After end - upload ALL remaining parts in order
    parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
    for part_path in parts:
        if part_path in uploaded_files:
            continue
        if os.path.exists(part_path) and os.path.getsize(part_path) > 1000:
            uploaded += 1
            uploaded_files.add(part_path)
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
