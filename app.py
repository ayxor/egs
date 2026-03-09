"""
Composer Service - Stub
Branch: composer

The Composer is the sole external entry point and orchestrator of the platform.
It validates JWTs and coordinates all other internal services.

Run:
    pip install flask
    python app.py
"""

from flask import Flask, request, jsonify, Response
import time
import uuid

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jwt_required():
    """Return the decoded token payload or raise a 401 response."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, (jsonify({"error": "missing or invalid Authorization header"}), 401)
    # TODO: validate JWT signature using the Keycloak public key cached at startup
    # For now, return a mock payload so the other logic can be exercised.
    mock_payload = {
        "user_id": "user-stub-001",
        "email": "professor@ua.pt",
        "role": "professor",
        "institution": "universidade-aveiro",
    }
    return mock_payload, None


def _professor_required():
    payload, err = _jwt_required()
    if err:
        return None, err
    if payload.get("role") != "professor":
        return None, (jsonify({"error": "forbidden – professor role required"}), 403)
    return payload, None


# ---------------------------------------------------------------------------
# Startup: fetch Keycloak public key
# TODO: on real startup call GET http://keycloak:8080/realms/egs/protocol/openid-connect/certs
#       and cache the public key in memory for local JWT validation.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/auth/login", methods=["POST"])
def auth_login():
    """
    Proxy login to Keycloak (grant_type: password).
    TODO: forward to POST http://keycloak:8080/realms/egs/protocol/openid-connect/token
    """
    body = request.get_json(force=True) or {}
    if not body.get("email") or not body.get("password"):
        return jsonify({"error": "email and password are required"}), 400

    # Stub response — replace with real Keycloak call
    return jsonify({
        "access_token": "stub-access-token",
        "refresh_token": "stub-refresh-token",
        "expires_in": 3600,
    }), 200


@app.route("/auth/refresh", methods=["POST"])
def auth_refresh():
    """
    Proxy token refresh to Keycloak (grant_type: refresh_token).
    TODO: forward to POST http://keycloak:8080/realms/egs/protocol/openid-connect/token
    """
    body = request.get_json(force=True) or {}
    if not body.get("refresh_token"):
        return jsonify({"error": "refresh_token is required"}), 400

    # Stub response
    return jsonify({
        "access_token": "stub-new-access-token",
        "refresh_token": "stub-new-refresh-token",
        "expires_in": 3600,
    }), 200


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.route("/users", methods=["POST"])
def register_user():
    """
    Register a new user.
    TODO:
      1. Obtain service token from Keycloak (grant_type: client_credentials)
      2. POST http://keycloak:8080/realms/egs/users  with email, password, role, institution
      3. Store user_id + name + institution in local DB
      4. POST http://notifications:8080/notifications/email  (template: welcome)
    """
    body = request.get_json(force=True) or {}
    required = ["email", "password", "name", "role", "institution"]
    for field in required:
        if not body.get(field):
            return jsonify({"error": f"missing required field: {field}"}), 400

    valid_roles = {"professor", "student"}
    if body["role"] not in valid_roles:
        return jsonify({"error": f"role must be one of {valid_roles}"}), 400

    # Stub: generate a fake user_id
    user_id = str(uuid.uuid4())

    # TODO: persist to DB and call Keycloak + Notifications

    return jsonify({"user_id": user_id}), 201


@app.route("/users/me", methods=["GET"])
def get_me():
    """Return the authenticated user's profile from the local DB."""
    payload, err = _jwt_required()
    if err:
        return err

    # TODO: look up user profile in DB using payload["user_id"]
    return jsonify({
        "user_id": payload["user_id"],
        "email": payload["email"],
        "name": "Professor Stub",
        "role": payload["role"],
        "institution": payload["institution"],
        "course": "MIECT",   # optional
    }), 200


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

