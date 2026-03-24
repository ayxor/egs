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

from flask import Flask, request, jsonify, Response, make_response
from flask_cors import CORS
from urllib.parse import quote
from datetime import datetime, timedelta, timezone

import mimetypes
import os

app = Flask(__name__)
CORS(app)


@app.before_request
def _handle_cors_preflight():
    # Allow browser preflight requests for cross-origin API usage.
    if request.method == "OPTIONS":
        response = make_response("", 204)
        return _apply_cors_headers(response)
    return None


@app.after_request
def _cors_after_request(response):
    return _apply_cors_headers(response)


def _apply_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,X-API-Key,Range"
    response.headers["Access-Control-Expose-Headers"] = "Content-Range,Accept-Ranges"
    return response

# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("OBJECT_STORAGE_API_KEY", "stub-api-key")

def _require_api_key():
    token = request.args.get("token")
    if token == "stub-presign":
        # Allow requests with valid presigned tokens
        expires = request.args.get("expires")
        if expires and int(expires) > int(datetime.now(timezone.utc).timestamp()):
            return None
        return jsonify({"error": "presigned token expired"}), 403

    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


def _sanitize_key(key):
    key = (key or "").strip().replace("\\", "/").lstrip("/")
    if not key:
        return ""
    # prevent path traversal
    if ".." in key.split("/"):
        return ""
    return key


# ---------------------------------------------------------------------------
# Storage Backend
# We are currently using the local file system as the database/store
# Structure: ./data/{bucket}/{key}
# ---------------------------------------------------------------------------
DATA_DIR = os.environ.get("OBJECT_STORAGE_DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Buckets
# ---------------------------------------------------------------------------

@app.route("/buckets", methods=["GET"])
def list_buckets():
    """
    List all namespaces (buckets) with pagination.
    Query args: limit (default 50), offset (default 0), query (default empty)
    """
    err = _require_api_key()
    if err:
        return err

    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid limit or offset"}), 400

    query = request.args.get("query", "").lower()

    try:
        # List all directory names in `DATA_DIR`
        existing_buckets = [name for name in os.listdir(DATA_DIR) if os.path.isdir(os.path.join(DATA_DIR, name))]
    except FileNotFoundError:
        existing_buckets = []

    all_buckets = [b for b in existing_buckets if query in b.lower()]
    total = len(all_buckets)
    buckets_page = all_buckets[offset:offset + limit]

    return jsonify({
        "buckets": buckets_page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "query": query
    }), 200


@app.route("/buckets/<bucket>", methods=["PUT"])
def create_bucket(bucket):
    """
    Create a new namespace (bucket) physically as a folder in the file system.
    """
    err = _require_api_key()
    if err:
        return err

    bucket_path = os.path.join(DATA_DIR, bucket)

    if os.path.exists(bucket_path):
        return jsonify({"error": "bucket already exists"}), 409

    try:
        os.makedirs(bucket_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"bucket": bucket}), 201


@app.route("/buckets/<bucket>", methods=["DELETE"])
def delete_bucket(bucket):
    """
    Delete a bucket and all its contents by recursively removing the directory.
    """
    import shutil
    err = _require_api_key()
    if err:
        return err

    bucket_path = os.path.join(DATA_DIR, bucket)
    if not os.path.exists(bucket_path):
        return jsonify({"error": "bucket not found"}), 404

    try:
        shutil.rmtree(bucket_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return "", 204


# ---------------------------------------------------------------------------
# Objects
# ---------------------------------------------------------------------------

@app.route("/objects/<bucket>", methods=["GET"])
def list_objects(bucket):
    """
    List all object keys in a given bucket with pagination and search.
    Query args: limit (default 50), offset (default 0), query (default empty)
    """
    err = _require_api_key()
    if err:
        return err

    if not os.path.exists(os.path.join(DATA_DIR, bucket)):
        return jsonify({"error": "bucket not found"}), 404

    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "invalid limit or offset"}), 400

    query = request.args.get("query", "").lower()

    bucket_path = os.path.join(DATA_DIR, bucket)
    existing_objects = []
    for root, dirs, files in os.walk(bucket_path):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, bucket_path)
            existing_objects.append(rel_path.replace("\\", "/"))

    all_objects = [k for k in existing_objects if query in k.lower()]
    total = len(all_objects)
    objects_page = all_objects[offset:offset + limit]

    return jsonify({
        "objects": objects_page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "query": query
    }), 200


