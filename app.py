"""
Notifications Service - Stub
Branch: notifications

Generic, template-based transactional email delivery service.
Completely agnostic to business logic — only sends emails when asked to by the Composer.
Accessible only by internal services via API key.

Run:
    pip install flask flask-sqlalchemy
    python app.py
"""

from flask import Flask, request, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import os
import uuid

app = Flask(__name__)

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
# In production this should point to a publicly reachable hostname.
BASE_URL = os.environ.get("NOTIFICATIONS_BASE_URL", "http://localhost:8080")


def _require_api_key():
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return jsonify({"error": "unauthorized"}), 401
    return None


# ---------------------------------------------------------------------------
# Template registry
# Each template declares which data fields it expects.
# TODO: load from files/DB; add real rendering (e.g. Jinja2 + SMTP send).
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, list[str]] = {
    "welcome":         ["name"],
    "upload_complete": ["name", "title"],
}


# ---------------------------------------------------------------------------
# Database model
# ---------------------------------------------------------------------------

class Notification(db.Model):
    __tablename__ = "notifications"

    id        = db.Column(db.String(36), primary_key=True)
    to        = db.Column(db.String(255), nullable=False)
    subject   = db.Column(db.String(500), nullable=False)
    template  = db.Column(db.String(100), nullable=False)
    # status: "sent" | "opened"
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
# GIF89a with GCT + Graphic Control Extension (transparency index 0) + image data.
# ---------------------------------------------------------------------------

TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00"  # header + logical screen descriptor (GCT present)
    b"\x00\x00\x00\x00\x00\x00"             # GCT: 2 entries, both black/transparent
    b"\x21\xf9\x04\x01\x00\x00\x00\x00"    # Graphic Control Extension (transparent index=0)
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"  # image descriptor
    b"\x02\x02\x4c\x01\x00"                 # image data (LZW)
    b"\x3b"                                 # trailer
)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@app.route("/notifications/email", methods=["POST"])
def send_email():
    """
    Accept an email request, persist a Notification record, and queue it
    for delivery (asynchronous).
    Returns 202 Accepted — guarantees an attempt, not delivery.
    TODO:
      1. Render the chosen template with the supplied data fields,
         injecting the tracking pixel <img> tag into the HTML body.
      2. Queue the rendered message for SMTP / third-party delivery
         (e.g. SendGrid, Mailgun, AWS SES).
    """
    err = _require_api_key()
    if err:
        return err

    body = request.get_json(force=True) or {}

    for field in ("to", "subject", "template"):
        if not body.get(field):
            return jsonify({"error": f"missing required field: {field}"}), 400
    if "data" not in body:
        return jsonify({"error": "missing required field: data"}), 400

    template_name = body["template"]
    if template_name not in TEMPLATES:
        return jsonify({"error": "template not found"}), 404

    required_fields = TEMPLATES[template_name]
    data = body.get("data", {})
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"error": f"missing data fields for template: {missing}"}), 400

    # Persist notification record
    notification = Notification(
        to=body["to"],
        subject=body["subject"],
        template=template_name,
    )
    db.session.add(notification)
    db.session.commit()

    # TODO: actually render and send the email, embedding the tracking pixel:
    #   <img src="{BASE_URL}/notifications/track/{notification.id}.gif"
    #        width="1" height="1" style="display:none">
    print(
        f"[STUB] Would send email to={body['to']} "
        f"subject='{body['subject']}' template={template_name} data={data} "
        f"notification_id={notification.id}"
    )

    return jsonify({"notification_id": notification.id}), 202


# ---------------------------------------------------------------------------
# Tracking pixel
# ---------------------------------------------------------------------------

@app.route("/notifications/track/<notification_id>.gif", methods=["GET"])
def track_open(notification_id):
    """
    Called automatically when the recipient opens the email (the mail client
    loads the embedded 1x1 pixel image).
    Marks the notification as opened (first open only) and returns the pixel.
    No API key required — this URL is hit by external mail clients.
    """
    notification = db.session.get(Notification, notification_id)
    if notification and notification.status == "sent":
        notification.status = "opened"
        notification.opened_at = datetime.now(timezone.utc)
        db.session.commit()

    return Response(TRANSPARENT_GIF, mimetype="image/gif", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma":        "no-cache",
    })


# ---------------------------------------------------------------------------
# Notification records
# ---------------------------------------------------------------------------

@app.route("/notifications", methods=["GET"])
def list_notifications():
    """
    Return a list of all sent notifications with their read status.
    Optional query params:
      - status: filter by 'sent' or 'opened'
      - to:     filter by recipient email
    """
    err = _require_api_key()
    if err:
        return err

    query = Notification.query

    status_filter = request.args.get("status")
    if status_filter:
        if status_filter not in ("sent", "opened"):
            return jsonify({"error": "status must be 'sent' or 'opened'"}), 400
        query = query.filter_by(status=status_filter)

    to_filter = request.args.get("to")
    if to_filter:
        query = query.filter_by(to=to_filter)

    notifications = query.order_by(db.desc(Notification.sent_at)).all()
    return jsonify({"notifications": [n.to_dict() for n in notifications]}), 200


@app.route("/notifications/<notification_id>", methods=["GET"])
def get_notification(notification_id):
    """Return the details and read status of a specific notification."""
    err = _require_api_key()
    if err:
        return err

    notification = db.session.get(Notification, notification_id)
    if not notification:
        return jsonify({"error": "notification not found"}), 404

    return jsonify(notification.to_dict()), 200


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@app.route("/notifications/templates", methods=["GET"])
def list_templates():
    """Return the list of all available email templates."""
    err = _require_api_key()
    if err:
        return err

    return jsonify({"templates": list(TEMPLATES.keys())}), 200


@app.route("/notifications/templates/<template>", methods=["GET"])
def get_template(template):
    """
    Return the details of a specific template, including required data fields.
    Useful for callers to discover what keys the data object must contain.
    """
    err = _require_api_key()
    if err:
        return err

    if template not in TEMPLATES:
        return jsonify({"error": "template not found"}), 404

    return jsonify({
        "template": template,
        "fields": TEMPLATES[template],
    }), 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)