@app.route("/videos", methods=["POST"])
def upload_video():
    """
    Upload a video without Video Editor processing.
    TODO:
      1. Validate JWT (professor role)
      2. PUT raw bytes to Object Storage  http://object-storage:8080/objects/{bucket}/{key}
      3. Store metadata in local DB
      4. POST http://notifications:8080/notifications/email  (template: upload_complete)
    """
    payload, err = _professor_required()
    if err:
        return err

    title = request.form.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 400

    # Stub: generate fake IDs
    video_id = str(uuid.uuid4())

    # TODO: upload file to Object Storage, persist metadata, send notification

    return jsonify({"video_id": video_id}), 201


@app.route("/videos/process", methods=["POST"])
def upload_video_with_processing():
    """
    Upload a video WITH Video Editor processing.
    Returns 202 + job_id and opens an SSE stream for progress.
    TODO:
      1. Validate JWT (professor role)
      2. PUT raw bytes to Object Storage
      3. Generate presigned GET URL (src) and PUT URL (dst) from Object Storage
      4. POST http://video-editor:8080/jobs  with src_url, dst_url, progress_url, operations
      5. Subscribe to Video Editor SSE and relay progress to client
      6. On done: persist metadata + send notification
    """
    payload, err = _professor_required()
    if err:
        return err

    title = request.form.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not request.form.get("operations"):
        return jsonify({"error": "operations is required"}), 400

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 400

    job_id = str(uuid.uuid4())

    # Stub SSE stream — replace with real relay from Video Editor
    def sse_stream():
        for percent in [0, 25, 50, 75, 100]:
            event = f'data: {{"job_id": "{job_id}", "percent": {percent}, "status": "{"done" if percent == 100 else "processing"}"}}\n\n'
            yield event
            time.sleep(0.5)
        # On completion include video_id
        video_id = str(uuid.uuid4())
        yield f'data: {{"job_id": "{job_id}", "percent": 100, "status": "done", "video_id": "{video_id}"}}\n\n'

    return Response(sse_stream(), status=202, mimetype="text/event-stream")


@app.route("/videos", methods=["GET"])
def list_videos():
    """
    List/search videos scoped to the authenticated user's institution.
    Query params: q, course, subject, limit (default 25), offset (default 0)
    TODO: SELECT from DB WHERE institution = ? AND (title ILIKE ? OR ...)
    """
    payload, err = _jwt_required()
    if err:
        return err

    q       = request.args.get("q", "")
    course  = request.args.get("course", "")
    subject = request.args.get("subject", "")
    limit   = int(request.args.get("limit", 25))
    offset  = int(request.args.get("offset", 0))

    # Stub response
    return jsonify({
        "total": 0,
        "limit": limit,
        "offset": offset,
        "results": [],
    }), 200


@app.route("/videos/<video_id>", methods=["GET"])
def get_video(video_id):
    """
    Return video metadata + a temporary presigned streaming URL.
    TODO:
      1. Validate JWT; check institution matches video's institution
      2. Generate presigned GET URL from Object Storage
    """
    payload, err = _jwt_required()
    if err:
        return err

    # TODO: fetch from DB; 404 if not found; 403 if different institution
    return jsonify({
        "video_id": video_id,
        "title": "Stub Video",
        "description": "Stub description",
        "tags": [],
        "course": "MIECT",
        "subject": "LSD",
        "uploader_id": "user-stub-001",
        "created_at": "2024-03-01T10:00:00Z",
        "stream_url": f"http://object-storage:8080/objects/universidade-aveiro/raw/{video_id}.mp4?token=stub",
    }), 200


@app.route("/videos/<video_id>", methods=["DELETE"])
def delete_video(video_id):
    """
    Delete a video. Only the uploader may delete.
    TODO:
      1. Validate JWT
      2. Check uploader_id == payload["user_id"]
      3. DELETE object from Object Storage
      4. Remove metadata from DB
    """
    payload, err = _jwt_required()
    if err:
        return err

    # TODO: check ownership; delete from Object Storage and DB
    return "", 204


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
