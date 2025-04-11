from flask import Flask, request, jsonify
from yt_dlp import YoutubeDL
import threading, time, uuid, shutil, json, os, datetime, subprocess
import requests  # ✅ Required for GoFile and key fetching

app = Flask(__name__)

MAX_LOGS = 20
active_task = None
task_queue = []
progress_data = {}
completed_logs_path = "completed_logs.json"

# Load existing logs if available
if os.path.exists(completed_logs_path):
    with open(completed_logs_path) as f:
        completed_logs = json.load(f)
else:
    completed_logs = []

def save_completed_log(entry):
    global completed_logs
    completed_logs.insert(0, entry)
    completed_logs = completed_logs[:MAX_LOGS]
    with open(completed_logs_path, "w") as f:
        json.dump(completed_logs, f, indent=2)

def update_progress(taskid, message, percent, speed=None, eta=None):
    timestamp = time.time()
    log_entry = {
        "message": message,
        "percent": percent,
        "timestamp": timestamp
    }
    if speed:
        log_entry["speed"] = speed
    if eta:
        log_entry["eta"] = eta

    progress_data[taskid]["progress"].append(log_entry)

def download_task(taskid, url):
    try:
        progress_data[taskid]["status"] = "processing"
        update_progress(taskid, "🔍 Processing URL", 5)

        ydl_opts = {
            'format': 'best',
            'outtmpl': f'downloads/{taskid}.mp4',
            'quiet': True,
            'noplaylist': True,
            'progress_hooks': [lambda d: progress_hook(d, taskid)],
        }

        update_progress(taskid, "🔎 Validating link", 10)
        time.sleep(1)  # Simulated delay

        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            video_title = info_dict.get("title", "Untitled")
            filesize = info_dict.get("filesize") or 0

        update_progress(taskid, "✅ Uploading to GoFile", 95)

        with open(filename, 'rb') as f:
            res = requests.post("https://api.gofile.io/uploadFile", files={"file": f})
            gofile_data = res.json()

        gofile_url = gofile_data['data']['downloadPage']
        update_progress(taskid, "✅ Done", 100)

        save_completed_log({
            "video_id": taskid,
            "title": video_title,
            "url": gofile_url,
            "timestamp": str(datetime.datetime.now())
        })

        progress_data[taskid]["status"] = "done"
        progress_data[taskid]["gofile"] = gofile_url

        os.remove(filename)

    except Exception as e:
        update_progress(taskid, f"❌ Error: {str(e)}", 0)
        progress_data[taskid]["status"] = "error"
        progress_data[taskid]["error"] = str(e)

    finally:
        global active_task
        active_task = None

def progress_hook(d, taskid):
    if d['status'] == 'downloading':
        percent = d.get("_percent_str", "0").strip().replace("%", "")
        speed = d.get("_speed_str", "0")
        eta = d.get("_eta_str", "0")
        update_progress(taskid, "⬇️ Downloading", float(percent), speed=speed, eta=eta)

def task_handler():
    global active_task
    if not active_task and task_queue:
        next = task_queue.pop(0)
        taskid = next["taskid"]
        url = next["url"]
        active_task = taskid
        thread = threading.Thread(target=download_task, args=(taskid, url))
        thread.start()

@app.route('/download', methods=['GET'])
def download():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    taskid = str(uuid.uuid4())
    progress_data[taskid] = {
        "status": "pending",
        "start_time": str(datetime.datetime.now()),
        "progress": []
    }

    if active_task:
        task_queue.append({"taskid": taskid, "url": url})
        update_progress(taskid, "📦 Task queued. Awaiting execution.", 1)
        return jsonify({"message": "Task added to queue", "taskid": taskid}), 202

    thread = threading.Thread(target=download_task, args=(taskid, url))
    active_task = taskid
    thread.start()
    return jsonify({"message": "Download started", "taskid": taskid}), 200

@app.route('/response', methods=['GET'])
def response():
    taskid = request.args.get("taskid")
    if not taskid or taskid not in progress_data:
        return jsonify({"error": "Invalid or missing taskid"}), 404
    return jsonify(progress_data[taskid])

@app.route('/admin', methods=['GET'])
def admin():
    return jsonify({
        "active_task": active_task,
        "queue_length": len(task_queue),
        "completed": completed_logs[-MAX_LOGS:]
    })

if __name__ == '__main__':
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    app.run(host='0.0.0.0', port=10000)
