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

tasks = {}
task_queue = []
max_concurrent_downloads = 1
current_downloads = 0
DOWNLOAD_DIR = "downloads"
PART_SIZE_MB = 400  # split video if it's larger than 400MB

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f}{unit}"
        bytes /= 1024
    return f"{bytes:.2f}TB"

def log_progress(task_id, message, percent):
    tasks[task_id]["progress"] = {
        "message": message,
        "percent": percent,
        "timestamp": time.strftime("%M:%S", time.localtime())
    }

def process_queue():
    global current_downloads
    while True:
        if current_downloads < max_concurrent_downloads and task_queue:
            task = task_queue.pop(0)
            current_downloads += 1
            threading.Thread(target=handle_download, args=(task,)).start()
        time.sleep(1)

def handle_download(task):
    global current_downloads
    task_id = task["id"]
    url = task["url"]
    tasks[task_id] = {
        "status": "processing",
        "start_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "progress": {},
        "result": []
    }

    log_progress(task_id, "🔍 Processing URL", 5)
    start_time = time.time()
    full_path = os.path.join(DOWNLOAD_DIR, f"{task_id}.mp4")

    ydl_opts = {
        "outtmpl": full_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "progress_hooks": [lambda d: hook(d, task_id, start_time)],
        "ffmpeg_location": "/usr/bin/ffmpeg",
        "hls_prefer_native": True,
        "allow_unplayable_formats": True,
    }

    try:
        log_progress(task_id, "✅ Validating link...", 10)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        log_progress(task_id, "📤 Splitting & uploading...", 95)
        part_links = split_and_upload(task_id, full_path)
        tasks[task_id]["result"] = part_links
        log_progress(task_id, f"✅ Done in {int(time.time() - start_time)}s", 100)
        tasks[task_id]["status"] = "completed"

    except Exception as e:
        tasks[task_id]["status"] = "error"
        log_progress(task_id, f"❌ Error: {str(e)}", 0)

    finally:
        current_downloads -= 1
        if os.path.exists(full_path):
            os.remove(full_path)

def split_and_upload(task_id, video_path):
    part_urls = []
    size_mb = os.path.getsize(video_path) / (1024 * 1024)

    if size_mb <= PART_SIZE_MB:
        part_urls.append(upload_to_gofile(video_path))
        return part_urls

    part_num = 1
    temp_dir = os.path.join(DOWNLOAD_DIR, f"{task_id}_parts")
    os.makedirs(temp_dir, exist_ok=True)

    command = f"ffmpeg -i \"{video_path}\" -c copy -map 0 -f segment -segment_time 300 -reset_timestamps 1 \"{temp_dir}/part_%03d.mp4\""
    subprocess.call(command, shell=True)

    for fname in sorted(os.listdir(temp_dir)):
        fpath = os.path.join(temp_dir, fname)
        part_links.append(upload_to_gofile(fpath))
        os.remove(fpath)

    shutil.rmtree(temp_dir, ignore_errors=True)
    return part_urls

def upload_to_gofile(file_path):
    with open(file_path, "rb") as f:
        response = requests.post("https://store1.gofile.io/uploadFile", files={"file": f})
    return response.json()["data"]["downloadPage"]

def hook(d, task_id, start_time):
    if d["status"] == "downloading":
        percent = float(d.get("_percent_str", "0%").strip("%"))
        downloaded = d.get("_downloaded_bytes_str", "0B")
        total = d.get("_total_bytes_str", "0B")
        speed = d.get("_speed_str", "0B/s")
        eta = d.get("eta", 0)
        msg = f"⬇️ {percent:.1f}% | {downloaded}/{total} at {speed} | ETA: {eta}s"
        log_progress(task_id, msg, percent)
    elif d["status"] == "finished":
        log_progress(task_id, "🔄 Processing video...", 90)

@app.route("/download")
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    task_id = str(uuid.uuid4())
    task = {"id": task_id, "url": url}
    task_queue.append(task)
    return jsonify({
        "task_id": task_id,
        "status_url": f"/response?taskid={task_id}"
    }), 202

@app.route("/response")
def response():
    task_id = request.args.get("taskid")
    if not task_id or task_id not in tasks:
        return jsonify({"error": "Invalid or missing task ID"}), 404
    return jsonify(tasks[task_id])

@app.route("/")
def home():
    return jsonify({
        "status": "running",
        "tasks": len(tasks),
        "queue": len(task_queue),
        "active_downloads": current_downloads,
        "cpu": f"{psutil.cpu_percent()}%",
        "memory": f"{psutil.virtual_memory().percent}%"
    })

threading.Thread(target=process_queue, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
