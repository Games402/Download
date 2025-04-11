from flask import Flask, request, jsonify
from threading import Thread
from yt_dlp import YoutubeDL
import uuid
import time
import datetime
import os
import shutil
import psutil

app = Flask(__name__)
tasks = {}
download_folder = "downloads"
os.makedirs(download_folder, exist_ok=True)

def format_time(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%H:%M')

def format_eta(seconds):
    return time.strftime('%M:%S', time.gmtime(seconds))

def run_download(task_id, url):
    start_time = time.time()
    tasks[task_id] = {
        "status": "processing",
        "current_log": {
            "message": "🔍 Processing URL",
            "percent": 5,
            "timestamp": format_time(start_time)
        },
        "start": start_time
    }

    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "progress_hooks": [lambda d: handle_progress(d, task_id)],
        "outtmpl": f"{download_folder}/{task_id}.mp4",
        "ffmpeg_location": "/usr/bin/ffmpeg",
        "usenetrc": False,
    }

    try:
        tasks[task_id]["status"] = "validating"
        tasks[task_id]["current_log"] = {
            "message": "🔎 Validating link",
            "percent": 10,
            "timestamp": format_time(time.time())
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["current_log"] = {
            "message": "✅ Download complete",
            "percent": 100,
            "timestamp": format_time(time.time())
        }

    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["current_log"] = {
            "message": f"❌ Error: {str(e)}",
            "percent": 0,
            "timestamp": format_time(time.time())
        }

def handle_progress(d, task_id):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '').strip().replace('%', '')
        eta = d.get('eta', 0)
        speed = d.get('_speed_str', '').strip()
        downloaded = d.get('_downloaded_bytes_str', '')
        total = d.get('_total_bytes_str', '')
        message = f"⬇️ Downloading: {percent}% | {downloaded} of {total} at {speed} | ETA: {format_eta(eta)}"
        tasks[task_id]["status"] = "downloading"
        tasks[task_id]["current_log"] = {
            "message": message,
            "percent": float(percent or 0),
            "eta": format_eta(eta),
            "timestamp": format_time(time.time())
        }

@app.route("/download", methods=["GET"])
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL missing"}), 400

    task_id = str(uuid.uuid4())
    thread = Thread(target=run_download, args=(task_id, url))
    thread.start()

    return jsonify({
        "message": "📥 Download started",
        "task_id": task_id
    })

@app.route("/response", methods=["GET"])
def response():
    task_id = request.args.get("taskid")
    if task_id not in tasks:
        return jsonify({"error": "Invalid task ID"}), 404

    task = tasks[task_id]
    return jsonify({
        "task_id": task_id,
        "status": task["status"],
        "current_log": task["current_log"],
        "start_time": format_time(task["start"])
    })

@app.route("/")
def home():
    return "✅ Render backend is running!"

if __name__ == "__main__":
    app.run(debug=False, port=10000)
