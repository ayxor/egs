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
from datetime import datetime, timezone
import threading
import time
import uuid
import os

app = Flask(__name__)

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


def _update_job(job_id: str, **kwargs):
    with _jobs_lock:
        _jobs[job_id].update(kwargs)
        _jobs[job_id]["updated_at"] = datetime.now(timezone.utc).isoformat()


def _process_job(job_id: str, src_url: str, dst_url: str, progress_url: str | None, operations: list):
    """
    Background thread that simulates processing.
    TODO:
      1. GET src_url  → download source bytes
      2. Apply each operation with FFmpeg (or another library)
      3. POST progress updates to progress_url via SSE
      4. PUT dst_url  → upload processed bytes
    """
    import urllib.request

    _update_job(job_id, status="processing", percent=0)

    try:
        # --- Step 1: fetch source ---
        # TODO: replace stub sleep with real download
        time.sleep(0.5)
        _update_job(job_id, percent=10)

        # --- Step 2: process operations ---
        steps = len(operations) if operations else 1
        for i, op in enumerate(operations, start=1):
            op_type = op.get("type") if isinstance(op, dict) else op
            print(f"[STUB] job={job_id} applying operation: {op_type}")
            # TODO: invoke FFmpeg or processing library here
            time.sleep(1)
            percent = 10 + int((i / steps) * 80)
            _update_job(job_id, percent=percent)

        # --- Step 3: deliver result ---
        # TODO: PUT processed bytes to dst_url
        time.sleep(0.5)
        _update_job(job_id, status="done", percent=100)

    except Exception as exc:
        print(f"[STUB] job={job_id} failed: {exc}")
        _update_job(job_id, status="failed", percent=_jobs[job_id]["percent"])


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
        return jsonify({"error": "job not found"}), 404

    return jsonify({
        "job_id":     job["job_id"],
        "status":     job["status"],
        "percent":    job["percent"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
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
        return jsonify({"error": "job not found"}), 404

    def sse_generator():
        while True:
            job = _jobs.get(job_id, {})
            status  = job.get("status", "unknown")
            percent = job.get("percent", 0)
            yield f'data: {{"job_id": "{job_id}", "percent": {percent}, "status": "{status}"}}\n\n'
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
