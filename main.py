import asyncio
import glob
import json
import os
import re
import subprocess
import time
import traceback

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
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

USERNAMES = []
RECORDING = set()


def normalize_platform(platform: str) -> str:
    alias_map = {
        "17": "17live",
        "afreeca": "soop",
        "yt": "youtube",
    }
    platform = (platform or "").strip().lower()
    return alias_map.get(platform, platform)


def parse_entry(entry: str):
    entry = str(entry).strip()
    low = entry.lower()

    if "sooplive" in low or "afreecatv" in low:
        match = re.search(r"play\.sooplive\.com/([a-z0-9_-]+)(?:/\d+)?", low)
        if match:
            return "soop", match.group(1)
        match = re.search(r"sooplive\.(?:com|co\.kr)/([a-z0-9_-]+)", low)
        if match and match.group(1) not in {"play", "live", "channel"}:
            return "soop", match.group(1)

    if "chzzk" in low:
        match = re.search(r"chzzk\.naver\.com/(?:live/)?([a-z0-9_-]+)", low)
        if match:
            return "chzzk", match.group(1)

    if "17.live" in low or "17live" in low:
        match = re.search(r"17\.live/(?:en/)?(?:live/)?([a-z0-9_-]+)", low)
        if match:
            return "17live", match.group(1)

    if "nimo.tv" in low:
        match = re.search(r"nimo\.tv/(?:live/)?(\d+)", low)
        if match:
            return "nimo", match.group(1)

    if "twitch.tv" in low:
        match = re.search(r"twitch\.tv/([a-z0-9_-]+)", low)
        if match:
            return "twitch", match.group(1)

    if "kick.com" in low:
        match = re.search(r"kick\.com/([a-z0-9_-]+)", low)
        if match:
            return "kick", match.group(1)

    if "youtube.com" in low or "youtu.be" in low:
        match = re.search(r"youtube\.com/(?:@|channel/|c/|user/)([a-z0-9_.-]+)", low)
        if match:
            return "youtube", "@" + match.group(1).lstrip("@")
        match = re.search(r"youtu\.be/([a-z0-9_-]+)", low)
        if match:
            return "youtube", match.group(1)
        match = re.search(r"youtube\.com/live/([a-z0-9_-]+)", low)
        if match:
            return "youtube", match.group(1)

    if "tiktok.com" in low:
        match = re.search(r"tiktok\.com/@?([a-z0-9_.-]+)", low)
        if match:
            return "tiktok", "@" + match.group(1).lstrip("@")

    if "bigo.tv" in low:
        match = re.search(r"bigo\.tv/([a-z0-9_-]+)", low)
        if match:
            return "bigo", match.group(1)

    if "douyin.com" in low:
        match = re.search(r"douyin\.com/([a-z0-9_-]+)", low)
        if match:
            return "douyin", match.group(1)

    if "twitcasting.tv" in low:
        match = re.search(r"twitcasting\.tv/([a-z0-9_-]+)", low)
        if match:
            return "twitcasting", match.group(1)

    if "nicovideo.jp" in low:
        match = re.search(r"nicovideo\.jp/watch/([a-z0-9_-]+)", low)
        if match:
            return "nicolive", match.group(1)

    if "facebook.com" in low:
        match = re.search(r"facebook\.com/([a-z0-9_.-]+)", low)
        if match and match.group(1) not in {"live", "watch"}:
            return "facebook", match.group(1)

    if "dailymotion.com" in low:
        match = re.search(r"dailymotion\.com/([a-z0-9_-]+)", low)
        if match:
            return "dailymotion", match.group(1)

    if "vimeo.com" in low:
        match = re.search(r"vimeo\.com/([a-z0-9_-]+)", low)
        if match:
            return "vimeo", match.group(1)

    if "bilibili.com" in low:
        match = re.search(r"bilibili\.com/(\d+)", low)
        if match:
            return "bilibili", match.group(1)

    if ":" in entry:
        platform, uid = entry.split(":", 1)
        platform = normalize_platform(platform)
        uid = uid.strip()
        if platform not in PLATFORMS:
            platform = "soop"
        if platform in {"youtube", "tiktok"} and not uid.startswith("@"):
            uid = "@" + uid
        return platform, uid

    return "soop", entry.lstrip("@").strip()


