"""
Video Editor Service - Stub
Branch: video-editor

Generic, asynchronous media processing service.
Receives a source file via URL, applies operations, and delivers the result
to a destination URL.
Accessible only by internal services via API key.

Run:
    pip install -r requirements.txt
    python app.py
"""

from datetime import datetime, timezone
import json
import os
import threading
import time
import uuid

from flask import Flask, Response, jsonify, request

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
# ---------------------------------------------------------------------------

SUPPORTED_OPERATIONS: dict[str, list[str]] = {
    "watermark": ["text", "position", "opacity"],
    "rotate": ["degrees"],
    "trim": ["start", "end"],
    "resize": ["width", "height"],
}


# ---------------------------------------------------------------------------
# In-memory job store
# Structure: {
#   job_id: {
#     status, percent, created_at, updated_at, operations,
#     generation, cancel_requested
#   }
# }
# ---------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_job_payload(body: dict):
    for field in ("src_url", "dst_url", "operations"):
        if not body.get(field):
            return None, (jsonify({"error": f"missing required field: {field}"}), 400)

    operations = body["operations"]
    if not isinstance(operations, list) or len(operations) == 0:
        return None, (jsonify({"error": "operations must be a non-empty list"}), 400)

    for op in operations:
        op_type = op.get("type") if isinstance(op, dict) else op
        if op_type not in SUPPORTED_OPERATIONS:
            return None, (jsonify({"error": f"unknown operation: {op_type}"}), 422)

    return operations, None


def _update_job_if_active(job_id: str, generation: int, **kwargs) -> bool:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job or job.get("generation") != generation:
            return False

        if job.get("cancel_requested"):
            job["status"] = "cancelled"
            job["updated_at"] = _utc_now_iso()
            return False

        job.update(kwargs)
        job["updated_at"] = _utc_now_iso()
        return True


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return dict(job)


def _create_or_replace_job(job_id: str, body: dict) -> None:
    now = _utc_now_iso()

    with _jobs_lock:
        previous = _jobs.get(job_id)
        generation = (previous.get("generation", 0) + 1) if previous else 1

        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "percent": 0,
            "created_at": now,
            "updated_at": now,
            "operations": body["operations"],
            "generation": generation,
            "cancel_requested": False,
        }

    worker = threading.Thread(
        target=_process_job,
        args=(
            job_id,
            generation,
            body["src_url"],
            body["dst_url"],
            body.get("progress_url"),
            body["operations"],
        ),
        daemon=True,
    )
    worker.start()


def _process_job(
    job_id: str,
    generation: int,
    src_url: str,
    dst_url: str,
    progress_url: str | None,
    operations: list,
):
    """
    Background thread that simulates processing.
    TODO:
      1. GET src_url and download bytes
      2. Apply each operation with FFmpeg (or similar)
      3. Notify progress_url if provided
      4. PUT output bytes into dst_url
    """
    _ = src_url
    _ = dst_url
    _ = progress_url

    if not _update_job_if_active(job_id, generation, status="processing", percent=0):
        return

    try:
        time.sleep(0.5)
        if not _update_job_if_active(job_id, generation, percent=10):
            return

        steps = len(operations) if operations else 1
        for index, op in enumerate(operations, start=1):
            op_type = op.get("type") if isinstance(op, dict) else op
            print(f"[STUB] job={job_id} applying operation: {op_type}")
            time.sleep(1)
            percent = 10 + int((index / steps) * 80)
            if not _update_job_if_active(job_id, generation, percent=percent):
                return

        time.sleep(0.5)
        _update_job_if_active(job_id, generation, status="done", percent=100)

    except Exception as exc:
        print(f"[STUB] job={job_id} failed: {exc}")
        _update_job_if_active(job_id, generation, status="failed")


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.route("/jobs", methods=["POST"])
def create_job():
    err = _require_api_key()
    if err:
        return err

    body = request.get_json(force=True, silent=True) or {}
    _, validation_error = _validate_job_payload(body)
    if validation_error:
        return validation_error

    job_id = f"job_{uuid.uuid4().hex[:6]}"
    _create_or_replace_job(job_id, body)
    return jsonify({"job_id": job_id}), 202


@app.route("/jobs/<job_id>", methods=["PUT"])
def upsert_job(job_id):
    err = _require_api_key()
    if err:
        return err

    body = request.get_json(force=True, silent=True) or {}
    _, validation_error = _validate_job_payload(body)
    if validation_error:
        return validation_error

    _create_or_replace_job(job_id, body)
    return jsonify({"job_id": job_id}), 202


@app.route("/jobs/<job_id>", methods=["DELETE"])
def cancel_job(job_id):
    err = _require_api_key()
    if err:
        return err

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404

        if job["status"] not in ("done", "failed", "cancelled"):
            job["cancel_requested"] = True
            job["status"] = "cancelled"
            job["updated_at"] = _utc_now_iso()

    return "", 204


@app.route("/jobs/operations", methods=["GET"])
def list_operations():
    err = _require_api_key()
    if err:
        return err

    operations = [
        {"type": op_type, "params": params}
        for op_type, params in SUPPORTED_OPERATIONS.items()
    ]
    return jsonify({"operations": operations}), 200


@app.route("/jobs/<job_id>", methods=["GET"])
def get_job(job_id):
    err = _require_api_key()
    if err:
        return err

    job = _get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404

    return (
        jsonify(
            {
                "job_id": job["job_id"],
                "status": job["status"],
                "percent": job["percent"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
            }
        ),
        200,
    )


@app.route("/jobs/<job_id>/progress", methods=["GET"])
def job_progress_sse(job_id):
    err = _require_api_key()
    if err:
        return err

    if not _get_job(job_id):
        return jsonify({"error": "job not found"}), 404

    def sse_generator():
        while True:
            job = _get_job(job_id)
            if not job:
                break

            payload = {
                "job_id": job_id,
                "percent": job.get("percent", 0),
                "status": job.get("status", "unknown"),
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if payload["status"] in ("done", "failed", "cancelled"):
                break

            time.sleep(0.5)

    return Response(
        sse_generator(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.route("/jobs/<job_id>/operations", methods=["GET"])
def get_job_operations(job_id):
    err = _require_api_key()
    if err:
        return err

    job = _get_job(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404

    return jsonify({"operations": job["operations"]}), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
