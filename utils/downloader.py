import os, re, uuid, asyncio, shutil
from typing import Optional, Dict, Any, List
import yt_dlp

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp_downloads")
os.makedirs(TEMP_DIR, exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024


def detect_platform(url):
    url = url.lower()
    if "youtube.com" in url or "youtu.be" in url: return "youtube"
    if "instagram.com" in url: return "instagram"
    if "tiktok.com" in url: return "tiktok"
    if "vk.com" in url: return "vk"
    return None

def is_url(text):
    return bool(re.match(r"https?://\S+", text.strip()))

def _base_ydl_opts():
    return {"quiet": True, "no_warnings": True, "noplaylist": True,
            "socket_timeout": 30, "retries": 3, "fragment_retries": 3,
            "concurrent_fragment_downloads": 4}

async def get_video_info(url):
    loop = asyncio.get_event_loop()
    def _run():
        try:
            with yt_dlp.YoutubeDL({**_base_ydl_opts(), "skip_download": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info: return None
                return {"title": info.get("title","Unknown"),
                        "uploader": info.get("uploader") or info.get("channel","Unknown"),
                        "duration": info.get("duration",0), "url": url}
        except: return None
    return await loop.run_in_executor(None, _run)

async def download_audio(url, title="audio"):
    loop = asyncio.get_event_loop()
    def _run():
        uid = uuid.uuid4().hex[:8]
        opts = {**_base_ydl_opts(), "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": os.path.join(TEMP_DIR, f"{uid}.%(ext)s"),
                "postprocessors": [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: ydl.extract_info(url, download=True)
            expected = os.path.join(TEMP_DIR, f"{uid}.mp3")
            if os.path.exists(expected) and os.path.getsize(expected) <= MAX_FILE_SIZE:
                return expected
            for f in os.listdir(TEMP_DIR):
                if f.startswith(uid) and f.endswith(".mp3"):
                    full = os.path.join(TEMP_DIR, f)
                    if os.path.getsize(full) <= MAX_FILE_SIZE: return full
        except: return None
    return await loop.run_in_executor(None, _run)

async def download_video(url, title="video"):
    loop = asyncio.get_event_loop()
    def _run():
        uid = uuid.uuid4().hex[:8]
        fmt = ("bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
               "/bestvideo[height<=720]+bestaudio/best[height<=720]/best")
        opts = {**_base_ydl_opts(), "format": fmt,
                "outtmpl": os.path.join(TEMP_DIR, f"{uid}.%(ext)s"),
                "merge_output_format": "mp4"}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: ydl.extract_info(url, download=True)
            for f in os.listdir(TEMP_DIR):
                if f.startswith(uid):
                    full = os.path.join(TEMP_DIR, f)
                    if os.path.getsize(full) <= MAX_FILE_SIZE: return full
        except: return None
    return await loop.run_in_executor(None, _run)

async def search_music(query, limit=8):
    loop = asyncio.get_event_loop()
    def _run():
        opts = {"quiet":True,"no_warnings":True,"skip_download":True,
                "extract_flat":"in_playlist","socket_timeout":15,"retries":2}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                res = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            out = []
            for e in (res.get("entries",[]) if res else []):
                if not e: continue
                vid = e.get("id") or e.get("url","")
                if not vid: continue
                out.append({"title": e.get("title","Unknown"),
                             "uploader": e.get("uploader") or e.get("channel","Unknown"),
                             "duration": e.get("duration",0),
                             "url": f"https://www.youtube.com/watch?v={vid}", "id": vid})
            return out
        except: return []
    return await loop.run_in_executor(None, _run)

async def download_playlist(url):
    loop = asyncio.get_event_loop()
    def _run():
        uid = uuid.uuid4().hex[:8]
        opts = {**_base_ydl_opts(), "noplaylist": False, "playlistend": 10,
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": os.path.join(TEMP_DIR, f"{uid}_%(playlist_index)02d.%(ext)s"),
                "postprocessors": [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: ydl.extract_info(url, download=True)
            return [os.path.join(TEMP_DIR,f) for f in sorted(os.listdir(TEMP_DIR))
                    if f.startswith(uid) and f.endswith(".mp3")
                    and os.path.getsize(os.path.join(TEMP_DIR,f)) <= MAX_FILE_SIZE]
        except: return []
    return await loop.run_in_executor(None, _run)

def cleanup_file(path):
    try:
        if path and os.path.exists(path): os.remove(path)
    except: pass

def cleanup_old_files(max_age_seconds=3600):
    import time; now = time.time()
    try:
        for f in os.listdir(TEMP_DIR):
            full = os.path.join(TEMP_DIR, f)
            if os.path.isfile(full) and now - os.path.getmtime(full) > max_age_seconds:
                os.remove(full)
    except: pass