def make_entry(platform: str, uid: str) -> str:
    platform = normalize_platform(platform)
    uid = str(uid).strip()
    if platform not in PLATFORMS:
        platform = "soop"
    if platform in {"youtube", "tiktok"} and not uid.startswith("@"):
        uid = "@" + uid
    return f"{platform}:{uid}"


def get_url(entry: str) -> str:
    platform, uid = parse_entry(entry)
    return PLATFORMS[platform].format(id=uid)


def get_all_urls(entry: str):
    platform, uid = parse_entry(entry)

    urls = {
        "nimo": [f"https://m.nimo.tv/live/{uid}", f"https://m.nimo.tv/{uid}"],
        "17live": [f"https://17.live/en/live/{uid}", f"https://17.live/live/{uid}"],
        "soop": [f"https://play.sooplive.com/{uid}", f"https://play.sooplive.com/{uid}/"],
        "chzzk": [f"https://chzzk.naver.com/live/{uid}"],
        "youtube": [f"https://youtube.com/{uid}/live", f"https://youtube.com/{uid}"],
        "tiktok": [f"https://tiktok.com/{uid}/live", f"https://tiktok.com/{uid}"],
        "bigo": [f"https://bigo.tv/{uid}", f"https://www.bigo.tv/{uid}"],
        "douyin": [f"https://live.douyin.com/{uid}"],
        "twitcasting": [f"https://twitcasting.tv/{uid}"],
        "nicolive": [f"https://live.nicovideo.jp/watch/{uid}"],
        "facebook": [f"https://facebook.com/{uid}/live", f"https://facebook.com/{uid}"],
    }

    return urls.get(platform, [get_url(entry)])


def display_name(entry: str) -> str:
    platform, uid = parse_entry(entry)
    return f"@{uid.lstrip('@')} [{platform}]"


