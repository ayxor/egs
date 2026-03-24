"""
Composer Service — UAStream Platform

Central orchestrator and sole external API entry point.
Validates JWTs against Keycloak and coordinates all internal services
(Object Storage, Video Editor, Notifications).

Run (dev):
    pip install -r requirements.txt
    python app.py
"""

import json
import uuid
import logging
import re
import os
from urllib.parse import urlencode

from flask import Flask, request, jsonify, Response, render_template, redirect
from flask_cors import CORS
from jose import JWTError

import config
import db
import auth
import services

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Module-level startup — runs in every gunicorn worker on import
# ---------------------------------------------------------------------------
try:
    db.init()
    logger.info("Database initialised")
except Exception as _exc:
    logger.warning("Database init deferred (will retry on first request): %s", _exc)

auth.fetch_jwks()

# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Homepage / docs
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def homepage():
    """Home feed page."""
    return render_template(
        "home.html",
        page_title="UAStream",
        page_name="home",
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


@app.route("/library", methods=["GET"])
def library_page():
    """Video library page."""
    return render_template(
        "library.html",
        page_title="Library · UAStream",
        page_name="library",
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


@app.route("/watch/<video_id>", methods=["GET"])
def watch_page(video_id):
    """Watch page."""
    return render_template(
        "watch.html",
        page_title="Watch · UAStream",
        page_name="watch",
        selected_video_id=video_id,
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


@app.route("/upload", methods=["GET"])
def upload_page():
    """Professor upload page."""
    return render_template(
        "upload.html",
        page_title="Upload · UAStream",
        page_name="upload",
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


@app.route("/auth", methods=["GET"])
def auth_page():
    """Authentication page."""
    return render_template(
        "auth.html",
        page_title="Sign In · UAStream",
        page_name="auth",
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


def _auth_callback_uri():
    """Build the absolute callback URI for this current request host."""
    return f"{request.host_url.rstrip('/')}/auth/callback"


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _jwt_required():
    """Return decoded JWT payload dict or a (response, status) error tuple."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None, (jsonify({"error": "missing or invalid Authorization header"}), 401)

    token = header[7:]
    try:
        payload = auth.decode_token(token)
    except JWTError as exc:
        return None, (jsonify({"error": f"invalid token: {exc}"}), 401)

    return {
        "user_id": payload.get("sub"),
        "email": payload.get("email"),
        "name": payload.get("name") or payload.get("preferred_username") or payload.get("email"),
        "preferred_username": payload.get("preferred_username"),
        "role": payload.get("role"),
        "institution": payload.get("institution"),
    }, None


def _professor_required():
    payload, err = _jwt_required()
    if err:
        return None, err
        
    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user or user["role"] != "professor":
        return None, (jsonify({"error": "forbidden – professor role required"}), 403)
        
    # Populate payload with db truth
    payload["role"] = user["role"]
    payload["institution"] = user["institution"]
    return payload, None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/auth/login", methods=["GET"])
def auth_login_redirect():
    """Redirect browser to Keycloak login (Authorization Code flow)."""
    params = {
        "client_id": config.KEYCLOAK_CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": _auth_callback_uri(),
    }
    url = (
        f"{config.KEYCLOAK_PUBLIC_URL}/realms/{config.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/auth?{urlencode(params)}"
    )
    return redirect(url, code=302)


@app.route("/auth/callback", methods=["GET"])
def auth_callback():
    """Handle OAuth callback and bootstrap browser token session."""
    oidc_error = request.args.get("error")
    if oidc_error:
        return render_template(
            "auth_callback.html",
            page_title="Sign In Failed · UAStream",
            page_name="auth-callback",
            auth_error=request.args.get("error_description") or oidc_error,
            downstream_services={
                "iam": config.KEYCLOAK_URL,
                "object_storage": config.OBJECT_STORAGE_URL,
                "video_editor": config.VIDEO_EDITOR_URL,
                "notifications": config.NOTIFICATIONS_URL,
                "database": config.DATABASE_URL,
            },
        ), 401

    code = request.args.get("code")
    if not code:
        return render_template(
            "auth_callback.html",
            page_title="Sign In Failed · UAStream",
            page_name="auth-callback",
            auth_error="Missing authorization code.",
            downstream_services={
                "iam": config.KEYCLOAK_URL,
                "object_storage": config.OBJECT_STORAGE_URL,
                "video_editor": config.VIDEO_EDITOR_URL,
                "notifications": config.NOTIFICATIONS_URL,
                "database": config.DATABASE_URL,
            },
        ), 400

    status, data = auth.exchange_authorization_code(
        code=code,
        redirect_uri=_auth_callback_uri(),
    )
    if status != 200:
        logger.warning("Authorization code exchange failed: %s", data)
        return render_template(
            "auth_callback.html",
            page_title="Sign In Failed · UAStream",
            page_name="auth-callback",
            auth_error=(data.get("error_description") or data.get("error") or "Token exchange failed."),
            downstream_services={
                "iam": config.KEYCLOAK_URL,
                "object_storage": config.OBJECT_STORAGE_URL,
                "video_editor": config.VIDEO_EDITOR_URL,
                "notifications": config.NOTIFICATIONS_URL,
                "database": config.DATABASE_URL,
            },
        ), 401

    return render_template(
        "auth_callback.html",
        page_title="Signing In · UAStream",
        page_name="auth-callback",
        access_token=data.get("access_token", ""),
        refresh_token=data.get("refresh_token", ""),
        id_token=data.get("id_token", ""),
        next_path="/library",
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


@app.route("/auth/logout", methods=["GET"])
def auth_logout():
    """Terminate the Keycloak SSO session and redirect back to home."""
    id_token_hint = request.args.get("id_token_hint", "")
    params = {
        "post_logout_redirect_uri": request.host_url,
        "client_id": config.KEYCLOAK_CLIENT_ID,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    end_session_url = (
        f"{config.KEYCLOAK_PUBLIC_URL}/realms/{config.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/logout?{urlencode(params)}"
    )
    return redirect(end_session_url, code=302)

@app.route("/auth/login", methods=["POST"])
def auth_login():
    """Proxy login to Keycloak (grant_type: password)."""
    body = request.get_json(force=True) or {}
    if not body.get("email") or not body.get("password"):
        return jsonify({"error": "email and password are required"}), 400

    status, data = auth.login(body["email"], body["password"])
    if status != 200:
        return jsonify(data), status

    return jsonify({
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"],
    }), 200


@app.route("/auth/refresh", methods=["POST"])
def auth_refresh():
    """Proxy token refresh to Keycloak (grant_type: refresh_token)."""
    body = request.get_json(force=True) or {}
    if not body.get("refresh_token"):
        return jsonify({"error": "refresh_token is required"}), 400

    status, data = auth.refresh_token(body["refresh_token"])
    if status != 200:
        return jsonify(data), status

    return jsonify({
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data["expires_in"],
    }), 200


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.route("/users", methods=["POST"])
def register_user():
    """Register a new user (Keycloak + local DB + welcome email)."""
    body = request.get_json(force=True) or {}
    for field in ("email", "password", "name", "role", "institution"):
        if not body.get(field):
            return jsonify({"error": f"missing required field: {field}"}), 400

    if body["role"] not in ("professor", "student"):
        return jsonify({"error": "role must be 'professor' or 'student'"}), 400

    # Duplicate check
    if db.get_user_by_email(body["email"]):
        return jsonify({"error": "user already exists"}), 409

    # 1) Obtain service token
    try:
        service_token = auth.get_service_token()
    except Exception as exc:
        logger.error("Failed to get Keycloak service token: %s", exc)
        return jsonify({"error": "identity service unavailable"}), 502

    # 2) Create user in Keycloak
    kc_status, kc_result = auth.create_keycloak_user(
        service_token,
        body["email"],
        body["password"],
        body["role"],
        body["institution"],
    )
    if kc_status == 409:
        return jsonify({"error": "user already exists"}), 409
    if kc_status != 201:
        logger.error("Keycloak user creation failed: %s", kc_result)
        return jsonify({"error": "failed to create user in identity provider"}), 502

    keycloak_user_id = kc_result

    # 3) Persist profile in local DB
    user = db.create_user(
        keycloak_user_id=keycloak_user_id,
        email=body["email"],
        name=body["name"],
        role=body["role"],
        institution=body["institution"],
        course=body.get("course"),
    )

    # 4) Send welcome email (fire-and-forget)
    services.send_email(
        to=body["email"],
        subject="Bem-vindo ao UAStream",
        template="welcome",
        data={"name": body["name"]},
    )

    return jsonify({"user_id": str(user["id"])}), 201


@app.route("/users/me", methods=["GET"])
def get_me():
    """Return the authenticated user's profile."""
    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        # Fallback for accounts that exist in Keycloak but are not yet synced locally.
        return jsonify({
            "user_id": payload["user_id"],
            "email": payload.get("email") or payload.get("preferred_username") or "",
            "name": payload.get("name") or payload.get("preferred_username") or "User",
            "role": payload.get("role") or "student",
            "institution": payload.get("institution") or "",
            "course": None,
        }), 200

    return jsonify({
        "user_id": str(user["id"]),
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "institution": user["institution"],
        "course": user["course"],
    }), 200


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------

def _parse_tags():
    """Extract tags from the multipart form (list of strings or JSON)."""
    tags = request.form.getlist("tags")
    if not tags:
        raw = request.form.get("tags")
        if raw:
            try:
                tags = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                tags = [raw]
    return tags


@app.route("/videos", methods=["POST"])
def upload_video_endpoint():
    """Upload a video without Video Editor processing."""
    payload, err = _professor_required()
    if err:
        return err

    title = request.form.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 400

    description = request.form.get("description", "")
    tags = _parse_tags()
    course = request.form.get("course", "")
    subject = request.form.get("subject", "")

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    institution = user["institution"]
    bucket = institution
    raw_key = f"raw/{uuid.uuid4()}.mp4"

    # 1) Ensure institution bucket exists
    services.ensure_bucket(bucket)

    # 2) Upload raw file to Object Storage
    try:
        services.upload_object(bucket, raw_key, file.read())
    except Exception as exc:
        logger.error("Object Storage upload failed: %s", exc)
        return jsonify({"error": "failed to upload video"}), 502

    # 3) Persist metadata
    video = db.create_video(
        uploader_id=user["id"],
        institution=institution,
        title=title,
        description=description,
        tags=tags,
        course=course,
        subject=subject,
        storage_bucket=bucket,
        raw_storage_key=raw_key,
        status="uploaded",
    )

    # 4) Notification (fire-and-forget)
    services.send_email(
        to=user["email"],
        subject="Vídeo submetido com sucesso",
        template="upload_complete",
        data={"name": user["name"], "title": title},
    )

    return jsonify({"video_id": str(video["id"])}), 201


@app.route("/videos/process", methods=["POST"])
def upload_video_with_processing():
    """Upload a video WITH Video Editor processing.

    Returns 202 with an SSE stream relaying real-time progress from the
    Video Editor. The final SSE event (status: done) includes the video_id.
    """
    payload, err = _professor_required()
    if err:
        return err

    title = request.form.get("title")
    if not title:
        return jsonify({"error": "title is required"}), 400
    operations_raw = request.form.get("operations")
    if not operations_raw:
        return jsonify({"error": "operations is required"}), 400
    try:
        operations = json.loads(operations_raw)
    except (json.JSONDecodeError, TypeError):
        return jsonify({"error": "operations must be valid JSON"}), 400
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file is required"}), 400

    description = request.form.get("description", "")
    tags = _parse_tags()
    course = request.form.get("course", "")
    subject = request.form.get("subject", "")

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    institution = user["institution"]
    bucket = institution
    video_uuid = str(uuid.uuid4())
    raw_key = f"raw/{video_uuid}.mp4"
    processed_key = f"processed/{video_uuid}.mp4"

    # 1) Ensure bucket + upload raw file
    services.ensure_bucket(bucket)
    try:
        services.upload_object(bucket, raw_key, file.read())
    except Exception as exc:
        logger.error("Upload to Object Storage failed: %s", exc)
        return jsonify({"error": "failed to upload video"}), 502

    # 2) Create video record (status: processing)
    video = db.create_video(
        uploader_id=user["id"],
        institution=institution,
        title=title,
        description=description,
        tags=tags,
        course=course,
        subject=subject,
        storage_bucket=bucket,
        raw_storage_key=raw_key,
        status="processing",
    )
    video_id = str(video["id"])

    # 3) Obtain presigned URLs (src for GET, dst for PUT)
    try:
        src_presign = services.presign_object(bucket, raw_key, method="GET")
        dst_presign = services.presign_object(bucket, processed_key, method="PUT")
    except Exception as exc:
        logger.error("Presign failed: %s", exc)
        db.update_video_status(video_id, "failed")
        return jsonify({"error": "failed to generate presigned URLs"}), 502

    # 4) Submit job to Video Editor
    progress_url = f"{config.COMPOSER_BASE_URL}/internal/jobs/progress"
    try:
        job_resp = services.create_job(
            src_url=src_presign["url"],
            dst_url=dst_presign["url"],
            progress_url=progress_url,
            operations=operations,
        )
    except Exception as exc:
        logger.error("Video Editor job creation failed: %s", exc)
        db.update_video_status(video_id, "failed")
        return jsonify({"error": "failed to start processing job"}), 502

    external_job_id = job_resp["job_id"]

    # 5) Record processing job in DB
    db.create_processing_job(video_id, external_job_id, operations, processed_key)

    # 6) Relay SSE progress from Video Editor to the client
    def _sse_relay():
        try:
            for raw_event in services.stream_job_progress(external_job_id):
                data_str = raw_event.strip()
                if data_str.startswith("data:"):
                    data_str = data_str[5:].strip()

                try:
                    event_data = json.loads(data_str)
                except json.JSONDecodeError:
                    yield raw_event
                    continue

                status = event_data.get("status")

                if status == "done":
                    # Finalise video
                    db.update_video_status(video_id, "ready", processed_key)
                    db.update_processing_job(external_job_id, "done", 100)
                    event_data["video_id"] = video_id
                    yield f"data: {json.dumps(event_data)}\n\n"
                    # Send notification
                    services.send_email(
                        to=user["email"],
                        subject="Vídeo processado com sucesso",
                        template="upload_complete",
                        data={"name": user["name"], "title": title},
                    )
                    return
                elif status == "failed":
                    db.update_video_status(video_id, "failed")
                    db.update_processing_job(
                        external_job_id, "failed", 0, "processing failed"
                    )
                    yield raw_event
                    return
                else:
                    # Intermediate progress
                    percent = event_data.get("percent", 0)
                    db.update_processing_job(external_job_id, status, percent)
                    yield raw_event
        except Exception as exc:
            logger.error("SSE relay error: %s", exc)
            db.update_video_status(video_id, "failed")
            yield f'data: {json.dumps({"error": "stream interrupted"})}\n\n'

    return Response(_sse_relay(), status=202, mimetype="text/event-stream")


@app.route("/videos", methods=["GET"])
def list_videos_endpoint():
    """List / search videos scoped to the authenticated user's institution."""
    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    q = request.args.get("q", "") or None
    course = request.args.get("course", "") or None
    subject = request.args.get("subject", "") or None
    try:
        limit = min(int(request.args.get("limit", 25)), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400

    total, results = db.search_videos(
        institution=user["institution"],
        q=q,
        course=course,
        subject=subject,
        limit=limit,
        offset=offset,
    )

    return jsonify({
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [
            {
                "video_id": str(v["id"]),
                "title": v["title"],
                "description": v["description"],
                "tags": v["tags"] or [],
                "course": v["course"],
                "subject": v["subject"],
                "uploader_id": str(v["uploader_id"]),
                "created_at": v["created_at"].isoformat() if v["created_at"] else None,
            }
            for v in results
        ],
    }), 200


@app.route("/videos/<video_id>", methods=["GET"])
def get_video_endpoint(video_id):
    """Return video metadata and a temporary presigned streaming URL."""
    if not _UUID_RE.match(video_id):
        print("VIDEO NOT FOUND"); return jsonify({"error": "video not found"}), 404

    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    video = db.get_video(video_id)
    if not video:
        print("VIDEO NOT FOUND"); return jsonify({"error": "video not found"}), 404

    if video["institution"] != user["institution"]:
        print("FORBIDDEN"); return jsonify({"error": "forbidden"}), 403

    # Prefer the processed version if available
    storage_key = video["processed_storage_key"] or video["raw_storage_key"]
    try:
        presign = services.presign_object(
            video["storage_bucket"], storage_key, method="GET"
        )
        stream_url = presign["url"]
        
        # Rewrite internal object-storage URL to localhost for the frontend client browser
        if stream_url and "http://object-storage:8080" in stream_url:
            stream_url = stream_url.replace("http://object-storage:8080", "http://localhost:8081")
            
    except Exception as e:
        stream_url = None; print("PRESIGN ERROR:", e)

    return jsonify({
        "video_id": str(video["id"]),
        "title": video["title"],
        "description": video["description"],
        "tags": video["tags"] or [],
        "course": video["course"],
        "subject": video["subject"],
        "uploader_id": str(video["uploader_id"]),
        "created_at": video["created_at"].isoformat() if video["created_at"] else None,
        "stream_url": stream_url,
    }), 200


@app.route("/videos/<video_id>", methods=["DELETE"])
def delete_video_endpoint(video_id):
    """Delete a video. Only the uploader may delete."""
    if not _UUID_RE.match(video_id):
        print("VIDEO NOT FOUND"); return jsonify({"error": "video not found"}), 404

    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    video = db.get_video(video_id)
    if not video:
        print("VIDEO NOT FOUND"); return jsonify({"error": "video not found"}), 404

    if str(video["uploader_id"]) != str(user["id"]):
        return jsonify({"error": "forbidden – only the uploader can delete"}), 403

    # Remove from Object Storage
    services.delete_object(video["storage_bucket"], video["raw_storage_key"])
    if video["processed_storage_key"]:
        services.delete_object(video["storage_bucket"], video["processed_storage_key"])

    # Soft-delete in DB
    db.delete_video(video_id)

    return "", 204


# ---------------------------------------------------------------------------
# Internal (called by Video Editor via progress_url callback)
# ---------------------------------------------------------------------------

@app.route("/internal/jobs/progress", methods=["POST"])
def receive_job_progress():
    """Callback endpoint for the Video Editor to push progress updates."""
    body = request.get_json(force=True) or {}
    external_job_id = body.get("job_id")
    status = body.get("status")
    percent = body.get("percent", 0)

    if not external_job_id or not status:
        return jsonify({"error": "job_id and status are required"}), 400

    error_msg = body.get("error") if status == "failed" else None
    db.update_processing_job(external_job_id, status, percent, error_msg)

    if status in ("done", "failed"):
        job = db.get_processing_job_by_external_id(external_job_id)
        if job:
            vid = str(job["video_id"])
            if status == "done":
                # Use the key stored when the job was created
                processed_key = job.get("processed_key") or f"processed/{vid}.mp4"
                db.update_video_status(vid, "ready", processed_key)
            else:
                db.update_video_status(vid, "failed")

    return "", 204


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Initialise database
    try:
        db.init()
        logger.info("Database initialised")
    except Exception as exc:
        logger.warning("Database init failed (will retry on first request): %s", exc)

    # Cache Keycloak public keys
    auth.fetch_jwks()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), debug=True)
