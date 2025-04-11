import os
import uuid
import time
import threading
import shutil
import subprocess
from flask import Flask, request, jsonify
import yt_dlp
import psutil
import requests

app = Flask(__name__)

DOWNLOAD_DIR = "downloads"
PART_SIZE_MB = 300
MAX_CONCURRENT = 1
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

tasks = {}
task_queue = []
active_downloads = 0


def format_eta(seconds):
    m, s = divmod(int(seconds), 60)
    return f"{m:02}:{s:02}"

def log_status(task_id, message, percent):
    now = time.time()
    tasks[task_id]["log"] = {
        "message": message,
        "percent": percent,
        "timestamp": now
    }

def handle_task(task):
    global active_downloads
    task_id = task["id"]
    url = task["url"]
    start_time = time.time()
    tasks[task_id] = {
        "status": "processing",
        "start_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "log": {},
        "parts": []
    }

    try:
        log_status(task_id, "🔍 Processing URL...", 5)

        # Step 1: Download .m3u8 as a full MP4
        filename = os.path.join(DOWNLOAD_DIR, f"{task_id}.mp4")
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'outtmpl': filename,
            'retries': 2,
            'noplaylist': True,
            'no_warnings': True,
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'progress_hooks': [lambda d: update_hook(d, task_id, start_time)]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        log_status(task_id, "🎬 Splitting video into parts...", 92)

        # Step 2: Split into 300MB chunks
        split_dir = os.path.join(DOWNLOAD_DIR, f"{task_id}_parts")
        os.makedirs(split_dir, exist_ok=True)

        part_prefix = os.path.join(split_dir, f"{task_id}_part_")
        split_cmd = [
            "ffmpeg", "-i", filename, "-c", "copy", "-f", "segment",
            "-segment_size", str(PART_SIZE_MB * 1024 * 1024),
            "-reset_timestamps", "1", f"{part_prefix}%03d.mp4"
        ]

        subprocess.run(split_cmd, check=True)
        os.remove(filename)

        # Step 3: Upload each part
        for part_file in sorted(os.listdir(split_dir)):
            part_path = os.path.join(split_dir, part_file)
            log_status(task_id, f"📤 Uploading {part_file}...", 95)

            with open(part_path, "rb") as f:
                r = requests.post("https://store1.gofile.io/uploadFile", files={"file": f})
                download_url = r.json()["data"]["downloadPage"]
                tasks[task_id]["parts"].append(download_url)
            os.remove(part_path)

        tasks[task_id]["status"] = "completed"
        log_status(task_id, f"✅ Done! {len(tasks[task_id]['parts'])} parts uploaded.", 100)

    except Exception as e:
        tasks[task_id]["status"] = "error"
        log_status(task_id, f"❌ Error: {str(e)}", 0)
    finally:
        shutil.rmtree(split_dir, ignore_errors=True)
        active_downloads -= 1


def update_hook(d, task_id, start_time):
    if d["status"] == "downloading":
        p = float(d.get("_percent_str", "0").strip("%"))
        eta = format_eta(d.get("eta", 0))
        log_status(task_id, f"⬇️ Downloading... {p:.1f}% | ETA {eta}", p)
    elif d["status"] == "finished":
        log_status(task_id, "📦 Download complete. Processing...", 90)


def task_manager():
    global active_downloads
    while True:
        if active_downloads < MAX_CONCURRENT and task_queue:
            task = task_queue.pop(0)
            active_downloads += 1
            threading.Thread(target=handle_task, args=(task,)).start()
        time.sleep(1)


@app.route("/download")
def queue_download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400
    task_id = str(uuid.uuid4())
    task = {"id": task_id, "url": url}
    task_queue.append(task)
    return jsonify({"task_id": task_id, "status_url": f"/response?taskid={task_id}"}), 202


@app.route("/response")
def get_status():
    task_id = request.args.get("taskid")
    if not task_id or task_id not in tasks:
        return jsonify({"error": "Invalid or missing task ID"}), 404
    return jsonify(tasks[task_id])


@app.route("/")
def health():
    return jsonify({
        "status": "running",
        "queued": len(task_queue),
        "active": active_downloads,
        "tasks": len(tasks),
        "cpu": f"{psutil.cpu_percent()}%",
        "ram": f"{psutil.virtual_memory().percent}%"
    })


# Start background task manager
threading.Thread(target=task_manager, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
