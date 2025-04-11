from flask import Flask, request, jsonify
import threading, time, uuid
import yt_dlp
import requests
from datetime import datetime
from queue import Queue

app = Flask(__name__)

tasks = {}
task_queue = Queue()
max_concurrent_tasks = 1
active_tasks = 0

def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def estimate_time(start, percent):
    if percent == 0:
        return "Calculating..."
    elapsed = time.time() - start
    total = elapsed / (percent / 100)
    remaining = total - elapsed
    return f"{int(remaining)}s left"

def download_worker():
    global active_tasks
    while True:
        if not task_queue.empty() and active_tasks < max_concurrent_tasks:
            task_id = task_queue.get()
            active_tasks += 1
            try:
                run_download(task_id)
            except Exception as e:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["error"] = str(e)
            active_tasks -= 1

def update_progress(task_id, message, percent):
    task = tasks.get(task_id)
    if task:
        log = {
            "message": message,
            "percent": percent,
            "timestamp": time.time(),
            "eta": estimate_time(task["start_ts"], percent)
        }
        task["progress"].append(log)

def run_download(task_id):
    task = tasks[task_id]
    url = task["url"]
    task["status"] = "processing"
    task["start_ts"] = time.time()
    update_progress(task_id, "🔍 Processing URL...", 5)

    time.sleep(1)  # Simulated processing delay
    update_progress(task_id, "🔎 Validating URL...", 10)

    ydl_opts = {
        'format': 'best',
        'outtmpl': f'/tmp/{task_id}.mp4',
        'progress_hooks': [lambda d: handle_progress(d, task_id)],
        'noplaylist': True,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            update_progress(task_id, "⏬ Downloading...", 20)
            ydl.download([url])
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = str(e)
        return

    update_progress(task_id, "✅ Uploading to GoFile...", 95)

    try:
        with open(f'/tmp/{task_id}.mp4', 'rb') as f:
            go_res = requests.post('https://store1.gofile.io/uploadFile', files={'file': f})
            go_url = go_res.json()['data']['downloadPage']
            tasks[task_id]["gofile_url"] = go_url
    except Exception as e:
        tasks[task_id]["status"] = "error"
        tasks[task_id]["error"] = "Upload failed: " + str(e)
        return

    update_progress(task_id, "✅ Done!", 100)
    tasks[task_id]["status"] = "completed"

def handle_progress(d, task_id):
    if d['status'] == 'downloading':
        percent = d.get('_percent_str', '0%').strip().replace('%', '')
        try:
            percent = float(percent)
        except:
            percent = 0
        update_progress(task_id, f"📦 Downloading... {percent:.2f}%", percent)

@app.route('/download')
def download():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "url": url,
        "status": "queued",
        "progress": [],
        "start_time": now(),
        "gofile_url": None,
        "error": None
    }

    task_queue.put(task_id)
    return jsonify({"task_id": task_id, "message": "Task added to queue"}), 202

@app.route('/response')
def response():
    task_id = request.args.get('taskid')
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Invalid Task ID"}), 404

    return jsonify({
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "start_time": task["start_time"],
        "gofile_url": task.get("gofile_url"),
        "error": task.get("error")
    })

if __name__ == '__main__':
    threading.Thread(target=download_worker, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