def load_usernames():
    try:
        with open(USERNAMES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    except Exception as exc:
        print(f"Could not load usernames file: {exc}", flush=True)
        return []

    if not isinstance(data, list):
        return []

    parsed = []
    for item in data:
        platform, uid = parse_entry(str(item))
        entry = make_entry(platform, uid)
        if entry not in parsed:
            parsed.append(entry)
    return parsed


def save_usernames():
    temp_file = f"{USERNAMES_FILE}.tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(USERNAMES, file, ensure_ascii=False, indent=2)
        os.replace(temp_file, USERNAMES_FILE)
    except Exception as exc:
        print(f"Could not save usernames: {exc}", flush=True)


USERNAMES = load_usernames()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✨🎬 YOON 🎬✨\n"
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
            "⚠️ Usage:\n\n"
            "SOOP: /add seoeun3104\n"
            "YouTube: /add youtube:@channel\n"
            "TikTok: /add tiktok:@username\n"
            "Twitch: /add twitch:username\n"
            "Kick: /add kick:username\n"
            "Bigo: /add bigo:username\n"
            "NicoLive: /add nicolive:lv123456"
        )
        return

    raw = " ".join(context.args).strip()
    platform, uid = parse_entry(raw)
    entry = make_entry(platform, uid)

    if entry in USERNAMES:
        await update.message.reply_text(f"ℹ️ Already added:\n🎬 {display_name(entry)}")
        return

    USERNAMES.append(entry)
    save_usernames()

    await update.message.reply_text(
        f"✅ Added!\n\n"
        f"🎬 {display_name(entry)}\n"
        f"🔗 {get_url(entry)}\n"
        f"🔴 Recording: ON\n"
        f"🎞️ 360p30"
    )


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
        await update.message.reply_text(f"🗑️ Removed:\n🎬 {display_name(entry)}")
    else:
        await update.message.reply_text(f"❌ Not found:\n🎬 {display_name(entry)}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not USERNAMES:
        await update.message.reply_text("📭 Empty list.\n👉 /add seoeun3104")
        return

    text = "👀 Watching:\n\n"
    for user in USERNAMES:
        status = "🔴 REC" if user in RECORDING else "⏳ Waiting"
        text += f"🎬 {display_name(user)}  {status}\n"
    text += "\n🎞️ 360p30 | ✂️ 10 Min"
    await update.message.reply_text(text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not RECORDING:
        await update.message.reply_text("😴 No live streams are currently recording.")
        return

    text = "🔴 Recording:\n\n"
    for user in sorted(RECORDING):
        text += f"🎥 {display_name(user)}\n"
    await update.message.reply_text(text)


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧪 Testing...")
    if not MIXDROP_EMAIL or not MIXDROP_KEY:
        await update.message.reply_text("❌ Mixdrop config missing")
    else:
        await update.message.reply_text("✅ Mixdrop config present")

    if not CHANNEL_ID:
        await update.message.reply_text("❌ Channel ID missing")
    else:
        await update.message.reply_text("✅ Channel ID present")


def run_command(args, timeout=30):
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"Command error ({args[0]}): {exc}", flush=True)
        return None


def get_nimo_info(room_id: str):
    api_url = f"https://m.nimo.tv/api/v1/live/room?roomId={room_id}"
    try:
        response = requests.get(api_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return False, []

        data = response.json()
        details = data.get("data") or data
        room = details.get("room") or details

        for key in ("liveStreamUrl", "streamUrl", "hlsUrl", "m3u8Url", "playUrl"):
            value = room.get(key) or details.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return True, [value]

        live_status = room.get("liveStatus")
        return live_status in (1, "1", True, "live"), []

    except Exception as exc:
        print(f"Nimo check error: {exc}", flush=True)
        return False, []


def get_17live_info(uid: str):
    api_url = f"https://wap-api.17app.co/api/v1/liveStreams/getLiveStreamInfo?liveStreamID={uid}"
    try:
        response = requests.get(api_url, headers=HEADERS_17, timeout=15)
        if response.status_code != 200:
            return False, []

        data = response.json()
        details = data.get("data", data)
        if not isinstance(details, dict):
            return False, []

        found = []

        def scan(obj):
            if isinstance(obj, dict):
                for value in obj.values():
                    if isinstance(value, str) and value.startswith("http") and (".m3u8" in value or ".flv" in value):
                        found.append(value)
                    else:
                        scan(value)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)

        scan(details)
        if found:
            return True, found

        return details.get("isLive") in (1, True, "1"), []

    except Exception as exc:
        print(f"17Live check error: {exc}", flush=True)
        return False, []


def get_soop_info(uid: str) -> bool:
    try:
        response = requests.get(f"https://bjapi.afreecatv.com/api/{uid}/station", headers=HEADERS_SOOP, timeout=15)
        if response.status_code == 200:
            data = response.json()
            return bool(data.get("broad_start") or data.get("is_live"))
    except Exception as exc:
        print(f"SOOP check error: {exc}", flush=True)
    return False


def get_bigo_live_url(url: str):
    result = run_command(["streamlink", url, "best", "--stream-url"], timeout=45)
    if result and result.returncode == 0:
        stream_url = result.stdout.strip()
        if stream_url.startswith("http"):
            return stream_url
    return None


def upload_to_mixdrop(file_path: str):
    if not MIXDROP_EMAIL or not MIXDROP_KEY:
        print("Mixdrop config missing.", flush=True)
        return None

    try:
        file_size_mb = os.path.getsize(file_path) / 1024 / 1024
        print(f"Mixdrop upload start: {file_path} ({file_size_mb:.1f} MB)", flush=True)

        with open(file_path, "rb") as file:
            encoder = MultipartEncoder(
                fields={
                    "email": MIXDROP_EMAIL,
                    "key": MIXDROP_KEY,
                    "file": (
                        os.path.basename(file_path),
                        file,
                        "application/octet-stream",
                    ),
                }
            )

            response = requests.post(
                "https://ul.mixdrop.ag/api",
                data=encoder,
                headers={"Content-Type": encoder.content_type},
                timeout=(30, 3600),
            )
            response.raise_for_status()
            data = response.json()

        print(f"Mixdrop response: {data}", flush=True)

        if data.get("success"):
            result = data.get("result", {})
            return result.get("url")

    except Exception as exc:
        print(f"Mixdrop upload error: {exc}\n{traceback.format_exc()}", flush=True)

    return None


def is_live(entry: str) -> bool:
    platform, uid = parse_entry(entry)
    print(f"Checking live status: {entry}", flush=True)

    if platform == "bigo":
        for url in get_all_urls(entry):
            stream_url = get_bigo_live_url(url)
            if stream_url:
                return True
        return False

    if platform == "nimo":
        live, _ = get_nimo_info(uid)
        return live

    if platform == "17live":
        live, _ = get_17live_info(uid)
        if live:
            return True

    if platform == "soop" and get_soop_info(uid):
        return True

    for url in get_all_urls(entry):
        result = run_command(["streamlink", url, "360p30,360p,best", "--stream-url"], timeout=30)
        if result and result.stdout.strip().startswith("http"):
            return True

        result = run_command(["yt-dlp", url, "--skip-download", "--quiet"], timeout=30)
        if result and result.returncode == 0:
            return True

    return False


def get_stream_url(entry: str):
    platform, _ = parse_entry(entry)

    if platform == "bigo":
        for url in get_all_urls(entry):
            stream_url = get_bigo_live_url(url)
            if stream_url:
                return stream_url
        return None

    for url in get_all_urls(entry):
        for quality in ("360p30", "360p", "best"):
            result = run_command(["streamlink", url, quality, "--stream-url"], timeout=30)
            if result and result.stdout.strip().startswith("http"):
                return result.stdout.strip()

        result = run_command(
            ["yt-dlp", url, "-f", "best[height<=360][fps<=30]/best[height<=360]/best", "-g"],
            timeout=30,
        )
        if result and result.returncode == 0:
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if lines and lines[0].startswith("http"):
                return lines[0]

    print(f"No stream URL found for {entry}", flush=True)
    return None


def is_file_ready(path: str) -> bool:
    try:
        if not os.path.isfile(path):
            return False

        initial_size = os.path.getsize(path)
        if initial_size < 1000:
            return False

        if time.time() - os.path.getmtime(path) < 5:
            return False

        time.sleep(2)

        if not os.path.isfile(path):
            return False

        return initial_size == os.path.getsize(path)

    except Exception:
        return False


async def upload_one_part(entry: str, part_path: str, index: int, app):
    try:
        size_mb = os.path.getsize(part_path) / 1024 / 1024
    except OSError:
        return False

    print(f"Uploading part {index}: {part_path} ({size_mb:.1f} MB)", flush=True)

    mixdrop_link = await asyncio.to_thread(upload_to_mixdrop, part_path)

    if mixdrop_link:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━\n"
            f"📂 Part {index}\n"
            f"🎞️ 360p30 | 📦 {size_mb:.1f} MB\n"
            f"🔗 Mixdrop:\n{mixdrop_link}"
        )
    else:
        caption = (
            f"🎬 {display_name(entry)}\n"
            f"━━━━━━━━━━━━\n"
            f"📂 Part {index}\n"
            f"🎞️ 360p30 | 📦 {size_mb:.1f} MB\n"
            f"❌ Mixdrop upload failed"
        )

    sent = False

    if CHANNEL_ID:
        if size_mb < 48:
            try:
                with open(part_path, "rb") as video:
                    await app.bot.send_video(
                        chat_id=CHANNEL_ID,
                        video=video,
                        caption=caption,
                        supports_streaming=True,
                    )
                sent = True
            except Exception as exc:
                print(f"Telegram video send failed: {exc}", flush=True)

        if not sent:
            try:
                with open(part_path, "rb") as document:
                    await app.bot.send_document(
                        chat_id=CHANNEL_ID,
                        document=document,
                        caption=caption,
                        filename=os.path.basename(part_path),
                    )
                sent = True
            except Exception as exc:
                print(f"Telegram document send failed: {exc}", flush=True)
    else:
        print("CHANNEL_ID is not configured.", flush=True)

    if sent or mixdrop_link:
        try:
            os.remove(part_path)
        except OSError as exc:
            print(f"Could not remove uploaded part: {exc}", flush=True)
        return True

    return False


