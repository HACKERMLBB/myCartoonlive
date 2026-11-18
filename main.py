import subprocess
import os
import time
import threading
import requests
from flask import Flask

app = Flask(__name__)

FOLDER = "/tmp/myLive"
os.makedirs(FOLDER, exist_ok=True)

MIXDROP_API_KEY = os.environ.get("MIXDROP_API_KEY", "")
MIXDROP_EMAIL = os.environ.get("MIXDROP_EMAIL", "")
MIXDROP_FOLDER_ID = os.environ.get("MIXDROP_FOLDER_ID", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "")

CURRENT_LINK = {"url": os.environ.get("LIVE_LINK", ""), "active": False, "part": 1}
STOP_FLAG = {"stop": False}

@app.route("/")
def home():
    return "Bot is Running"

@app.route("/health")
def health():
    return "OK"

def tg_send(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=30)
    except:
        pass

def get_thumbnail(video_path, thumb_path):
    cmd = ["ffmpeg", "-y", "-ss", "5", "-i", video_path, "-vframes", "1", thumb_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(thumb_path):
        return thumb_path
    return None

def upload_to_mixdrop(file_path):
    print(f"Uploading to MixDrop: {file_path}", flush=True)
    try:
        url = "https://ul.mixdrop.ag/api"
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {"email": MIXDROP_EMAIL, "key": MIXDROP_API_KEY}
            if MIXDROP_FOLDER_ID:
                data["folder"] = MIXDROP_FOLDER_ID
            r = requests.post(url, files=files, data=data, timeout=1200)
            res = r.json()
            if res.get("result") == "success":
                file_code = res["result"]["fileref"]
                link = f"https://mixdrop.ag/f/{file_code}"
                print(f"MixDrop Done: {link}", flush=True)
                return link
            else:
                print(f"MixDrop Failed: {res}", flush=True)
                return None
    except Exception as e:
        print(f"Upload Error: {e}", flush=True)
        return None

def send_to_channel(file_path, mixdrop_link, part_name):
    if not mixdrop_link:
        return
    thumb_path = file_path + ".jpg"
    thumb = get_thumbnail(file_path, thumb_path)
    size_mb = round(os.path.getsize(file_path) / 1024 / 1024, 1)
    caption = (
        f"🎬 <b>Cartoon Live - {part_name}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✨ <b>New Episode Uploaded!</b>\n"
        f"🍿 Enjoy Watching Baby! 💖\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📦 Size: {size_mb} MB\n"
        f"🎞️ Quality: HD\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Watch Now:</b>\n"
        f"{mixdrop_link}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"❤️ Share & Enjoy!"
    )
    try:
        if thumb:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(thumb, "rb") as photo:
                requests.post(url, data={"chat_id": TELEGRAM_CHANNEL_ID, "caption": caption, "parse_mode": "HTML"}, files={"photo": photo}, timeout=60)
        else:
            tg_send(TELEGRAM_CHANNEL_ID, caption)
        print(f"Channel Done: {part_name}", flush=True)
    except Exception as e:
        print(f"Telegram Error: {e}", flush=True)
    if thumb and os.path.exists(thumb):
        os.remove(thumb)

def upload_and_send(file_path, part_name):
    link = upload_to_mixdrop(file_path)
    send_to_channel(file_path, link, part_name)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass

def record_live(link, chat_id):
    CURRENT_LINK["active"] = True
    STOP_FLAG["stop"] = False
    part_num = 1
    tg_send(chat_id, "🔴 <b>LIVE DETECTED!</b>\n\n🎬 Recording Started...\n⏳ Please Wait Baby! 💖")
    tg_send(TELEGRAM_CHANNEL_ID, "🔴 <b>LIVE STARTED!</b>\n\n🎬 Cartoon Live Started!\n✨ New Parts Coming Soon...\n⏳ Stay Tuned Baby! 💖")
    while not STOP_FLAG["stop"]:
        check = subprocess.run(["yt-dlp", "-f", "bestvideo+bestaudio/best", "--get-url", link], capture_output=True, text=True)
        if check.returncode != 0 or not check.stdout.strip():
            break
        stream_url = check.stdout.strip().splitlines()[0]
        part_path = os.path.join(FOLDER, f"Live_Part{part_num}.mp4")
        print(f"Recording Part {part_num}", flush=True)
        cmd = ["ffmpeg", "-y", "-i", stream_url, "-c", "copy", "-fs", "100M", part_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(part_path) and os.path.getsize(part_path) > 1000:
            t = threading.Thread(target=upload_and_send, args=(part_path, f"Part {part_num}"))
            t.start()
            tg_send(chat_id, f"✅ <b>Part {part_num} Done!</b>\n📤 Uploading to MixDrop...\n🎬 Recording Part {part_num + 1}...")
        else:
            break
        part_num += 1
        time.sleep(2)
        check2 = subprocess.run(["yt-dlp", "-f", "bestvideo+bestaudio/best", "--get-url", link], capture_output=True, text=True)
        if check2.returncode != 0:
            break
    CURRENT_LINK["active"] = False
    tg_send(chat_id, "🏁 <b>Live Finished!</b>\n\n✅ All Parts Uploaded!\n💖 Thank You Baby!")
    tg_send(TELEGRAM_CHANNEL_ID, "🏁 <b>Live Finished!</b>\n\n✅ All Parts Uploaded!\n🍿 Enjoy Watching! 💖")

def telegram_polling():
    offset = 0
    print("Telegram Polling Started", flush=True)
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            r = requests.get(url, timeout=35).json()
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if not text or not chat_id:
                    continue
                if text.startswith("/start"):
                    tg_send(chat_id, "👋 <b>Hi Baby! 💖</b>\n\n🎬 Send Your Live Link Like This:\n\n<code>/live YOUR_LINK</code>\n\n📌 Commands:\n/live - Start Recording\n/stop - Stop Recording\n/status - Check Status")
                elif text.startswith("/live"):
                    parts = text.split(None, 1)
                    if len(parts) < 2:
                        tg_send(chat_id, "❌ <b>Please Send Link Like This Baby!</b>\n\n<code>/live YOUR_LINK</code>")
                        continue
                    if CURRENT_LINK["active"]:
                        tg_send(chat_id, "⚠️ <b>Already Recording Baby!</b>\n\nSend /stop to stop first.")
                        continue
                    link = parts[1].strip()
                    CURRENT_LINK["url"] = link
                    tg_send(chat_id, f"🔍 <b>Checking Live...</b>\n\n🔗 Link: {link}\n⏳ Please Wait...")
                    t = threading.Thread(target=record_live, args=(link, chat_id))
                    t.start()
                elif text.startswith("/stop"):
                    if CURRENT_LINK["active"]:
                        STOP_FLAG["stop"] = True
                        tg_send(chat_id, "🛑 <b>Stopping...</b>\n\n⏳ Please Wait Baby!")
                    else:
                        tg_send(chat_id, "😅 <b>No Live Recording Now Baby!</b>")
                elif text.startswith("/status"):
                    if CURRENT_LINK["active"]:
                        tg_send(chat_id, "🔴 <b>Status: Recording...</b>\n\n🎬 Live is Recording Baby! 💖")
                    else:
                        tg_send(chat_id, "⚪ <b>Status: Waiting...</b>\n\nSend /live + link to start Baby! 🎬")
        except Exception as e:
            print(f"Polling Error: {e}", flush=True)
            time.sleep(5)

threading.Thread(target=telegram_polling, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
