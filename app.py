"""
Video Editor Service - Pull Model
Branch: video-editor
"""

from flask import Flask, request, jsonify, Response, send_file
from flask_cors import CORS
from datetime import datetime, timezone
import threading
import time
import uuid
import os
import json
import subprocess
import re
import select
import hvac
import time

def get_vault_secret(secret_path, env_fallback, default_val="stub-api-key"):
    vault_addr = os.environ.get("VAULT_ADDR")
    vault_token = os.environ.get("VAULT_TOKEN")

    if not (vault_addr and vault_token):
        return os.environ.get(env_fallback, default_val)

    attempts = 5
    delay = 0.5
    for attempt in range(1, attempts + 1):
        try:
            client = hvac.Client(url=vault_addr, token=vault_token)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data']['api_key']
            else:
                print(f"Vault auth failed on attempt {attempt}")
        except Exception as e:
            print(f"Failed to fetch {secret_path} from Vault (attempt {attempt}): {e}")

        if attempt < attempts:
            time.sleep(delay)
            delay = min(delay * 2, 5)

    return os.environ.get(env_fallback, default_val)

app = Flask(__name__)
CORS(app)

API_KEY = get_vault_secret("video-editor", "VIDEO_EDITOR_API_KEY")
JOB_DIR = "/tmp/video_editor_jobs"
os.makedirs(JOB_DIR, exist_ok=True)

def _require_api_key():
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None

SUPPORTED_OPERATIONS = {
    "watermark": ["text", "position", "opacity"],
    "rotate":    ["degrees"],
    "trim":      ["start", "end"],
    "resize":    ["width", "height"],
}

_jobs = {}
_jobs_lock = threading.Lock()

