"""
Notifications Service
Branch: notifications

Generic, template-based transactional email delivery service.
Completely agnostic to business logic — only sends emails when asked to by the Composer.
Accessible only by internal services via API key.

Run:
    pip install -r requirements.txt
    python app.py

FastAPI:
    http://uastream.com/openapi/swagger

Environment variables:
    NOTIFICATIONS_API_KEY   Shared secret (default: stub-api-key)
    NOTIFICATIONS_BASE_URL  Public base URL for tracking pixels (default: http://uastream.com)
    DATABASE_URL            SQLAlchemy DB URL (default: sqlite:///notifications.db)
    SMTP_HOST               SMTP server hostname (default: localhost)
    SMTP_PORT               SMTP server port (default: 587)
    SMTP_USER               SMTP username
    SMTP_PASSWORD           SMTP password
    SMTP_FROM               Sender address (default: noreply@notifications.local)
    SMTP_USE_TLS            Use STARTTLS (default: true)
    SMTP_USE_SSL            Use SSL/TLS from the start, e.g. port 465 (default: false)
"""

from flask_openapi3.openapi import OpenAPI
from flask_openapi3.models.info import Info
from flask_openapi3.models.security_scheme import SecurityScheme
from flask import request, jsonify, Response
from pydantic import BaseModel
from flask_sqlalchemy import SQLAlchemy
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from datetime import datetime, timezone
import os
import uuid
import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("notifications")

info = Info(title="Notifications Service API", version="1.0.0")
app = OpenAPI(
    __name__,
    info=info,
    security_schemes={
        "ApiKeyAuth": SecurityScheme(
            type="apiKey",
            name="X-API-Key",
            security_scheme_in="header",
        )
    },
)

# Reusable security requirement applied to every protected endpoint
_API_SECURITY = [{"ApiKeyAuth": []}]

# ---------------------------------------------------------------------------
# API key enforcement — runs before route handlers (and before Pydantic
# validation), so unauthenticated requests always get 401, never 422.
# The tracking pixel endpoint is explicitly excluded.
# ---------------------------------------------------------------------------

# Endpoints exempt from API key check:
#   - track_open        → tracking pixel (called by external mail clients)
#   - openapi.*         → Swagger UI, openapi.json, static assets (endpoint prefix)
_PUBLIC_ENDPOINTS = {"track_open", "get_metrics"}
# Covers openapi.*, swagger.*, redoc.*, rapidoc.*, scalar.*, elements.*
_PUBLIC_ENDPOINT_PREFIXES = ("openapi.", "swagger.", "redoc.", "rapidoc.", "scalar.", "elements.")

@app.before_request
def check_api_key():
    endpoint = request.endpoint or ""
    # No endpoint = unmatched route → let Flask return 404 naturally
    if not endpoint:
        return None
    if endpoint in _PUBLIC_ENDPOINTS or any(endpoint.startswith(p) for p in _PUBLIC_ENDPOINT_PREFIXES):
        return None
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///notifications.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("NOTIFICATIONS_API_KEY", "stub-api-key")

# Base URL used to build the tracking pixel URL embedded in emails.
BASE_URL = os.environ.get("NOTIFICATIONS_BASE_URL", "http://uastream.com")

# ---------------------------------------------------------------------------
# SMTP config
# ---------------------------------------------------------------------------

SMTP_HOST     = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT     = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER     = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM     = os.environ.get("SMTP_FROM", "noreply@notifications.local")
SMTP_USE_TLS  = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
SMTP_USE_SSL  = os.environ.get("SMTP_USE_SSL", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Jinja2 template engine
# ---------------------------------------------------------------------------

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=True,
)

# Template registry: maps template name -> list of required data fields.
# This is the source of truth for validation; the actual HTML lives in
# templates/<name>.html (and optionally templates/<name>.txt for plain text).
TEMPLATES: dict[str, list[str]] = {
    "welcome":         ["name"],
    "upload_complete": ["name", "title"],
    "new_video":       ["name", "course", "professor_name", "title"],
}


# ---------------------------------------------------------------------------
# Path parameter models (required by flask-openapi3)
# ---------------------------------------------------------------------------

class TemplatePath(BaseModel):
    template: str

class NotificationPath(BaseModel):
    notification_id: str

class EmailRequest(BaseModel):
    to: str
    subject: str
    template: str
    data: dict

class NotificationQuery(BaseModel):
    status: str | None = None
    to: str | None = None


def _render_template(template_name: str, data: dict, extra: dict) -> tuple[str, str | None]:
    """
    Render a template and return (html_body, plain_text_body).
    extra contains service-level vars (tracking_pixel_url, etc.).
    Returns (html, None) if no .txt variant exists.
    """
    context = {**data, **extra}

    html_template = jinja_env.get_template(f"{template_name}.html")
    html_body = html_template.render(**context)

    try:
        txt_template = jinja_env.get_template(f"{template_name}.txt")
        text_body = txt_template.render(**context)
    except TemplateNotFound:
        text_body = None

    return html_body, text_body


# ---------------------------------------------------------------------------
# SMTP delivery
# ---------------------------------------------------------------------------

