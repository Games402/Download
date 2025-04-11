import os
import uuid
import time
import shutil
import threading
import subprocess
from flask import Flask, request, jsonify
from collections import deque
from datetime import datetime
import requests

app = Flask(__name__)

task_queue = deque()
active_task = None
tasks = {}
logs = {}
MAX_LOGS = 20

def generate_task_id():
    return str(uuid.uuid4())[:8]

def clean_old_logs():
    while len(logs) > MAX_LOGS:
        logs.pop(next(iter(logs)))

def update_log(task_id, status, progress=None, speed=None, eta=None):
    logs[task_id] = {
        "status": status,
        "progress": progress,
        "speed": speed,
        "eta": eta,
        "timestamp": datetime.utcnow().isoformat()
    }
    clean_old_logs()

def download_and_process(task_id, url):
    global active_task
    folder = f"task_{task_id}"
    os.makedirs(folder, exist_ok=True)
    update_log(task_id, "⏳ Processing URL...", progress="0%", eta="Estimating...")

    command = [
        "yt-dlp",
        "--downloader", "ffmpeg",
        "--hls-prefer-ffmpeg",
        "--no-part",
        "--progress",
        "-o", f"{folder}/video.mp4",
        url
    ]

    start_time = time.time()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    try:
        for line in process.stdout:
            if "%" in line:
                parts = line.strip().split()
                try:
                    percent = next(x for x in parts if "%" in x)
                    speed = next(x for x in parts if "iB/s" in x)
                    eta = next((x for x in parts if "ETA" in x or ":" in x), "Estimating...")
                    update_log(task_id, "⬇️ Downloading...", percent, speed, eta)
                except StopIteration:
                    continue
            elif "Merging" in line or "Deleting" in line:
                update_log(task_id, f"⚙️ {line.strip()}")
    except Exception as e:
        update_log(task_id, f"❌ Error: {str(e)}")
        active_task = None
        return

    process.wait()
    duration = time.time() - start_time

    if os.path.exists(f"{folder}/video.mp4"):
        update_log(task_id, "✅ Download complete. Uploading...", progress="100%", eta="0s")
        try:
            with open(f"{folder}/video.mp4", "rb") as f:
                response = requests.post("https://api.gofile.io/uploadFile", files={"file": f}).json()
            link = response["data"]["downloadPage"]
            update_log(task_id, f"✅ Done! [Open]({link})", progress="100%", speed="0", eta=f"{int(duration)}s")
        except:
            update_log(task_id, "✅ Downloaded, but failed to upload.")
    else:
        update_log(task_id, "❌ Download failed or file not found.")

    shutil.rmtree(folder, ignore_errors=True)
    active_task = None

@app.route("/")
def home():
    return jsonify({"status": "Server running", "uptime": time.ctime()})

@app.route("/download")
def start_download():
    global active_task

    url = request.args.get("url")
    if not url or not url.startswith("http"):
        return jsonify({"error": "Invalid or missing URL"}), 400

    task_id = generate_task_id()
    tasks[task_id] = {"url": url}
    task_queue.append((task_id, url))
    update_log(task_id, "⏳ Queued. Waiting for availability...")

    return jsonify({"task_id": task_id, "message": "Download task queued."})

@app.route("/response")
def get_response():
    task_id = request.args.get("taskid")
    if not task_id:
        return jsonify({"error": "Missing taskid"}), 400
    if task_id not in logs:
        return jsonify({"error": "Invalid taskid or task not started yet"}), 404
    return jsonify({"task_id": task_id, "log": logs[task_id]})

def task_handler():
    global active_task
    while True:
        if active_task is None and task_queue:
            task_id, url = task_queue.popleft()
            active_task = task_id
            threading.Thread(target=download_and_process, args=(task_id, url), daemon=True).start()
        time.sleep(2)

if __name__ == "__main__":
    threading.Thread(target=task_handler, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
