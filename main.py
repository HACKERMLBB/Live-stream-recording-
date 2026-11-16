import subprocess
import requests
import os
import time
import glob
import json
import threading
import asyncio
import re
import traceback
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
MIXDROP_KEY = os.getenv("MIXDROP_KEY")
MIXDROP_EMAIL = os.getenv("MIXDROP_EMAIL")
CHANNEL_ID = os.getenv("CHANNEL_ID")
USERNAMES_FILE = "usernames.json"

PLATFORMS = {
    "soop": "https://play.sooplive.com/{id}",
    "twitch": "https://twitch.tv/{id}",
    "kick": "https://kick.com/{id}",
    "nimo": "https://m.nimo.tv/live/{id}",
    "17live": "https://17.live/en/live/{id}",
    "17": "https://17.live/en/live/{id}",
    "chzzk": "https://chzzk.naver.com/live/{id}",
    "youtube": "https://youtube.com/{id}",
    "yt": "https://youtube.com/{id}",
    "tiktok": "https://tiktok.com/{id}",
    "bigo": "https://bigo.tv/{id}",
    "douyin": "https://live.douyin.com/{id}",
    "twitcasting": "https://twitcasting.tv/{id}",
    "nicolive": "https://live.nicovideo.jp/watch/{id}",
    "facebook": "https://facebook.com/{id}",
    "dailymotion": "https://dailymotion.com/{id}",
    "vimeo": "https://vimeo.com/{id}",
    "bilibili": "https://live.bilibili.com/{id}",
    "pixiv": "https://sketch.pixiv.net/lives/{id}",
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
HEADERS_SOOP = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://play.sooplive.com/",
    "Origin": "https://play.sooplive.com",
    "Accept": "application/json, text/plain, */*",
}

