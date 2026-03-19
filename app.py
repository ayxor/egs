"""
Video Editor Service - Stub
Branch: video-editor

Generic, asynchronous media processing service.
Receives a source file upload, applies operations, and delivers the result
to a destination URL.
Accessible only by internal services via API key.

Run:
    pip install -r requirements.txt
    python app.py
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
import threading
import time
import uuid

from flask import Flask, jsonify, request

app = Flask(__name__)


# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("VIDEO_EDITOR_API_KEY", "stub-api-key")
DB_PATH = os.environ.get("VIDEO_EDITOR_DB_PATH", "video_editor.db")
_db_init_error: str | None = None


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


def _parse_operations(raw_operations):
    operations = raw_operations

    if isinstance(raw_operations, str):
        try:
            operations = json.loads(raw_operations)
        except json.JSONDecodeError:
            return None, (jsonify({"error": "operations must be valid JSON"}), 400)

    if not isinstance(operations, list) or len(operations) == 0:
        return None, (jsonify({"error": "operations must be a non-empty list"}), 400)

    for op in operations:
        op_type = op.get("type") if isinstance(op, dict) else op
        if op_type not in SUPPORTED_OPERATIONS:
            return None, (jsonify({"error": f"unknown operation: {op_type}"}), 422)

    return operations, None


def _validate_job_payload(body: dict, *, require_src_url: bool = True):
    required_fields = ["dst_url", "operations"]
    if require_src_url:
        required_fields.insert(0, "src_url")

    for field in required_fields:
        if not body.get(field):
            return None, (jsonify({"error": f"missing required field: {field}"}), 400)

    operations, parse_error = _parse_operations(body.get("operations"))
    if parse_error:
        return None, parse_error

    validated_body = dict(body)
    validated_body["operations"] = operations

    return validated_body, None


def _build_post_job_payload_from_multipart():
    if not request.mimetype or not request.mimetype.startswith("multipart/form-data"):
        return None, (
            jsonify({"error": "POST /jobs must use multipart/form-data"}),
            400,
        )

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return None, (jsonify({"error": "missing required field: file"}), 400)

    body = {
        "src_url": f"upload://{uploaded_file.filename}",
        "dst_url": request.form.get("dst_url"),
        "progress_url": request.form.get("progress_url"),
        "operations": request.form.get("operations"),
        "source_file_name": uploaded_file.filename,
        "source_file_mime_type": uploaded_file.mimetype or "application/octet-stream",
    }

    return _validate_job_payload(body, require_src_url=True)


def _update_job_if_active(job_id: str, generation: int, **kwargs) -> bool:
    should_continue = True

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job or job.get("generation") != generation:
            return False

        if job.get("cancel_requested"):
            job["status"] = "cancelled"
            job["updated_at"] = _utc_now_iso()
            should_continue = False
        else:
            job.update(kwargs)
            job["updated_at"] = _utc_now_iso()

    return should_continue


def _get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return dict(job)


def _create_or_replace_job(job_id: str, body: dict) -> None:
    now = _utc_now_iso()
    source_ref = body.get("source_file_name") or body["src_url"]

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
            "source_ref": source_ref,
            "source_file_name": body.get("source_file_name"),
            "source_file_mime_type": body.get("source_file_mime_type"),
            "generation": generation,
            "cancel_requested": False,
        }

    worker = threading.Thread(
        target=_process_job,
        args=(
            job_id,
            generation,
            source_ref,
            body["dst_url"],
            body.get("progress_url"),
            body["operations"],
        ),
        daemon=True,
    )
    worker.start()


def _init_db() -> None:
    """Initialize tiny SQLite table for service metadata."""
    global _db_init_error

    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS service_meta (
                    k TEXT PRIMARY KEY,
                    v TEXT NOT NULL
                )
                """
            )

            conn.execute(
                "INSERT OR IGNORE INTO service_meta (k, v) VALUES (?, ?)",
                ("service", "video-editor"),
            )
            conn.execute(
                "INSERT OR IGNORE INTO service_meta (k, v) VALUES (?, ?)",
                ("initialized_at", _utc_now_iso()),
            )
            conn.commit()
    except sqlite3.Error as exc:
        _db_init_error = str(exc)


def _process_job(
    job_id: str,
    generation: int,
    source_ref: str,
    dst_url: str,
    progress_url: str | None,
    operations: list,
):
    """
    Background thread that simulates processing.
    TODO:
      1. Load uploaded file bytes from source_ref
      2. Apply each operation with FFmpeg (or similar)
      3. Notify progress_url if provided
      4. PUT output bytes into dst_url
    """
    _ = source_ref
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

_init_db()


@app.route("/", methods=["GET"])
def frontend_demo():
    return app.send_static_file("index.html")

@app.route("/jobs", methods=["POST"])
def create_job():
    err = _require_api_key()
    if err:
        return err

    body, validation_error = _build_post_job_payload_from_multipart()
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
    body, validation_error = _validate_job_payload(body, require_src_url=True)
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


@app.route("/db/status", methods=["GET"])
def db_status():
    err = _require_api_key()
    if err:
        return err

    if _db_init_error:
        return jsonify({"error": "database unavailable", "details": _db_init_error}), 500

    try:
        with sqlite3.connect(DB_PATH) as conn:
            meta_row = conn.execute("SELECT COUNT(*) FROM service_meta").fetchone()
            meta_entries = meta_row[0] if meta_row else 0
    except sqlite3.Error as exc:
        return jsonify({"error": "database unavailable", "details": str(exc)}), 500

    return (
        jsonify(
            {
                "database": "sqlite",
                "status": "ok",
                "path": DB_PATH,
                "meta_entries": meta_entries,
            }
        ),
        200,
    )


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
                "progress": {"percent": job["percent"]},
                "operations": job["operations"],
                "source_ref": job["source_ref"],
                "source_file_name": job.get("source_file_name"),
                "source_file_mime_type": job.get("source_file_mime_type"),
                "created_at": job["created_at"],
                "updated_at": job["updated_at"],
            }
        ),
        200,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
