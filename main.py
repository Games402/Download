from flask import Flask, request, jsonify
import threading, time, uuid, shutil
from yt_dlp import YoutubeDL
import os, json, datetime, subprocess

app = Flask(__name__)
tasks = {}
queue = []
MAX_LOG = 20
LOG_FILE = 'logs.json'

def save_log(task_id, log):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            logs = json.load(f)
    else:
        logs = {}

    logs[task_id] = log
    if len(logs) > MAX_LOG:
        oldest = sorted(logs.keys())[0]
        logs.pop(oldest)

    with open(LOG_FILE, 'w') as f:
        json.dump(logs, f, indent=2)

def download_video(task_id, url):
    log = {"status": "processing", "start_time": str(datetime.datetime.now()), "progress": []}
    tasks[task_id] = log
    save_log(task_id, log)

    def log_progress(msg, percent):
        log["progress"].append({
            "timestamp": time.time(),
            "message": msg,
            "percent": percent
        })
        save_log(task_id, log)

    try:
        log_progress("🔍 Processing URL", 5)
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'outtmpl': f'{task_id}.mp4',
            'progress_hooks': [lambda d: log_progress(
                f"⬇️ {d['_percent_str']} - ETA: {d.get('eta', '?')}s", int(float(d['_percent_str'].strip('%')))
            ) if d['status'] == 'downloading' else None],
        }

        if "#EXT-X-KEY" in requests.get(url).text:
            ydl_opts['allow_unplayable_formats'] = True

        log_progress("✅ Validating link", 15)
        time.sleep(0.2)

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        log_progress("☁️ Uploading to GoFile.io", 95)
        gofile_resp = requests.post("https://store1.gofile.io/uploadFile", files={'file': open(f'{task_id}.mp4', 'rb')})
        gofile_url = gofile_resp.json()['data']['downloadPage']
        log_progress("✅ Completed", 100)
        log['status'] = 'completed'
        log['url'] = gofile_url
        save_log(task_id, log)
        os.remove(f'{task_id}.mp4')
    except Exception as e:
        log['status'] = 'error'
        log['error'] = str(e)
        save_log(task_id, log)

def task_handler():
    if not queue or any(t["status"] == "processing" for t in tasks.values()):
        return
    task = queue.pop(0)
    threading.Thread(target=download_video, args=(task["task_id"], task["url"])).start()

@app.route('/download')
def start_download():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "queued", "progress": []}
    queue.append({"task_id": task_id, "url": url})
    task_handler()
    return jsonify({"task_id": task_id, "message": "Task added to queue."})

@app.route('/response')
def task_status():
    task_id = request.args.get('taskid')
    if task_id not in tasks:
        return jsonify({'error': 'Invalid task ID'}), 404
    return jsonify(tasks[task_id])

@app.route('/')
def home():
    return "🎬 .m3u8 Downloader API (Render Optimized)"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