@app.route("/objects/<bucket>", methods=["PUT"])
@app.route("/objects/<bucket>/<path:key>", methods=["PUT"])
def upload_object(bucket, key=None):
    """
    Store a binary object under bucket/key.
    Key is provided via query param ?key=<object-key>
    or header X-Object-Key.
    Body: raw bytes (Content-Type: application/octet-stream).
    Currently writes to local file system.
    """
    err = _require_api_key()
    if err:
        return err

    if not key:
        key = _sanitize_key(request.args.get("key") or request.headers.get("X-Object-Key"))
    else:
        key = _sanitize_key(key)
        
    if not bucket or not key:
        return jsonify({"error": "invalid bucket or key"}), 400

    bucket_path = os.path.join(DATA_DIR, bucket)
    # Auto-create bucket if it doesn't exist (lenient for stub)
    os.makedirs(bucket_path, exist_ok=True)

    data = request.get_data()
    file_path = os.path.join(bucket_path, key)

    # Create any nested directories for the key itself
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(data)

    return jsonify({"bucket": bucket, "key": key}), 201


@app.route("/objects/<bucket>/<path:key>", methods=["GET"])
def download_object(bucket, key):
    """
    Return the raw bytes of a stored object from the file system.
    Supports optional HTTP Range header for partial content (e.g. video streaming).
    """
    err = _require_api_key()
    if err:
        return err

    file_path = os.path.join(DATA_DIR, bucket, key)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return jsonify({"error": "bucket or key not found"}), 404

    range_header = request.headers.get("Range")
    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    if range_header:
        # Basic Range support: bytes=start-end
        try:
            range_spec = range_header.replace("bytes=", "")
            start_str, end_str = range_spec.split("-")
            start = int(start_str)
            end   = int(end_str) if end_str else file_size - 1

            with open(file_path, "rb") as f:
                f.seek(start)
                chunk = f.read(end - start + 1)

            return Response(
                chunk,
                status=206,
                mimetype=content_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(len(chunk)),
                },
            )
        except Exception:
            return jsonify({"error": "invalid Range header"}), 400

    def generate():
        with open(file_path, "rb") as f:
            while chunk := f.read(4096):
                yield chunk

    return Response(
        generate(),
        status=200,
        mimetype=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@app.route("/objects/<bucket>", methods=["DELETE"])
def delete_object_by_query(bucket):
    """
    Remove an object by query string key.
    Example: DELETE /objects/my-bucket?key=path/file.bin
    """
    key = _sanitize_key(request.args.get("key"))
    if not key:
        return jsonify({"error": "invalid bucket or key"}), 400
    return _delete_object(bucket, key)


@app.route("/objects/<bucket>/<path:key>", methods=["DELETE"])
def delete_object(bucket, key):
    """
    Remove an object from the given bucket.
    """
    return _delete_object(bucket, key)


def _delete_object(bucket, key):
    err = _require_api_key()
    if err:
        return err

    key = _sanitize_key(key)
    if not key:
        return jsonify({"error": "invalid bucket or key"}), 400

    file_path = os.path.join(DATA_DIR, bucket, key)
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return jsonify({"error": "bucket or key not found"}), 404

    try:
        os.remove(file_path)

        # Cleanup empty parent directories
        directory = os.path.dirname(file_path)
        bucket_path = os.path.join(DATA_DIR, bucket)
        while directory != bucket_path:
            if not os.listdir(directory):
                os.rmdir(directory)
                directory = os.path.dirname(directory)
            else:
                break

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return "", 204


# ---------------------------------------------------------------------------
@app.route("/objects/<bucket>/<path:key>/presign", methods=["POST"])
def presign(bucket, key):
    method = request.json.get("method", "GET")
    expires_in = request.json.get("expires_in", 3600)  # seconds
    
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    
    url = (
        f"http://object-storage:8080/objects/{quote(bucket)}/{quote(key)}"
        f"?token=stub-presign&method={method}&expires={int(expires_at.timestamp())}"
    )
    
    return jsonify({
        "url": url,
        "expires_at": expires_at.isoformat()
    }), 200

# Entry point

# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