async def upload_ready_parts(entry: str, part_paths, uploaded_count: int, uploaded_files: set, app):
    for part_path in part_paths:
        if part_path in uploaded_files:
            continue

        ready = await asyncio.to_thread(is_file_ready, part_path)
        if not ready:
            continue

        try:
            succeeded = await upload_one_part(entry, part_path, uploaded_count + 1, app)
        except Exception as exc:
            print(f"Upload part failed: {exc}\n{traceback.format_exc()}", flush=True)
            succeeded = False

        if succeeded:
            uploaded_count += 1
            uploaded_files.add(part_path)

    return uploaded_count


async def stop_process(process):
    if process is None or process.poll() is not None:
        return

    try:
        process.terminate()
        await asyncio.to_thread(process.wait, timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            await asyncio.to_thread(process.wait, timeout=10)
        except Exception:
            pass


async def process_stream(entry: str, app):
    platform, uid = parse_entry(entry)
    safe_uid = re.sub(r"[^a-zA-Z0-9_-]", "_", uid.lstrip("@")) or "stream"
    base_name = f"{platform}_{safe_uid}_{int(time.time())}"

    print(f"Live detected: {entry} -> Starting stream recording", flush=True)

    uploaded_count = 0
    uploaded_files = set()
    retry = 0
    attempt = 0

    try:
        while retry < 5:
            process = None
            log_file = None
            attempt += 1
            attempt_name = f"{base_name}_try{attempt}"
            pattern = f"{attempt_name}_part%03d.mp4"
            glob_pattern = f"{attempt_name}_part*.mp4"

            try:
                stream_url = await asyncio.to_thread(get_stream_url, entry)

                if not stream_url:
                    retry += 1
                    print(f"No stream URL found; retry {retry}/5 for {entry}", flush=True)
                    await asyncio.sleep(15)
                    continue

                retry = 0
                log_file = open(f"{attempt_name}_ffmpeg.log", "w", encoding="utf-8")

                process = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-y",
                        "-rw_timeout",
                        "15000000",
                        "-i",
                        stream_url,
                        "-c",
                        "copy",
                        "-f",
                        "segment",
                        "-segment_time",
                        "600",
                        "-segment_format",
                        "mp4",
                        "-reset_timestamps",
                        "1",
                        "-break_non_keyframes",
                        "1",
                        pattern,
                    ],
                    stdout=log_file,
                    stderr=log_file,
                )

                while process.poll() is None:
                    await asyncio.sleep(20)
                    part_paths = sorted(glob.glob(glob_pattern))
                    uploaded_count = await upload_ready_parts(entry, part_paths, uploaded_count, uploaded_files, app)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                retry += 1
                print(f"Stream processing error for {entry}: {exc}\n{traceback.format_exc()}", flush=True)
            finally:
                if process is not None:
                    await stop_process(process)
                if log_file is not None:
                    log_file.close()

            part_paths = sorted(glob.glob(glob_pattern))
            uploaded_count = await upload_ready_parts(entry, part_paths, uploaded_count, uploaded_files, app)

            live = await asyncio.to_thread(is_live, entry)
            if not live:
                print(f"Stream ended for {entry}", flush=True)
                break

            print(f"Stream disconnected but still live; reconnecting {entry}", flush=True)
            await asyncio.sleep(10)

    except asyncio.CancelledError:
        print(f"Recording task was cancelled for {entry}", flush=True)
        raise
    finally:
        RECORDING.discard(entry)
        print(f"Recording state cleared for {entry}", flush=True)