def _update_job(job_id, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
            _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()

def _process_job(job_id, operations):
    _update_job(job_id, status="processing", percent=0, message="Initializing workspace...")
    try:
        job_path = os.path.join(JOB_DIR, job_id)
        src_path = os.path.join(job_path, "src.mp4")
        dst_path = os.path.join(job_path, "dst.mp4")
        thumb_path = os.path.join(job_path, "thumb.jpg")

        _update_job(job_id, percent=15, message="Source loaded. Gathering metadata...")

        duration = 1.0
        try:
            probe_res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", src_path], capture_output=True, text=True)
            if probe_res.returncode == 0:
                duration = float(probe_res.stdout.strip())
        except Exception:
            pass

        _update_job(job_id, percent=20, message=f"Configuring FFmpeg for video processing (duration: {duration:.1f}s)...")

        ffmpeg_args = [
            "ffmpeg", "-y", "-i", src_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-pix_fmt", "yuv420p", "-threads", "1"
        ]

        vf = []
        for op in operations:
            op_type = op.get("type") if isinstance(op, dict) else op
            params = op.get("params", {}) if isinstance(op, dict) else {}
            
            if op_type == "rotate":
                deg = params.get("degrees", 90)
                if deg == 90: vf.append("transpose=1")
                elif deg == 180: vf.append("transpose=2,transpose=2")
                elif deg == 270: vf.append("transpose=2")
            elif op_type == "resize":
                w, h = params.get("width", -1), params.get("height", -1)
                vf.append(f"scale={w}:{h}")
            elif op_type == "watermark":
                text = params.get("text", "Universidade de Aveiro")
                vf.append(f"drawtext=text='{text}':x=10:y=H-th-10:fontsize=48:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2")

        if vf:
            ffmpeg_args.extend(["-vf", ",".join(vf)])

        ffmpeg_args.append(dst_path)

        _update_job(job_id, percent=25, message="Starting FFmpeg encoding...")
        process = subprocess.Popen(ffmpeg_args, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        last_percent = 25
        
        while True:
            reads = [process.stderr.fileno()]
            ret = select.select(reads, [], [], 1.0)
            if ret[0]:
                line = process.stderr.readline()
                if not line:
                    break
                match = time_pattern.search(line)
                if match:
                    h, m, s = match.groups()
                    cur_time = int(h) * 3600 + int(m) * 60 + float(s)
                    prog = min((cur_time / duration) * 60, 60)
                    curr_percent = int(25 + prog)
                    if curr_percent > last_percent:
                        last_percent = curr_percent
                        _update_job(job_id, percent=last_percent, message="Encoding video streams...")
            else:
                if process.poll() is not None:
                    break

        process.wait()
        if process.returncode != 0:
            raise Exception(f"FFmpeg exited with code {process.returncode}")

        _update_job(job_id, percent=90, message="FFmpeg completed successfully. Generating thumbnail...")
        try:
            subprocess.run(["ffmpeg", "-y", "-i", dst_path, "-vframes", "1", "-q:v", "2", thumb_path], check=True, capture_output=True)
        except Exception as eval_ex:
            print(f"Failed to generate thumbnail: {eval_ex}")
        
        _update_job(job_id, status="done", percent=100, message="Processing complete.")
    except Exception as exc:
        _update_job(job_id, status="failed", error_message=str(exc))

@app.route("/jobs", methods=["POST"])
def create_job():
    err = _require_api_key()
    if err: return err

    if "file" not in request.files:
        return jsonify({"error": "missing file"}), 400
        
    file = request.files["file"]
    ops_raw = request.form.get("operations")
    if not ops_raw:
        return jsonify({"error": "missing operations"}), 400
        
    try:
        operations = json.loads(ops_raw)
    except json.JSONDecodeError:
        return jsonify({"error": "operations must be valid JSON"}), 400

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()

    job_dir = os.path.join(JOB_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    file.save(os.path.join(job_dir, "src.mp4"))

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id":     job_id,
            "status":     "queued",
            "percent":    0,
            "created_at": now,
            "updated_at": now,
            "operations": operations,
        }

    t = threading.Thread(target=_process_job, args=(job_id, operations), daemon=True)
    t.start()
    return jsonify({"job_id": job_id}), 202

@app.route("/jobs/operations", methods=["GET"])
def list_operations():
    if err := _require_api_key(): return err
    return jsonify({"operations": [{"type": k, "params": v} for k, v in SUPPORTED_OPERATIONS.items()]}), 200

@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    if err := _require_api_key(): return err
    if job_id not in _jobs: return jsonify({"error": "job not found"}), 404
    return jsonify(_jobs[job_id]), 200

@app.route("/jobs/<job_id>/progress", methods=["GET"])
def job_progress_sse(job_id):
    if err := _require_api_key(): return err
    if job_id not in _jobs: return jsonify({"error": "job not found"}), 404

    def sse_generator():
        while True:
            job = _jobs.get(job_id, {})
            status, percent = job.get("status"), job.get("percent", 0)
            message, error = job.get("message", ""), job.get("error_message", "")
            data = {"job_id": job_id, "percent": percent, "status": status, "message": message}
            if error: data["error"] = error
            yield f"data: {json.dumps(data)}\n\n"
            if status in ("done", "failed"): break
            time.sleep(0.5)

    return Response(sse_generator(), mimetype="text/event-stream")

@app.route("/jobs/<job_id>/result", methods=["GET"])
def get_result(job_id):
    if err := _require_api_key(): return err
    path = os.path.join(JOB_DIR, job_id, "dst.mp4")
    if not os.path.exists(path): return jsonify({"error": "result not ready"}), 404
    return send_file(path, mimetype="video/mp4")

@app.route("/jobs/<job_id>/thumbnail", methods=["GET"])
def get_thumbnail(job_id):
    if err := _require_api_key(): return err
    path = os.path.join(JOB_DIR, job_id, "thumb.jpg")
    if not os.path.exists(path): return jsonify({"error": "result not ready"}), 404
    return send_file(path, mimetype="image/jpeg")

@app.route("/metrics", methods=["GET"])
def get_metrics():
    with _jobs_lock:
        queued = sum(1 for j in _jobs.values() if j.get("status") == "queued")
        processing = sum(1 for j in _jobs.values() if j.get("status") == "processing")
        done = sum(1 for j in _jobs.values() if j.get("status") == "done")
        failed = sum(1 for j in _jobs.values() if j.get("status") == "failed")
        cancelled = sum(1 for j in _jobs.values() if j.get("status") == "cancelled")
    
    metrics = [
        f"video_editor_jobs_total{{status=\"queued\"}} {queued}",
        f"video_editor_jobs_total{{status=\"processing\"}} {processing}",
        f"video_editor_jobs_total{{status=\"done\"}} {done}",
        f"video_editor_jobs_total{{status=\"failed\"}} {failed}",
        f"video_editor_jobs_total{{status=\"cancelled\"}} {cancelled}",
    ]
    return Response("\n".join(metrics) + "\n", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
