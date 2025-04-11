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

# Global structures
tasks = {}
task_queue = []
max_concurrent_downloads = 1
current_downloads = 0
DOWNLOAD_DIR = "downloads"

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Util: Format size
def format_size(bytes):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.2f}{unit}"
        bytes /= 1024
    return f"{bytes:.2f}TB"

# Util: Create progress log entry
def log_progress(task_id, message, percent):
    entry = {
        "message": message,
        "percent": percent,
        "timestamp": time.time()
    }
    tasks[task_id]["progress"].append(entry)

# Worker thread to process queued tasks
def process_queue():
    global current_downloads
    while True:
        if current_downloads < max_concurrent_downloads and task_queue:
            task = task_queue.pop(0)
            current_downloads += 1
            threading.Thread(target=handle_download, args=(task,)).start()
        time.sleep(1)

# Core download function
def handle_download(task):
    global current_downloads
    task_id = task["id"]
    url = task["url"]

    tasks[task_id] = {
        "status": "processing",
        "start_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "progress": []
    }

    log_progress(task_id, "🔍 Processing URL", 5)
    start_time = time.time()

    # Download options
    output_path = os.path.join(DOWNLOAD_DIR, f"{task_id}.mp4")
    ydl_opts = {
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "progress_hooks": [lambda d: hook(d, task_id, start_time)],
        "ffmpeg_location": "/usr/bin/ffmpeg",  # Adjust for Render
    }

    try:
        log_progress(task_id, "✅ Validating link...", 10)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        duration = time.time() - start_time
        log_progress(task_id, f"✅ Download complete in {int(duration)}s", 100)

        # Upload to GoFile
        log_progress(task_id, "📤 Uploading to GoFile...", 95)
        with open(output_path, "rb") as f:
            upload = requests.post("https://store1.gofile.io/uploadFile", files={"file": f}).json()
        result_url = upload["data"]["downloadPage"]
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["result"] = result_url
        log_progress(task_id, "✅ Uploaded successfully", 100)

    except Exception as e:
        tasks[task_id]["status"] = "error"
        log_progress(task_id, f"❌ Error: {str(e)}", 0)

    finally:
        current_downloads -= 1
        if os.path.exists(output_path):
            os.remove(output_path)

# Hook for progress updates
def hook(d, task_id, start_time):
    if d["status"] == "downloading":
        downloaded = d.get("_downloaded_bytes_str", "0B")
        total = d.get("_total_bytes_str", "0B")
        speed = d.get("_speed_str", "0B/s")
        eta = d.get("eta", 0)
        percent = d.get("_percent_str", "0%")
        msg = f"⬇️ Downloading: {percent} | {downloaded} of {total} at {speed} | ETA: {eta}s"
        log_progress(task_id, msg, float(percent.strip("%")))
    elif d["status"] == "finished":
        log_progress(task_id, "🔄 Processing video...", 90)

# Endpoint to download
@app.route("/download")
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    task_id = str(uuid.uuid4())
    task = {"id": task_id, "url": url}
    task_queue.append(task)
    return jsonify({"task_id": task_id, "status_url": f"/response?taskid={task_id}"}), 202

# Endpoint to check progress
@app.route("/response")
def response():
    task_id = request.args.get("taskid")
    if not task_id or task_id not in tasks:
        return jsonify({"error": "Invalid or missing task ID"}), 404
    return jsonify(tasks[task_id])

# Health check or admin status
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

# Start background queue worker
threading.Thread(target=process_queue, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
