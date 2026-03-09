"""
Object Storage Service - Stub
Branch: object-storage

Generic binary file store. Agnostic to content type.
Accepts, serves, and generates presigned URLs for arbitrary binary objects.
Accessible only by internal services (Composer, Video Editor) via API key.

Run:
    pip install flask
    python app.py
"""

from flask import Flask, request, jsonify, Response
from datetime import datetime, timedelta, timezone
import os

app = Flask(__name__)

# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("OBJECT_STORAGE_API_KEY", "stub-api-key")

def _require_api_key():
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# In-memory store (replace with real storage backend)
# Structure: { bucket: { key: bytes } }
# ---------------------------------------------------------------------------
_store: dict[str, dict[str, bytes]] = {}


# ---------------------------------------------------------------------------
# Buckets
# ---------------------------------------------------------------------------

@app.route("/buckets/<bucket>", methods=["PUT"])
def create_bucket(bucket):
    """
    Create a new namespace (bucket).
    TODO: create the bucket in the real storage backend (e.g. MinIO, S3, local FS).
    """
    err = _require_api_key()
    if err:
        return err

    if bucket in _store:
        return jsonify({"error": "bucket already exists"}), 409

    _store[bucket] = {}
    return jsonify({"bucket": bucket}), 201


@app.route("/buckets/<bucket>", methods=["DELETE"])
def delete_bucket(bucket):
    """
    Delete a bucket and all its contents.
    TODO: delete from real storage backend.
    """
    err = _require_api_key()
    if err:
        return err

    if bucket not in _store:
        return jsonify({"error": "bucket not found"}), 404

    del _store[bucket]
    return "", 204


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

@app.route("/objects/<bucket>/<path:key>", methods=["PUT"])
def upload_object(bucket, key):
    """
    Store a binary object under bucket/key.
    Body: raw bytes (Content-Type: application/octet-stream).
    TODO: write to real storage backend.
    """
    err = _require_api_key()
    if err:
        return err

    if not bucket or not key:
        return jsonify({"error": "invalid bucket or key"}), 400

    # Auto-create bucket if it doesn't exist (lenient for stub)
    if bucket not in _store:
        _store[bucket] = {}

    data = request.get_data()
    _store[bucket][key] = data
    return jsonify({"bucket": bucket, "key": key}), 201


@app.route("/objects/<bucket>/<path:key>", methods=["GET"])
def download_object(bucket, key):
    """
    Return the raw bytes of a stored object.
    Supports optional HTTP Range header for partial content (e.g. video streaming).
    TODO: stream from real storage backend; honour Range header natively.
    """
    err = _require_api_key()
    if err:
        return err

    if bucket not in _store or key not in _store[bucket]:
        return jsonify({"error": "bucket or key not found"}), 404

    data = _store[bucket][key]
    range_header = request.headers.get("Range")

    if range_header:
        # Basic Range support: bytes=start-end
        try:
            range_spec = range_header.replace("bytes=", "")
            start_str, end_str = range_spec.split("-")
            start = int(start_str)
            end   = int(end_str) if end_str else len(data) - 1
            chunk = data[start:end + 1]
            return Response(
                chunk,
                status=206,
                mimetype="application/octet-stream",
                headers={
                    "Content-Range": f"bytes {start}-{end}/{len(data)}",
                    "Accept-Ranges": "bytes",
                },
            )
        except Exception:
            return jsonify({"error": "invalid Range header"}), 400

    return Response(data, status=200, mimetype="application/octet-stream")


@app.route("/objects/<bucket>/<path:key>", methods=["DELETE"])
def delete_object(bucket, key):
    """
    Remove an object from the given bucket.
    TODO: delete from real storage backend.
    """
    err = _require_api_key()
    if err:
        return err

    if bucket not in _store or key not in _store[bucket]:
        return jsonify({"error": "bucket or key not found"}), 404

    del _store[bucket][key]
    return "", 204


# ---------------------------------------------------------------------------
# Presigned URLs
# ---------------------------------------------------------------------------

@app.route("/objects/<bucket>/<path:key>/presign", methods=["POST"])
def presign(bucket, key):
    """
    Generate a temporary, scoped URL for direct access to an object.
    method: GET (download) | PUT (upload — used by Composer to give Video Editor a dst_url)
    TODO: generate a real signed URL using HMAC or the storage backend's presign API.
    """
    err = _require_api_key()
    if err:
        return err

    if bucket not in _store:
        return jsonify({"error": "bucket or key not found"}), 404

    body = request.get_json(force=True) or {}
    method = body.get("method", "").upper()
    expires_in = body.get("expires_in", 3600)

    if method not in ("GET", "PUT"):
        return jsonify({"error": "method must be GET or PUT"}), 400

    # For GET presigns the object must already exist.
    # For PUT presigns the object may not exist yet — that is the intended use case.
    if method == "GET" and key not in _store[bucket]:
        return jsonify({"error": "bucket or key not found"}), 404

    # Stub: build a fake presigned URL
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    url = (
        f"http://object-storage:8080/objects/{bucket}/{key}"
        f"?token=stub-presign&method={method}&expires={int(expires_at.timestamp())}"
    )

    return jsonify({
        "url": url,
        "expires_at": expires_at.isoformat(),
    }), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