def _send_email(to: str, subject: str, html_body: str, text_body: str | None) -> None:
    """
    Send a rendered email via SMTP.
    Raises smtplib.SMTPException (or subclass) on failure.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_FROM
    msg["To"]      = to

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if SMTP_USE_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], msg.as_string())

    log.info("Email sent to=%s subject='%s'", to, subject)


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class Notification(db.Model):
    __tablename__ = "notifications"

    id        = db.Column(db.String(36), primary_key=True)
    to        = db.Column(db.String(255), nullable=False)
    subject   = db.Column(db.String(500), nullable=False)
    template  = db.Column(db.String(100), nullable=False)
    # status: "sent" | "opened" | "failed"
    status    = db.Column(db.String(20), nullable=False)
    sent_at   = db.Column(db.DateTime, nullable=False)
    opened_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, to: str, subject: str, template: str) -> None:
        self.id        = str(uuid.uuid4())
        self.to        = to
        self.subject   = subject
        self.template  = template
        self.status    = "sent"
        self.sent_at   = datetime.now(timezone.utc)
        self.opened_at = None

    def to_dict(self):
        return {
            "notification_id": self.id,
            "to":              self.to,
            "subject":         self.subject,
            "template":        self.template,
            "status":          self.status,
            "sent_at":         self.sent_at.isoformat(),
            "opened_at":       self.opened_at.isoformat() if self.opened_at else None,
            "tracking_pixel":  f"{BASE_URL}/notifications/track/{self.id}.gif",
        }


with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# 1x1 transparent GIF (43 bytes — no external dependency needed)
# ---------------------------------------------------------------------------

TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00"
    b"\x00\x00\x00\x00\x00\x00"
    b"\x21\xf9\x04\x01\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"
    b"\x02\x02\x4c\x01\x00"
    b"\x3b"
)



# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@app.post("/notifications/email", security=_API_SECURITY)
def send_email(body: EmailRequest):
    """
    Accept an email request, render the template, send via SMTP, and persist
    a Notification record.
    Returns 202 Accepted — guarantees an attempt, not delivery.
    """
    template_name = body.template
    if template_name not in TEMPLATES:
        return jsonify({"error": "template not found"}), 404

    required_fields = TEMPLATES[template_name]
    missing = [f for f in required_fields if f not in body.data]
    if missing:
        return jsonify({"error": f"missing data fields for template: {missing}"}), 400

    # Persist notification record first so we have the ID for the tracking pixel.
    notification = Notification(
        to=body.to,
        subject=body.subject,
        template=template_name,
    )
    db.session.add(notification)
    db.session.commit()

    # Render template
    tracking_pixel_url = f"{BASE_URL}/notifications/track/{notification.id}.gif"
    try:
        html_body, text_body = _render_template(
            template_name,
            body.data,
            extra={"tracking_pixel_url": tracking_pixel_url},
        )
    except TemplateNotFound:
        notification.status = "failed"
        db.session.commit()
        log.error("Template file not found for '%s'", template_name)
        return jsonify({"error": "template file not found on disk"}), 500

    # Send email
    try:
        _send_email(body.to, body.subject, html_body, text_body)
    except Exception as exc:
        notification.status = "failed"
        db.session.commit()
        log.error("Failed to send email to %s: %s", body.to, exc)
        return jsonify({
            "notification_id": notification.id,
            "warning": f"Email queued but delivery failed: {exc}",
        }), 202

    return jsonify({"notification_id": notification.id}), 202


# ---------------------------------------------------------------------------
# Tracking pixel
# ---------------------------------------------------------------------------

@app.get("/notifications/track/<notification_id>.gif")
def track_open(path: NotificationPath):
    """
    Called automatically when the recipient opens the email.
    Marks the notification as opened (first open only) and returns the pixel.
    No API key required.
    """
    notification = db.session.get(Notification, path.notification_id)
    if notification and notification.status == "sent":
        notification.status = "opened"
        notification.opened_at = datetime.now(timezone.utc)
        db.session.commit()
        log.info("Notification opened: %s", path.notification_id)

    return Response(TRANSPARENT_GIF, mimetype="image/gif", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma":        "no-cache",
    })


# ---------------------------------------------------------------------------
# Notification records
# ---------------------------------------------------------------------------

@app.get("/notifications", security=_API_SECURITY)
def list_notifications(query: NotificationQuery):
    """List all sent notifications, with optional filtering."""
    q = Notification.query

    if query.status:
        if query.status not in ("sent", "opened"):
            return jsonify({"error": "status must be 'sent' or 'opened'"}), 400
        q = q.filter_by(status=query.status)

    if query.to:
        q = q.filter_by(to=query.to)

    notifications = q.order_by(db.desc(Notification.sent_at)).all()
    return jsonify({"notifications": [n.to_dict() for n in notifications]}), 200


@app.get("/notifications/<notification_id>", security=_API_SECURITY)
def get_notification(path: NotificationPath):
    """Return details and read status of a specific notification."""
    notification = db.session.get(Notification, path.notification_id)
    if not notification:
        return jsonify({"error": "notification not found"}), 404

    return jsonify(notification.to_dict()), 200


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@app.get("/notifications/templates", security=_API_SECURITY)
def list_templates():
    """Return the list of all available email templates."""
    return jsonify({"templates": list(TEMPLATES.keys())}), 200


@app.get("/notifications/templates/<template>", security=_API_SECURITY)
def get_template(path: TemplatePath):
    """Return template details including required data fields."""
    if path.template not in TEMPLATES:
        return jsonify({"error": "template not found"}), 404

    return jsonify({
        "template": path.template,
        "fields": TEMPLATES[path.template],
    }), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

@app.get("/metrics")
def get_metrics():
    try:
        sent = Notification.query.filter_by(status="sent").count()
        opened = Notification.query.filter_by(status="opened").count()
        failed = Notification.query.filter_by(status="failed").count()
    except Exception:
        sent = opened = failed = 0
    
    metrics = [
        f"notifications_emails_total{{status=\"sent\"}} {sent}",
        f"notifications_emails_total{{status=\"opened\"}} {opened}",
        f"notifications_emails_total{{status=\"failed\"}} {failed}",
    ]
    return Response("\n".join(metrics) + "\n", mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
