"""
Video Editor Service - Stub
Branch: video-editor

Generic, asynchronous media processing service.
Receives a source file via URL, applies operations, delivers result to a destination URL.
Completely agnostic to business logic — all URLs are supplied by the Composer.
Accessible only by internal services via API key.

Run:
    pip install flask
    python app.py
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from datetime import datetime, timezone
import threading
import time
import uuid
import os
import json

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("VIDEO_EDITOR_API_KEY", "stub-api-key")

def _require_api_key():
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# Supported operations registry
# TODO: implement real processing with FFmpeg (or similar).
# ---------------------------------------------------------------------------

SUPPORTED_OPERATIONS: dict[str, list[str]] = {
    "watermark": ["text", "position", "opacity"],
    "rotate":    ["degrees"],
    "trim":      ["start", "end"],
    "resize":    ["width", "height"],
}


# ---------------------------------------------------------------------------
# In-memory job store
# Structure: { job_id: { status, percent, created_at, updated_at, operations } }
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _update_job(job_id: str, progress_url: str | None, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
            _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # If progress_url is provided, push update to Composer
            if progress_url:
                _push_progress(job_id, progress_url, _jobs[job_id])


def _push_progress(job_id: str, progress_url: str, job_data: dict):
    """Notify the Composer about the job progress via webhook."""
    import urllib.request
    try:
        data = json.dumps({
            "job_id": job_id,
            "status": job_data.get("status", "unknown"),
            "percent": job_data.get("percent", 0),
            "message": job_data.get("message", ""),
            "error": job_data.get("error_message", "")
        }).encode("utf-8")
        req = urllib.request.Request(progress_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
    except Exception as exc:
        print(f"[STUB] Failed to push progress to {progress_url}: {exc}")


def _process_job(job_id: str, src_url: str, dst_url: str, progress_url: str | None, operations: list):
    """
    Background thread that processes video using FFmpeg.
    """
    import urllib.request
    import urllib.error
    import subprocess
    import tempfile
    import re
    import select

    _update_job(job_id, progress_url, status="processing", percent=0, message="Initializing workspace...")

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "src.video")
            dst_path = os.path.join(tmpdir, "dst.mp4")

            # --- Step 1: fetch source ---
            print(f"[EDITOR] job={job_id} downloading from {src_url}", flush=True)
            _update_job(job_id, progress_url, percent=5, message=f"Downloading source video from object storage...")
            req = urllib.request.Request(src_url, method="GET")
            try:
                with urllib.request.urlopen(req) as resp:
                    with open(src_path, "wb") as f:
                        f.write(resp.read())
            except urllib.error.URLError as e:
                raise Exception(f"Failed to communicate with Composer/Storage at {src_url}: {e}")
            
            _update_job(job_id, progress_url, percent=15, message="Source downloaded. Gathering metadata...")

            # Calculate duration
            duration = 1.0
            try:
                probe_res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", src_path], capture_output=True, text=True)
                if probe_res.returncode == 0:
                    duration = float(probe_res.stdout.strip())
            except Exception:
                pass

            _update_job(job_id, progress_url, percent=20, message=f"Configuring FFmpeg for video processing (duration: {duration:.1f}s)...")

            # --- Step 2: process operations with FFmpeg ---
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

            print(f"[EDITOR] job={job_id} running ffmpeg: {' '.join(ffmpeg_args)}", flush=True)
            _update_job(job_id, progress_url, percent=25, message="Starting FFmpeg encoding...")
            
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
                            _update_job(job_id, progress_url, percent=last_percent, message="Encoding video streams...")
                else:
                    if process.poll() is not None:
                        break

            process.wait()
            if process.returncode != 0:
                raise Exception(f"FFmpeg exited with code {process.returncode}")

            _update_job(job_id, progress_url, percent=90, message="FFmpeg completed successfully. Uploading output...")

            # --- Step 3: deliver result ---
            print(f"[EDITOR] job={job_id} uploading to {dst_url}", flush=True)
            with open(dst_path, "rb") as f:
                video_bytes = f.read()
                
            req = urllib.request.Request(dst_url, data=video_bytes, method="PUT")
            req.add_header("Content-Type", "video/mp4")
            with urllib.request.urlopen(req) as resp:
                pass
            
            _update_job(job_id, progress_url, status="done", percent=100, message="Upload complete, job finished.")

    except Exception as exc:
        print(f"[EDITOR] job={job_id} failed: {exc}")
        _update_job(job_id, progress_url, status="failed", error_message=str(exc))


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.route("/jobs", methods=["POST"])
def create_job():
    """
    Create and start a processing job asynchronously.
    Returns immediately with a job_id.
    TODO: validate operations against SUPPORTED_OPERATIONS; implement _process_job.
    """
    err = _require_api_key()
    if err:
        return err

    body = request.get_json(force=True) or {}
    for field in ("src_url", "dst_url", "operations"):
        if not body.get(field):
            return jsonify({"error": f"missing required field: {field}"}), 400

    operations = body["operations"]
    if not isinstance(operations, list) or len(operations) == 0:
        return jsonify({"error": "operations must be a non-empty list"}), 400

    # Validate operation types
    for op in operations:
        op_type = op.get("type") if isinstance(op, dict) else op
        if op_type not in SUPPORTED_OPERATIONS:
            return jsonify({"error": f"unknown operation: {op_type}"}), 422

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc).isoformat()

    with _jobs_lock:
        _jobs[job_id] = {
            "job_id":     job_id,
            "status":     "queued",
            "percent":    0,
            "created_at": now,
            "updated_at": now,
            "operations": operations,
        }

    # Start processing in background thread
    t = threading.Thread(
        target=_process_job,
        args=(job_id, body["src_url"], body["dst_url"], body.get("progress_url"), operations),
        daemon=True,
    )
    t.start()

    return jsonify({"job_id": job_id}), 202


@app.route("/jobs/operations", methods=["GET"])
def list_operations():
    """Return all operations supported by this service instance."""
    err = _require_api_key()
    if err:
        return err

    ops = [
        {"type": op_type, "params": params}
        for op_type, params in SUPPORTED_OPERATIONS.items()
    ]
    return jsonify({"operations": ops}), 200


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    """
    Return the current status and progress of a job.
    Alternative to SSE for contexts where streaming is not viable.
    """
    err = _require_api_key()
    if err:
        return err

    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "job_id not found"}), 404

    return jsonify({
        "job_id":     job["job_id"],
        "status":     job["status"],
        "percent":    job["percent"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "error_message": job.get("error_message", ""),
    }), 200


@app.route("/jobs/<job_id>/progress", methods=["GET"])
def job_progress_sse(job_id):
    """
    Stream real-time job progress via Server-Sent Events.
    The Composer subscribes to this stream and relays progress to the client.
    Stream closes automatically when the job reaches 'done' or 'failed'.
    """
    err = _require_api_key()
    if err:
        return err

    if job_id not in _jobs:
        return jsonify({"error": "job_id not found"}), 404

    def sse_generator():
        while True:
            job = _jobs.get(job_id, {})
            status  = job.get("status", "unknown")
            percent = job.get("percent", 0)
            message = job.get("message", "")
            error_msg = job.get("error_message", "")
            
            import json
            data = {"job_id": job_id, "percent": percent, "status": status, "message": message}
            if error_msg:
                data["error"] = error_msg
                
            yield f"data: {json.dumps(data)}\n\n"
            if status in ("done", "failed"):
                break
            time.sleep(0.5)

    return Response(sse_generator(), mimetype="text/event-stream")


@app.route("/jobs/<job_id>/operations", methods=["GET"])
def get_job_operations(job_id):
    """Return the operations that were requested for a specific job."""
    err = _require_api_key()
    if err:
        return err

    job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404

    return jsonify({"operations": job["operations"]}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