def parse_entry(entry):
    entry = entry.strip()
    low = entry.lower()

    if "sooplive" in low or "afreecatv" in low:
        m = re.search(r"play\.sooplive\.com/([a-z0-9_\-]+)(?:/\d+)?", low)
        if m:
            return "soop", m.group(1)
        m = re.search(r"sooplive\.(?:com|co\.kr)/([a-z0-9_\-]+)", low)
        if m and m.group(1) not in ["play", "live", "channel"]:
            return "soop", m.group(1)

    if "chzzk" in low:
        m = re.search(r"chzzk\.naver\.com/(?:live/)?([a-z0-9_\-]+)", low)
        if m:
            return "chzzk", m.group(1)

    if "17.live" in low or "17live" in low:
        m = re.search(r"17\.live/(?:en/)?(?:live/)?([a-z0-9_\-]+)", low)
        if m:
            return "17live", m.group(1)

    if "nimo.tv" in low:
        m = re.search(r"nimo\.tv/(?:live/)?(\d+)", low)
        if m:
            return "nimo", m.group(1)

    if "twitch.tv" in low:
        m = re.search(r"twitch\.tv/([a-z0-9_\-]+)", low)
        if m:
            return "twitch", m.group(1)

    if "kick.com" in low:
        m = re.search(r"kick\.com/([a-z0-9_\-]+)", low)
        if m:
            return "kick", m.group(1)

    if "youtube.com" in low or "youtu.be" in low:
        m = re.search(r"youtube\.com/(?:@|channel/|c/|user/)([a-z0-9_\-\.]+)", low)
        if m:
            return "youtube", "@" + m.group(1).lstrip("@")
        m = re.search(r"youtu\.be/([a-z0-9_\-]+)", low)
        if m:
            return "youtube", m.group(1)
        m = re.search(r"youtube\.com/live/([a-z0-9_\-]+)", low)
        if m:
            return "youtube", m.group(1)

    if "tiktok.com" in low:
        m = re.search(r"tiktok\.com/@([a-z0-9_\-\.]+)", low)
        if m:
            return "tiktok", "@" + m.group(1)
        m = re.search(r"tiktok\.com/([a-z0-9_\-\.]+)", low)
        if m:
            return "tiktok", "@" + m.group(1)

    if "bigo.tv" in low or "bigo" in low and "bigo:" in low:
        m = re.search(r"bigo\.tv/([a-z0-9_\-]+)", low)
        if m:
            return "bigo", m.group(1)

    if "douyin.com" in low:
        m = re.search(r"douyin\.com/([a-z0-9_\-]+)", low)
        if m:
            return "douyin", m.group(1)

    if "twitcasting.tv" in low:
        m = re.search(r"twitcasting\.tv/([a-z0-9_\-]+)", low)
        if m:
            return "twitcasting", m.group(1)

    if "nicovideo.jp" in low or "nicolive" in low:
        m = re.search(r"nicovideo\.jp/watch/([a-z0-9_\-]+)", low)
        if m:
            return "nicolive", m.group(1)

    if "facebook.com" in low or "fb.watch" in low:
        m = re.search(r"facebook\.com/([a-z0-9_\-\.]+)", low)
        if m and m.group(1) not in ["live", "watch"]:
            return "facebook", m.group(1)

    if "dailymotion.com" in low:
        m = re.search(r"dailymotion\.com/([a-z0-9_\-]+)", low)
        if m:
            return "dailymotion", m.group(1)

    if "vimeo.com" in low:
        m = re.search(r"vimeo\.com/([a-z0-9_\-]+)", low)
        if m:
            return "vimeo", m.group(1)

    if "bilibili.com" in low:
        m = re.search(r"bilibili\.com/(\d+)", low)
        if m:
            return "bilibili", m.group(1)

    entry_clean = low.replace("@", "").strip()
    if ":" in entry_clean:
        platform, uid = entry_clean.split(":", 1)
        platform = platform.strip()
        uid = uid.strip()
        if platform == "17":
            platform = "17live"
        if platform == "afreeca":
            platform = "soop"
        if platform == "yt":
            platform = "youtube"
        if platform not in PLATFORMS:
            platform = "soop"
        if platform in ["youtube", "tiktok"] and not uid.startswith("@"):
            uid = "@" + uid
        return platform, uid

    if entry_clean.startswith("youtube:") or entry_clean.startswith("tiktok:"):
        return entry_clean.split(":", 1)[0], "@" + entry_clean.split(":", 1)[1].lstrip("@")

    if re.match(r"^[a-z0-9_\-]+$", entry_clean) and "." not in entry_clean and "/" not in entry_clean:
        return "soop", entry_clean

    return "soop", entry_clean

def make_entry(platform, uid):
    if platform == "17":
        platform = "17live"
    if platform == "afreeca":
        platform = "soop"
    if platform == "yt":
        platform = "youtube"
    return f"{platform}:{uid}"

def get_url(entry):
    platform, uid = parse_entry(entry)
    return PLATFORMS[platform].format(id=uid)

def get_all_urls(entry):
    platform, uid = parse_entry(entry)
    if platform == "nimo":
        return [f"https://m.nimo.tv/live/{uid}", f"https://m.nimo.tv/{uid}"]
    if platform == "17live":
        return [f"https://17.live/en/live/{uid}", f"https://17.live/live/{uid}"]
    if platform == "soop":
        return [f"https://play.sooplive.com/{uid}", f"https://play.sooplive.com/{uid}/"]
    if platform == "chzzk":
        return [f"https://chzzk.naver.com/live/{uid}"]
    if platform == "youtube":
        return [f"https://youtube.com/{uid}/live", f"https://youtube.com/{uid}"]
    if platform == "tiktok":
        return [f"https://tiktok.com/{uid}/live", f"https://tiktok.com/{uid}"]
    if platform == "bigo":
        return [f"https://bigo.tv/{uid}", f"https://www.bigo.tv/{uid}"]
    if platform == "douyin":
        return [f"https://live.douyin.com/{uid}"]
    if platform == "twitcasting":
        return [f"https://twitcasting.tv/{uid}"]
    if platform == "nicolive":
        return [f"https://live.nicovideo.jp/watch/{uid}"]
    if platform == "facebook":
        return [f"https://facebook.com/{uid}/live", f"https://facebook.com/{uid}"]
    return [get_url(entry)]

