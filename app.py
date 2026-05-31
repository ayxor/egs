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
from urllib.parse import urlencode, quote

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


@app.route("/studio", methods=["GET"])
def studio_page():
    """Professor studio page (manage videos)."""
    return render_template(
        "studio.html",
        page_title="Studio · UAStream",
        page_name="studio",
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
    institution = body.get("institution") or "universidade-aveiro"
    course = body.get("course") or None

    for field in ("email", "password", "first_name", "last_name", "role"):
        if not body.get(field):
            return jsonify({"error": f"missing required field: {field}"}), 400

    if body["role"] not in ("professor", "student"):
        return jsonify({"error": "role must be 'professor' or 'student'"}), 400

    first_name = body["first_name"].strip()
    last_name = body["last_name"].strip()
    name = f"{first_name} {last_name}"

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
        service_token=service_token,
        email=body["email"],
        password=body["password"],
        first_name=first_name,
        last_name=last_name,
        role=body["role"],
        institution=institution,
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
        name=name,
        role=body["role"],
        institution=institution,
        course=course,
    )

    # 4) Send welcome email (fire-and-forget)
    services.send_email(
        to=body["email"],
        subject="Bem-vindo ao UAStream",
        template="welcome",
        data={"name": name},
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
# Channels & Subscriptions
# ---------------------------------------------------------------------------

@app.route("/channels", methods=["POST"])
def create_channel_endpoint():
    """Create a new channel (professor only)."""
    payload, err = _professor_required()
    if err:
        return err

    body = request.get_json(force=True) or {}
    name = body.get("name")
    if not name:
        return jsonify({"error": "name is required"}), 400

    channel_type = body.get("channel_type", "class")
    if channel_type not in ("class", "personal"):
        return jsonify({"error": "channel_type must be 'class' or 'personal'"}), 400

    visibility = body.get("visibility", "public")
    if visibility not in ("public", "unlisted", "private"):
        return jsonify({"error": "visibility must be 'public', 'unlisted', or 'private'"}), 400

    description = body.get("description", "")
    course_code = body.get("course_code")

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.create_channel(
        owner_id=user["id"],
        name=name,
        description=description,
        channel_type=channel_type,
        visibility=visibility,
        course_code=course_code,
    )

    # Automatically subscribe the creator to their own channel
    db.subscribe_to_channel(user["id"], channel["id"])

    return jsonify(channel), 201


@app.route("/channels/<channel_id>", methods=["PUT", "PATCH"])
def update_channel_endpoint(channel_id):
    """Update channel metadata (professor/owner only)."""
    if not _UUID_RE.match(channel_id):
        return jsonify({"error": "channel not found"}), 404

    payload, err = _professor_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({"error": "channel not found"}), 404

    # Enforce ownership check
    if str(channel["owner_id"]) != str(user["id"]):
        return jsonify({"error": "forbidden - only the owner can edit the channel"}), 403

    body = request.get_json(force=True) or {}
    name = body.get("name", channel["name"])
    if not name:
        return jsonify({"error": "name is required"}), 400

    visibility = body.get("visibility", channel["visibility"])
    if visibility not in ("public", "unlisted", "private"):
        return jsonify({"error": "visibility must be 'public', 'unlisted', or 'private'"}), 400

    description = body.get("description", channel["description"])
    course_code = body.get("course_code", channel["course_code"])

    db.update_channel(
        channel_id=channel_id,
        name=name,
        description=description,
        visibility=visibility,
        course_code=course_code,
    )

    return "", 204


@app.route("/channels/<channel_id>", methods=["DELETE"])
def delete_channel_endpoint(channel_id):
    """Delete a channel and all its videos (owner only)."""
    if not _UUID_RE.match(channel_id):
        return jsonify({"error": "channel not found"}), 404

    payload, err = _professor_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({"error": "channel not found"}), 404

    # Enforce ownership check
    if str(channel["owner_id"]) != str(user["id"]):
        return jsonify({"error": "forbidden - only the owner can delete the channel"}), 403

    db.delete_channel(channel_id)
    return "", 204


@app.route("/channels", methods=["GET"])
def list_channels_endpoint():
    """List channels visible to the user."""
    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channels = db.get_channels(user_id=user["id"])
    return jsonify({"results": channels}), 200


@app.route("/channels/<channel_id>", methods=["GET"])
def get_channel_endpoint(channel_id):
    """Get channel details and associated videos."""
    if not _UUID_RE.match(channel_id):
        return jsonify({"error": "channel not found"}), 404

    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({"error": "channel not found"}), 404

    # Visibility checks
    visibility = channel["visibility"]
    if visibility == "private":
        is_owner = str(channel["owner_id"]) == str(user["id"])
        is_sub = db.is_subscribed(user["id"], channel_id)
        if not is_owner and not is_sub:
            return jsonify({"error": "forbidden - private channel access restricted"}), 403

    videos = db.get_videos_by_channel(channel_id)
    return jsonify({
        "channel": channel,
        "is_subscribed": db.is_subscribed(user["id"], channel_id),
        "results": [
            {
                "video_id": str(v["id"]),
                "title": v["title"],
                "description": v["description"],
                "tags": v["tags"] or [],
                "course": v["course"],
                "subject": v["subject"],
                "status": v["status"],
                "duration": v.get("duration"),
                "thumbnail_url": f"/internal/storage/{quote(v['storage_bucket'])}/{v['thumbnail_key']}" if v.get("thumbnail_key") else None,
                "created_at": v["created_at"].isoformat() if v["created_at"] else None,
                "views": v.get("views", 0),
            }
            for v in videos
        ]
    }), 200

@app.route("/channels/<channel_id>/subscribers", methods=["GET"])
def get_channel_subscribers_endpoint(channel_id):
    """List subscribers of a course channel. Restricted to the channel owner."""
    if not _UUID_RE.match(channel_id):
        return jsonify({"error": "channel not found"}), 404

    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({"error": "channel not found"}), 404

    # Restrict strictly to channel owner
    if str(channel["owner_id"]) != str(user["id"]):
        return jsonify({"error": "forbidden - only the channel owner can view subscribers"}), 403

    subscribers = db.get_channel_subscribers(channel_id)
    return jsonify({
        "results": [
            {
                "name": sub["name"],
                "email": sub["email"],
            }
            for sub in subscribers
        ]
    }), 200


@app.route("/channels/<channel_id>/add-member", methods=["POST"])
def add_member_to_channel_endpoint(channel_id):
    """Add a user to a channel by email. Restricted to the channel owner (professor)."""
    if not _UUID_RE.match(channel_id):
        return jsonify({"error": "channel not found"}), 404

    payload, err = _professor_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({"error": "channel not found"}), 404

    # Restrict strictly to channel owner
    if str(channel["owner_id"]) != str(user["id"]):
        return jsonify({"error": "forbidden - only the channel owner can add members"}), 403

    body = request.get_json(force=True) or {}
    email = body.get("email", "").strip().lower()
    if not email:
        return jsonify({"error": "email is required"}), 400

    target_user = db.get_user_by_email(email)
    if not target_user:
        return jsonify({"error": f"No registered user found with email '{email}'"}), 404

    # Check if already subscribed
    if db.is_subscribed(target_user["id"], channel_id):
        return jsonify({"error": f"'{email}' is already a member of this channel"}), 409

    db.subscribe_to_channel(target_user["id"], channel_id)
    return jsonify({"message": f"'{email}' has been added to the channel successfully"}), 200


@app.route("/channels/<channel_id>/subscribe", methods=["POST"])
def subscribe_channel_endpoint(channel_id):
    """Subscribe or unsubscribe to a channel."""
    if not _UUID_RE.match(channel_id):
        return jsonify({"error": "channel not found"}), 404

    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    channel = db.get_channel(channel_id)
    if not channel:
        return jsonify({"error": "channel not found"}), 404

    body = request.get_json(force=True) or {}
    action = body.get("action", "subscribe")

    if action == "subscribe":
        db.subscribe_to_channel(user["id"], channel_id)
        return jsonify({"message": "subscribed successfully"}), 200
    elif action == "unsubscribe":
        db.unsubscribe_from_channel(user["id"], channel_id)
        return jsonify({"message": "unsubscribed successfully"}), 200
    else:
        return jsonify({"error": "action must be 'subscribe' or 'unsubscribe'"}), 400


@app.route("/channel/<channel_id>", methods=["GET"])
def channel_page(channel_id):
    """Channel landing page template."""
    return render_template(
        "channel.html",
        page_title="Channel · UAStream",
        page_name="channel",
        selected_channel_id=channel_id,
        downstream_services={
            "iam": config.KEYCLOAK_URL,
            "object_storage": config.OBJECT_STORAGE_URL,
            "video_editor": config.VIDEO_EDITOR_URL,
            "notifications": config.NOTIFICATIONS_URL,
            "database": config.DATABASE_URL,
        },
    )


@app.route("/users/me/subscriptions", methods=["GET"])
def get_my_subscriptions():
    """List current user's subscribed channels."""
    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    subs = db.get_user_subscriptions(user["id"])
    return jsonify({"results": subs}), 200


@app.route("/videos/subscribed", methods=["GET"])
def list_subscribed_videos():
    """Get a feed of latest videos from subscribed channels."""
    payload, err = _jwt_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    results = db.get_subscribed_feed(user["id"])
    return jsonify({
        "results": [
            {
                "video_id": str(v["id"]),
                "title": v["title"],
                "description": v["description"],
                "tags": v["tags"] or [],
                "course": v["course"],
                "subject": v["subject"],
                "duration": v.get("duration"),
                "thumbnail_url": f"/internal/storage/{quote(v['storage_bucket'])}/{v['thumbnail_key']}" if v.get("thumbnail_key") else None,
                "created_at": v["created_at"].isoformat() if v["created_at"] else None,
                "channel_id": str(v["channel_id"]) if v.get("channel_id") else None,
                "channel_name": v.get("channel_name"),
            }
            for v in results
        ]
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


def _notify_students(title, channel_id, uploader_name):
    if not channel_id:
        return
    channel = db.get_channel(channel_id)
    if not channel:
        return
    channel_name = channel["name"]

    subscribers = db.get_channel_subscribers(channel_id)
    for sub in subscribers:
        services.send_email(
            to=sub["email"],
            subject=f"Novo vídeo em {channel_name}: {title}",
            template="new_video",
            data={
                "name": sub["name"],
                "course": channel_name,
                "professor_name": uploader_name,
                "title": title
            },
        )


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
    channel_id = request.form.get("channel_id") or None
    if channel_id == "null" or channel_id == "":
        channel_id = None

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
        channel_id=channel_id,
    )

    # 4) Notification (fire-and-forget)
    services.send_email(
        to=user["email"],
        subject="Vídeo submetido com sucesso",
        template="upload_complete",
        data={"name": user["name"], "title": title},
    )
    _notify_students(title, channel_id, user["name"])

    return jsonify({"video_id": str(video["id"])}), 201


def parse_mp4_duration(data: bytes) -> float:
    idx = data.find(b'mvhd')
    if idx == -1:
        return 0.0
    
    if idx + 24 > len(data):
        return 0.0

    version = data[idx + 4]
    
    if version == 0:
        time_scale = int.from_bytes(data[idx + 16 : idx + 20], byteorder='big')
        duration = int.from_bytes(data[idx + 20 : idx + 24], byteorder='big')
    elif version == 1:
        if idx + 36 > len(data):
            return 0.0
        time_scale = int.from_bytes(data[idx + 24 : idx + 28], byteorder='big')
        duration = int.from_bytes(data[idx + 28 : idx + 36], byteorder='big')
    else:
        return 0.0
        
    if time_scale > 0:
        return float(duration) / float(time_scale)
    return 0.0

def format_duration(seconds: float) -> str:
    s = int(round(seconds))
    if s <= 0:
        return "0:05"
    h = s // 3600
    m = (s % 3600) // 60
    r = s % 60
    if h > 0:
        return f"{h}:{m:02d}:{r:02d}"
    return f"{m}:{r:02d}"

def _run_processing_job_in_background(video_id, external_job_id, bucket, processed_key, thumb_key, title, channel_id, user_email, user_name):
    """Actively polls the passive Video Editor, uploads results, and finalizes DB."""
    logger.info("Spawning background thread for video finalization of video_id: %s, job_id: %s", video_id, external_job_id)
    try:
        # Stream progress from the Video Editor
        for raw_event in services.stream_job_progress(external_job_id):
            data_str = raw_event.strip()
            if data_str.startswith("data:"):
                data_str = data_str[5:].strip()

            try:
                event_data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            status = event_data.get("status")
            percent = event_data.get("percent", 0)
            msg = event_data.get("message", "")

            if status == "done":
                try:
                    logger.info("Background job %s done. Downloading result...", external_job_id)
                    # Pull final video
                    processed_bytes = services.download_job_result(external_job_id)
                    services.upload_object(bucket, processed_key, processed_bytes)
                    
                    duration_str = None
                    try:
                        duration_secs = parse_mp4_duration(processed_bytes)
                        if duration_secs > 0:
                            duration_str = format_duration(duration_secs)
                            logger.info("Parsed video duration: %s secs -> %s", duration_secs, duration_str)
                    except Exception as parse_ex:
                        logger.error("Failed to parse MP4 duration: %s", parse_ex)

                    # Pull thumbnail
                    try:
                        thumb_bytes = services.download_job_thumbnail(external_job_id)
                        services.upload_object(bucket, thumb_key, thumb_bytes)
                    except Exception as e:
                        logger.error("Failed to pull thumbnail for job %s: %s", external_job_id, e)

                    # Finalise video in DB
                    db.update_video_status(video_id, "ready", processed_key, thumbnail_key=thumb_key, duration=duration_str)
                    db.update_processing_job(external_job_id, "done", 100, message="Processing complete.")

                    # Send notification to uploader
                    try:
                        services.send_email(
                            to=user_email,
                            subject="Vídeo processado com sucesso",
                            template="upload_complete",
                            data={"name": user_name, "title": title},
                        )
                    except Exception as email_err:
                        logger.error("Failed to send email to uploader: %s", email_err)
                    
                    # Send notification to subscribers
                    try:
                        _notify_students(title, channel_id, user_name)
                    except Exception as notify_err:
                        logger.error("Failed to notify students: %s", notify_err)
                        
                except Exception as e:
                    logger.error("Failed to finalize video %s in background: %s", video_id, e)
                    db.update_video_status(video_id, "failed")
                    db.update_processing_job(external_job_id, "failed", 0, str(e), message="Finalization failed.")
                return

            elif status == "failed":
                err_msg = event_data.get("error", "processing failed")
                logger.error("Background job %s reported failure: %s", external_job_id, err_msg)
                db.update_video_status(video_id, "failed")
                db.update_processing_job(external_job_id, "failed", 0, err_msg, message="Processing failed.")
                return

            else:
                # Intermediate progress
                db.update_processing_job(external_job_id, status, percent, message=msg)

    except Exception as exc:
        logger.error("Background job processing exception for job %s: %s", external_job_id, exc)
        try:
            db.update_video_status(video_id, "failed")
            db.update_processing_job(external_job_id, "failed", 0, str(exc), message="Unexpected background error.")
        except Exception as db_exc:
            logger.error("Failed to mark job/video as failed in DB: %s", db_exc)


@app.route("/videos/process", methods=["POST"])
def upload_video_with_processing():
    """Upload a video WITH Video Editor processing.

    Returns 202 with an SSE stream relaying real-time progress from the
    local database. The final SSE event (status: done) includes the video_id.
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
    channel_id = request.form.get("channel_id") or None
    if channel_id == "null" or channel_id == "":
        channel_id = None

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    institution = user["institution"]
    bucket = institution
    video_uuid = str(uuid.uuid4())
    raw_key = f"raw/{video_uuid}.mp4"
    processed_key = f"processed/{video_uuid}.mp4"

    thumb_key = f"thumbnails/{video_uuid}.jpg"
    
    # 1) Read file bytes into memory
    file_bytes = file.read()
    
    # 2) Ensure bucket + upload raw file
    services.ensure_bucket(bucket)
    try:
        services.upload_object(bucket, raw_key, file_bytes)
    except Exception as exc:
        logger.error("Upload to Object Storage failed: %s", exc)
        return jsonify({"error": "failed to upload video"}), 502

    # 3) Create video record (status: processing)
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
        channel_id=channel_id,
    )
    video_id = str(video["id"])

    # 4) Submit job strictly as a direct upload (no callbacks)
    try:
        job_resp = services.create_job(
            file_bytes=file_bytes,
            operations=operations,
        )
    except Exception as exc:
        logger.error("Video Editor job creation failed: %s", exc)
        db.update_video_status(video_id, "failed")
        return jsonify({"error": "failed to start processing job"}), 502

    external_job_id = job_resp["job_id"]

    # 5) Record processing job in DB
    db.create_processing_job(video_id, external_job_id, operations, processed_key)

    # 6) Spawn the background finalization thread
    import threading
    t = threading.Thread(
        target=_run_processing_job_in_background,
        args=(video_id, external_job_id, bucket, processed_key, thumb_key, title, channel_id, user["email"], user["name"])
    )
    t.daemon = True
    t.start()

    # 7) Relay SSE progress to client by polling PostgreSQL database
    def _sse_relay():
        import time
        last_percent = -1
        last_status = ""
        last_msg = ""
        while True:
            try:
                job = db.get_processing_job_by_external_id(external_job_id)
                if not job:
                    yield f"data: {json.dumps({'status': 'failed', 'error': 'Job not found'})}\n\n"
                    return

                status = job["status"]
                percent = job["percent"]
                msg = job.get("message") or ""

                if status != last_status or percent != last_percent or msg != last_msg:
                    event_data = {
                        "status": status,
                        "percent": percent,
                        "message": msg,
                        "video_id": video_id
                    }
                    if status == "failed" and job.get("error_message"):
                        event_data["error"] = job["error_message"]
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_status = status
                    last_percent = percent
                    last_msg = msg

                if status in ("done", "failed"):
                    return
                time.sleep(0.5)
            except Exception as e:
                logger.error("SSE database polling error: %s", e)
                yield f"data: {json.dumps({'status': 'failed', 'error': 'stream interrupted'})}\n\n"
                return

    return Response(_sse_relay(), status=202, mimetype="text/event-stream")


@app.route("/videos/me", methods=["GET"])
def list_my_videos_endpoint():
    """List videos uploaded by the authenticated user (professors)."""
    payload, err = _professor_required()
    if err:
        return err
        
    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404
        
    videos = db.get_videos_by_uploader(user["id"])
    return jsonify({
        "results": [
            {
                "video_id": str(v["id"]),
                "title": v["title"],
                "description": v["description"],
                "tags": v["tags"] or [],
                "course": v["course"],
                "subject": v["subject"],
                "status": v["status"],
                "duration": v.get("duration"),
                "thumbnail_url": f"/internal/storage/{quote(v['storage_bucket'])}/{v['thumbnail_key']}" if v.get("thumbnail_key") else None,
                "created_at": v["created_at"].isoformat() if v["created_at"] else None,
                "views": v.get("views", 0),
            }
            for v in videos
        ]
    }), 200


@app.route("/videos/<video_id>", methods=["PATCH", "PUT"])
def update_video_endpoint(video_id):
    """Update video metadata."""
    payload, err = _professor_required()
    if err:
        return err

    user = db.get_user_by_keycloak_id(payload["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404

    video = db.get_video(video_id)
    if not video:
        return jsonify({"error": "video not found"}), 404

    if video["uploader_id"] != user["id"]:
        return jsonify({"error": "forbidden"}), 403

    body = request.get_json(force=True) or {}
    title = body.get("title", video["title"])
    description = body.get("description", video["description"])
    course = body.get("course", video["course"])
    subject = body.get("subject", video["subject"])
    tags = body.get("tags", video["tags"])
    channel_id = body.get("channel_id") or video.get("channel_id")
    if channel_id == "null" or channel_id == "":
        channel_id = None
    
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]

    db.update_video(video_id, title, description, tags, course, subject, channel_id=channel_id)
    return "", 204


@app.route("/videos", methods=["GET"])
def list_videos_endpoint():
    """List / search videos scoped by channel visibility."""
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
        user_id=user["id"],
        q=q,
        course=course,
        subject=subject,
        limit=limit,
        offset=offset,
    )

    matching_channels = []
    if q:
        matching_channels = db.search_public_channels(q, limit=100)
    else:
        matching_channels = db.get_channels(user_id=None)

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
                "duration": v.get("duration"),
                "thumbnail_url": f"/internal/storage/{quote(v['storage_bucket'])}/{v['thumbnail_key']}" if v.get("thumbnail_key") else None,
                "created_at": v["created_at"].isoformat() if v["created_at"] else None,
                "channel_id": str(v["channel_id"]) if v.get("channel_id") else None,
                "channel_name": v.get("channel_name"),
                "uploader_name": v.get("uploader_name"),
                "views": v.get("views", 0),
            }
            for v in results
        ],
        "channels": [
            {
                "id": str(c["id"]),
                "name": c["name"],
                "description": c["description"],
                "course_code": c["course_code"],
                "owner_name": c["owner_name"],
                "visibility": c["visibility"],
            }
            for c in matching_channels
        ]
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
        print("VIDEOupload_page NOT FOUND"); return jsonify({"error": "video not found"}), 404

    # Increment views count
    try:
        db.increment_video_views(video_id)
    except Exception as e:
        logger.error("Failed to increment views for video %s: %s", video_id, e)

    # Enforce channel visibility rules
    channel_id = video.get("channel_id")
    if channel_id:
        visibility = video.get("channel_visibility")
        owner_id = video.get("channel_owner_id")
        
        if visibility == "private":
            is_owner = str(owner_id) == str(user["id"])
            is_sub = db.is_subscribed(user["id"], channel_id)
            if not is_owner and not is_sub:
                print("FORBIDDEN - PRIVATE CHANNEL ACCESS RESTRICTED")
                return jsonify({"error": "forbidden - private channel access restricted"}), 403

    # Prefer the processed version if available
    storage_key = video["processed_storage_key"] or video["raw_storage_key"]
    try:
        presign = services.presign_object(
            video["storage_bucket"], storage_key, method="GET"
        )
        stream_url = presign["url"]
        
        # Rewrite internal object-storage URL to public URL for the frontend client browser
        if stream_url and "http://object-storage:8080" in stream_url:
            stream_url = stream_url.replace("http://object-storage:8080", "http://uastream.com")
            
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
        "thumbnail_url": f"/internal/storage/{quote(video['storage_bucket'])}/{video['thumbnail_key']}" if video.get("thumbnail_key") else None,
        "created_at": video["created_at"].isoformat() if video["created_at"] else None,
        "stream_url": stream_url,
        "channel_id": str(channel_id) if channel_id else None,
        "channel_name": video.get("channel_name"),
        "views": video.get("views", 0),
        "duration": video.get("duration"),
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

@app.route("/internal/storage/<bucket>/<path:key>", methods=["GET", "PUT"])
def internal_storage_proxy(bucket, key):
    """Proxy requests from internal services to Object Storage."""
    if request.method == "GET":
        resp = services.download_object_stream(bucket, key)
        
        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                yield chunk
                
        return Response(generate(), status=resp.status_code, content_type=resp.headers.get("content-type"))
        
    elif request.method == "PUT":
        content_type = request.headers.get("Content-Type", "application/octet-stream")
        resp = services.upload_object_stream(bucket, key, request.stream, content_type=content_type)
        return Response(resp.content, status=resp.status_code, content_type=resp.headers.get("content-type"))


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
                thumbnail_key = processed_key.replace("processed/", "thumbnails/").replace(".mp4", ".jpg")
                db.update_video_status(vid, "ready", processed_key, thumbnail_key=thumbnail_key)
            else:
                db.update_video_status(vid, "failed")

    return "", 204

# ---------------------------------------------------------------------------
# Metrics & Observability Implementation
# ---------------------------------------------------------------------------
import time
import threading
import requests
from collections import defaultdict

_metrics_lock = threading.Lock()
_http_requests_total = defaultdict(int)
_http_request_duration_seconds = defaultdict(float)

@app.before_request
def before_request_metrics():
    request.start_time = time.time()

@app.after_request
def after_request_metrics(response):
    duration = 0.0
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
    
    path = request.path
    path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/<uuid>', path)
    path = re.sub(r'/watch/[^/]+', '/watch/<video_id>', path)
    path = re.sub(r'/channels/[^/]+', '/channels/<channel_id>', path)
    path = re.sub(r'/internal/storage/[^/]+/[^/]+', '/internal/storage/<bucket>/<key>', path)
    
    method = request.method
    status = str(response.status_code)
    
    with _metrics_lock:
        _http_requests_total[(method, path, status)] += 1
        _http_request_duration_seconds[(method, path)] += duration
        
    return response

def fetch_k8s_pod_metrics():
    token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ns_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    
    if not os.path.exists(token_path) or not os.path.exists(ns_path):
        return []
        
    try:
        import datetime
        with open(token_path, "r") as f:
            token = f.read().strip()
        with open(ns_path, "r") as f:
            namespace = f.read().strip()
            
        headers = {"Authorization": f"Bearer {token}"}
        metrics_lines = []
        
        # 1. Fetch Pod metrics (CPU/RAM)
        try:
            metrics_url = f"https://kubernetes.default.svc/apis/metrics.k8s.io/v1beta1/namespaces/{namespace}/pods"
            response = requests.get(metrics_url, headers=headers, verify=False, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                for item in data.get("items", []):
                    pod_name = item.get("metadata", {}).get("name", "")
                    app_name = item.get("metadata", {}).get("labels", {}).get("app", "")
                    if not app_name:
                        app_name = pod_name.split("-")[0]
                        
                    for container in item.get("containers", []):
                        container_name = container.get("name", "")
                        usage = container.get("usage", {})
                        
                        cpu_str = usage.get("cpu", "0n")
                        cpu_nanocores = 0
                        if cpu_str.endswith("n"):
                            cpu_nanocores = int(cpu_str[:-1])
                        elif cpu_str.endswith("u"):
                            cpu_nanocores = int(cpu_str[:-1]) * 1000
                        elif cpu_str.endswith("m"):
                            cpu_nanocores = int(cpu_str[:-1]) * 1000000
                        else:
                            try:
                                cpu_nanocores = int(cpu_str) * 1000000000
                            except Exception:
                                pass
                        
                        cpu_cores = cpu_nanocores / 1000000000.0
                        
                        mem_str = usage.get("memory", "0Ki")
                        mem_bytes = 0
                        if mem_str.endswith("Ki"):
                            mem_bytes = int(mem_str[:-2]) * 1024
                        elif mem_str.endswith("Mi"):
                            mem_bytes = int(mem_str[:-2]) * 1024 * 1024
                        elif mem_str.endswith("Gi"):
                            mem_bytes = int(mem_str[:-2]) * 1024 * 1024 * 1024
                        else:
                            try:
                                mem_bytes = int(mem_str)
                            except Exception:
                                pass
                                
                        metrics_lines.append(
                            f'kube_pod_cpu_usage_cores{{pod="{pod_name}",app="{app_name}",container="{container_name}"}} {cpu_cores:.6f}'
                        )
                        metrics_lines.append(
                            f'kube_pod_memory_usage_bytes{{pod="{pod_name}",app="{app_name}",container="{container_name}"}} {mem_bytes}'
                        )
        except Exception as exc:
            logger.warning("Exception fetching pod metrics: %s", exc)
            
        # 2. Fetch Pod metadata (Uptime and status phase)
        try:
            pods_url = f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/pods"
            response = requests.get(pods_url, headers=headers, verify=False, timeout=2.0)
            if response.status_code == 200:
                data = response.json()
                now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
                
                for item in data.get("items", []):
                    pod_name = item.get("metadata", {}).get("name", "")
                    app_name = item.get("metadata", {}).get("labels", {}).get("app", "")
                    if not app_name:
                        app_name = pod_name.split("-")[0]
                        
                    status = item.get("status", {})
                    phase = status.get("phase", "Unknown")
                    start_time_str = status.get("startTime")
                    
                    # Expose status phase gauge
                    metrics_lines.append(
                        f'kube_pod_status{{pod="{pod_name}",app="{app_name}",phase="{phase}"}} 1'
                    )
                    
                    if start_time_str:
                        try:
                            cleaned = start_time_str.split(".")[0].rstrip("Z")
                            dt = datetime.datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
                            start_ts = dt.replace(tzinfo=datetime.timezone.utc).timestamp()
                            uptime = max(0.0, now_ts - start_ts)
                            metrics_lines.append(
                                f'kube_pod_uptime_seconds{{pod="{pod_name}",app="{app_name}"}} {int(uptime)}'
                            )
                        except Exception:
                            pass
        except Exception as exc:
            logger.warning("Exception fetching pod statuses/uptime: %s", exc)
            
        return metrics_lines
    except Exception as exc:
        logger.warning("Exception while fetching pod metrics: %s", exc)
        return []

@app.route("/metrics", methods=["GET"])
def get_metrics():
    lines = []
    
    # Standard metrics representing the composer service being up
    lines.append('up{job="composer"} 1')
    
    with _metrics_lock:
        for (method, path, status), count in _http_requests_total.items():
            lines.append(f'http_requests_total{{app="composer",method="{method}",path="{path}",status="{status}"}} {count}')
        for (method, path), total_duration in _http_request_duration_seconds.items():
            lines.append(f'http_request_duration_seconds_sum{{app="composer",method="{method}",path="{path}"}} {total_duration:.6f}')
            count_for_dur = sum(
                cnt for (m, p, s), cnt in _http_requests_total.items()
                if m == method and p == path
            )
            lines.append(f'http_request_duration_seconds_count{{app="composer",method="{method}",path="{path}"}} {count_for_dur}')
            
    try:
        k8s_lines = fetch_k8s_pod_metrics()
        lines.extend(k8s_lines)
    except Exception as exc:
        logger.warning("Error fetching k8s pod metrics: %s", exc)
        
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


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