async def check_loop(app):
    while True:
        try:
            for username in list(USERNAMES):
                if username in RECORDING:
                    continue

                try:
                    live = await asyncio.to_thread(is_live, username)
                except Exception as exc:
                    print(f"Live check error for {username}: {exc}", flush=True)
                    continue

                if live and username not in RECORDING:
                    RECORDING.add(username)
                    asyncio.create_task(process_stream(username, app))

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"Main checker loop error: {exc}", flush=True)

        await asyncio.sleep(60)


async def run_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing.")
    if not CHANNEL_ID:
        raise RuntimeError("CHANNEL_ID is missing.")

    from telegram.request import HTTPXRequest

    httpx_request = HTTPXRequest(
        read_timeout=600,
        write_timeout=600,
        connect_timeout=60,
        pool_timeout=600,
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(httpx_request)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("test", test_command))

    print(
        f"Bot starting. Mixdrop configured: {bool(MIXDROP_EMAIL and MIXDROP_KEY)}; tracked users: {len(USERNAMES)}",
        flush=True,
    )

    checker_task = None

    try:
        await app.initialize()
        await app.start()

        if app.updater is None:
            raise RuntimeError("Telegram updater failed to initialize.")

        await app.updater.start_polling()
        checker_task = asyncio.create_task(check_loop(app))

        print("Bot is running.", flush=True)
        await asyncio.Event().wait()

    finally:
        if checker_task is not None:
            checker_task.cancel()
            try:
                await checker_task
            except asyncio.CancelledError:
                pass

        if app.updater is not None:
            await app.updater.stop()

        if app.running:
            await app.stop()

        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Bot stopped manually.", flush=True)
    except Exception as exc:
        print(f"Bot startup failed: {exc}", flush=True)
        raise