def display_name(entry):
    platform, uid = parse_entry(entry)
    return f"@{uid.lstrip('@')} [{platform}]"

if os.path.exists(USERNAMES_FILE):
    try:
        USERNAMES = json.load(open(USERNAMES_FILE))
        migrated = []
        for u in USERNAMES:
            if ":" not in str(u):
                migrated.append(make_entry("soop", str(u)))
            else:
                migrated.append(str(u).lower().replace("17:", "17live:").replace("afreeca:", "soop:").replace("yt:", "youtube:"))
        USERNAMES = migrated
    except Exception:
        USERNAMES = []
else:
    USERNAMES = []

RECORDING = set()
def save_usernames():
    with open(USERNAMES_FILE, "w") as f:
        json.dump(USERNAMES, f)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨🎬 𝗬𝗢𝗢𝗡 🎬✨\n"
        "💜 Auto Recorder Bot\n\n"
        "🔴 Auto Record\n"
        "🎞️ 360p30\n"
        "✂️ 10 Min Parts\n"
        "☁️ Mixdrop\n\n"
        "👑 SOOP | ❤️ YouTube | 🖤 TikTok\n"
        "💜 Twitch | 💚 Kick | 💙 Bigo\n"
        "💛 Nimo | 💖 17Live | 💚 CHZZK\n"
        "🇨🇳 Douyin | 🎌 NicoLive\n\n"
        "👉 /add seoeun3104"
    )

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ 𝗨𝘀𝗮𝗴𝗲\n\n"
            "👑 SOOP:\n"
            "/add seoeun3104\n\n"
            "❤️ YouTube:\n"
            "/add youtube:@channel\n\n"
            "🖤 TikTok:\n"
            "/add tiktok:@username\n\n"
            "🌐 Others:\n"
            "/add twitch:username\n"
            "/add kick:username\n"
            "/add bigo:username\n"
            "/add douyin:username\n"
            "/add twitcasting:username\n"
            "/add nicolive:lv123456"
        )
        return
    raw = " ".join(context.args).strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)
    if entry not in USERNAMES:
        USERNAMES.append(entry)
        save_usernames()
        await update.message.reply_text(
            f"✅ 𝗔𝗱𝗱𝗲𝗱!\n\n"
            f"🎬 {display_name(entry)}\n"
            f"🔗 {get_url(entry)}\n"
            f"🔴 Recording: ON\n"
            f"🎞️ 360p30"
        )
    else:
        await update.message.reply_text(f"ℹ️ Already Added\n🎬 {display_name(entry)}")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /remove seoeun3104")
        return
    raw = " ".join(context.args).strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)
    if entry in USERNAMES:
        USERNAMES.remove(entry)
        save_usernames()
        await update.message.reply_text(f"🗑️ Removed\n🎬 {display_name(entry)}")
    else:
        await update.message.reply_text(f"❌ Not Found\n🎬 {display_name(entry)}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not USERNAMES:
        await update.message.reply_text("📭 Empty\n👉 /add seoeun3104")
        return
    text = "👀 𝗪𝗮𝘁𝗰𝗵𝗶𝗻𝗴\n\n"
    for user in USERNAMES:
        status = "🔴 REC" if user in RECORDING else "⏳ Waiting"
        text += f"🎬 {display_name(user)}  {status}\n"
    text += "\n🎞️ 360p30 | ✂️ 10 Min"
    await update.message.reply_text(text)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No Live Now")
        return
    text = "🔴 𝗥𝗲𝗰𝗼𝗿𝗱𝗶𝗻𝗴\n\n"
    for user in RECORDING:
        text += f"🎥 {display_name(user)}\n"
    await update.message.reply_text(text)

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧪 Testing...")
    try:
        await context.bot.send_message(CHANNEL_ID, "🧪 Test OK ✅")
        await update.message.reply_text("✅ Channel OK")
    except Exception as e:
        await update.message.reply_text(f"❌ Channel Failed\n{e}")
    if not MIXDROP_EMAIL or not MIXDROP_KEY:
        await update.message.reply_text("❌ Mixdrop Missing")
    else:
        await update.message.reply_text("✅ Mixdrop OK")

def get_nimo_info(room_id):
    urls = [f"https://m.nimo.tv/api/v1/live/room?roomId={room_id}"]
    for api_url in urls:
        try:
            r = requests.get(api_url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            d = data.get("data", {})
            if not d:
                d = data
            room = d.get("room", d)
            for k in ["liveStreamUrl", "streamUrl", "hlsUrl", "m3u8Url", "playUrl"]:
                v = room.get(k) or d.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    return True, [v]
            if room.get("liveStatus") in [1, "1", True, "live"]:
                return True, []
        except Exception as e:
            print(f"Nimo Error: {e}")
            continue
    return False, []

def get_17live_info(uid):
    urls = [f"https://wap-api.17app.co/api/v1/liveStreams/getLiveStreamInfo?liveStreamID={uid}"]
    for api_url in urls:
        try:
            r = requests.get(api_url, headers=HEADERS_17, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            d = data.get("data", data)
            if not isinstance(d, dict):
                continue
            found = []
            def scan(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if isinstance(v, str) and v.startswith("http") and (".m3u8" in v or ".flv" in v):
                            found.append(v)
                        else:
                            scan(v)
                elif isinstance(obj, list):
                    for it in obj:
                        scan(it)
            scan(d)
            if found:
                return True, found
            if d.get("isLive") in [1, True, "1"]:
                return True, []
        except Exception as e:
            print(f"17Live Error: {e}")
            continue
    return False, []

def get_soop_info(uid):
    try:
        r = requests.get(f"https://bjapi.afreecatv.com/api/{uid}/station", headers=HEADERS_SOOP, timeout=15)
        print(f"SOOP API {uid}: {r.status_code} {r.text[:300]}", flush=True)
        if r.status_code == 200:
            data = r.json()
            if data.get("broad_start") or data.get("is_live"):
                return True
    except Exception as e:
        print(f"SOOP API Error: {e}", flush=True)
    return False

def upload_to_mixdrop(file_path):
    try:
        print(f"Mixdrop Upload Start : {file_path} Size: {os.path.getsize(file_path)/1024/1024:.1f} MB", flush=True)
        if not MIXDROP_EMAIL or not MIXDROP_KEY:
            print("Mixdrop Config Missing!", flush=True)
            return None
        with open(file_path, "rb") as f:
            response = requests.post("https://ul.mixdrop.ag/api", data={"email": MIXDROP_EMAIL, "key": MIXDROP_KEY}, files={"file": f}, timeout=3600).json()
        print(f"Mixdrop Response : {response}", flush=True)
        if response.get("success"):
            return response["result"]["url"]
    except Exception as e:
        print(f"Mixdrop Error : {e}\n{traceback.format_exc()}", flush=True)
    return None

def is_live(entry):
    platform, uid = parse_entry(entry)
    print(f"Checking is_live: {entry}", flush=True)
    if platform == "nimo":
        live, _ = get_nimo_info(uid)
        return live
    if platform == "17live":
        live, urls = get_17live_info(uid)
        if live:
            return True
    if platform == "soop":
        if get_soop_info(uid):
            return True
    for url in get_all_urls(entry):
        try:
            result = subprocess.run(["streamlink", url, "360p30,360p,best", "--stream-url"], capture_output=True, text=True, timeout=30)
            print(f"streamlink {url}: {result.stdout[:100]}", flush=True)
            if result.stdout.strip().startswith("http"):
                return True
        except Exception as e:
            print(f"streamlink error: {e}", flush=True)
        try:
            result2 = subprocess.run(["yt-dlp", url, "--skip-download", "--quiet"], capture_output=True, timeout=30)
            if result2.returncode == 0:
                return True
        except Exception as e:
            print(f"yt-dlp check error: {e}", flush=True)
    return False

def get_stream_url(entry):
    platform, uid = parse_entry(entry)
    if platform == "nimo":
        live, urls = get_nimo_info(uid)
        if urls:
            return urls[0]
    if platform == "17live":
        live, urls = get_17live_info(uid)
        if urls:
            return urls[0]
    for url in get_all_urls(entry):
        for quality in ["360p30", "360p", "best"]:
            try:
                result = subprocess.run(["streamlink", url, quality, "--stream-url"], capture_output=True, text=True, timeout=30)
                if result.stdout.strip().startswith("http"):
                    print(f"Stream URL via streamlink {quality}: {result.stdout.strip()[:120]}", flush=True)
                    return result.stdout.strip()
            except Exception as e:
                print(f"streamlink get_url error: {e}", flush=True)
        try:
            result = subprocess.run(["yt-dlp", url, "-f", "best[height<=360][fps<=30]/best[height<=360]/best", "-g"], capture_output=True, text=True, timeout=30)
            stream_url = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
            if stream_url.startswith("http"):
                return stream_url
        except Exception as e:
            print(f"yt-dlp get_url error: {e}", flush=True)
    print(f"NO Stream URL for {entry}", flush=True)
    return None

async def upload_one_part(entry, part_path, index, app):
    size_mb = 0
    try:
        size_mb = os.path.getsize(part_path) / 1024 / 1024
    except:
        pass
    print(f"Uploading Part {index} : {part_path} Size: {size_mb:.1f} MB", flush=True)
    mixdrop_link = None
    try:
        mixdrop_link = upload_to_mixdrop(part_path)
    except Exception as e:
        print(f"Mixdrop outer error: {e}", flush=True)
    if mixdrop_link:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━\n"
            f"📂 Part {index}\n"
            f"🎞️ 360p30 | 📦 {size_mb:.1f} MB\n"
            f"🔗 Mixdrop:\n{mixdrop_link}\n"
            f"━━━━━━━━━━━━\n"
            f"▶️ Part {index} ✨"
        )
    else:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━\n"
            f"📂 Part {index}\n"
            f"🎞️ 360p30 | 📦 {size_mb:.1f} MB\n"
            f"❌ Mixdrop Failed\n"
            f"━━━━━━━━━━━━\n"
            f"▶️ Part {index} ✨"
        )
    sent = False
    if size_mb < 48:
        try:
            with open(part_path, "rb") as video:
                await app.bot.send_video(CHANNEL_ID, video=video, caption=caption, supports_streaming=True)
            sent = True
        except Exception as e:
            print(f"send_video failed Part {index}: {e}", flush=True)
            sent = False
    if not sent:
        try:
            with open(part_path, "rb") as doc:
                await app.bot.send_document(CHANNEL_ID, document=doc, caption=caption, filename=os.path.basename(part_path))
            sent = True
        except Exception as e:
            print(f"send_document failed Part {index}: {e}", flush=True)
            sent = False
    if not sent:
        try:
            await app.bot.send_message(CHANNEL_ID, caption + f"\n\n⚠️ Upload Failed ({size_mb:.1f} MB)")
        except Exception as e:
            print(f"send_message fallback failed: {e}", flush=True)
    try:
        os.remove(part_path)
    except:
        pass

def is_file_ready(part_path):
    try:
        if not os.path.exists(part_path):
            return False
        if os.path.getsize(part_path) < 1000:
            return False
        if time.time() - os.path.getmtime(part_path) < 5:
            return False
        size1 = os.path.getsize(part_path)
        time.sleep(2)
        if not os.path.exists(part_path):
            return False
        return size1 == os.path.getsize(part_path)
    except:
        return False

async def process_stream(entry, app):
    platform, uid = parse_entry(entry)
    base_name = f"{platform}_{uid.lstrip('@')}_{int(time.time())}"
    print(f"LIVE Detected : {entry} -> Starting Record", flush=True)
    try:
        await app.bot.send_message(CHANNEL_ID,
            f"🔴 𝗟𝗜𝗩𝗘 𝗦𝘁𝗮𝗿𝘁𝗲𝗱!\n\n"
            f"🎬 {display_name(entry)}\n"
            f"🔗 {get_url(entry)}\n"
            f"🎞️ 360p30 | ⏳ Part 1 Soon..."
        )
    except Exception as e:
        print(f"Start notify failed: {e}", flush=True)
    try:
        stream_url = get_stream_url(entry)
        if not stream_url:
            print(f"Recording Failed - No Stream URL : {entry}", flush=True)
            try:
                await app.bot.send_message(CHANNEL_ID, f"❌ Record Failed\n🎬 {display_name(entry)}")
            except:
                pass
            RECORDING.discard(entry)
            return
        pattern = f"{base_name}_part%03d.mp4"
        log_file = open(f"{base_name}_ffmpeg.log", "w")
        ffmpeg_proc = subprocess.Popen(["ffmpeg", "-y", "-i", stream_url, "-c", "copy", "-f", "segment", "-segment_time", "600", "-segment_format", "mp4", "-reset_timestamps", "1", "-break_non_keyframes", "1", pattern], stdout=log_file, stderr=log_file)
        uploaded = 0
        uploaded_files = set()
        while ffmpeg_proc.poll() is None:
            await asyncio.sleep(20)
            parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
            for part_path in parts:
                if part_path in uploaded_files:
                    continue
                if is_file_ready(part_path):
                    uploaded += 1
                    uploaded_files.add(part_path)
                    try:
                        await upload_one_part(entry, part_path, uploaded, app)
                    except Exception as e:
                        print(f"upload crash: {e}\n{traceback.format_exc()}", flush=True)
        print(f"ffmpeg exited {ffmpeg_proc.poll()} for {entry}", flush=True)
        try:
            log_file.close()
        except:
            pass
        await asyncio.sleep(3)
        parts = sorted(glob.glob(f"{base_name}_part*.mp4"))
        for part_path in parts:
            if part_path in uploaded_files:
                continue
            if os.path.exists(part_path) and os.path.getsize(part_path) > 1000:
                uploaded += 1
                uploaded_files.add(part_path)
                try:
                    await upload_one_part(entry, part_path, uploaded, app)
                except Exception as e:
                    print(f"Final upload crash: {e}", flush=True)
        try:
            await app.bot.send_message(CHANNEL_ID,
                f"✅ 𝗟𝗶𝘃𝗲 𝗙𝗶𝗻𝗶𝘀𝗵𝗲𝗱!\n\n"
                f"🎬 {display_name(entry)}\n"
                f"📂 Total Parts: {uploaded}"
            )
        except:
            pass
    except Exception as e:
        print(f"process_stream CRASH {entry}: {e}\n{traceback.format_exc()}", flush=True)
    finally:
        RECORDING.discard(entry)

def check_loop(app, loop):
    while True:
        try:
            for username in list(USERNAMES):
                if username not in RECORDING and is_live(username):
                    RECORDING.add(username)
                    asyncio.run_coroutine_threadsafe(process_stream(username, app), loop)
        except Exception as e:
            print(f"check_loop error: {e}", flush=True)
        time.sleep(60)

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN missing!")
        return
    print(f"Config - CHANNEL_ID: {CHANNEL_ID} | Mixdrop: {bool(MIXDROP_EMAIL)} | Watching: {USERNAMES}", flush=True)
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(read_timeout=600, write_timeout=600, connect_timeout=60, pool_timeout=600)
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("test", test_command))
    loop = asyncio.get_event_loop()
    threading.Thread(target=check_loop, args=(app, loop), daemon=True).start()
    print("Bot Running...", flush=True)
    app.run_polling()

if __name__ == "__main__":
    main()
