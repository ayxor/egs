"""
Notifications Service - Stub
Branch: notifications

Generic, template-based transactional email delivery service.
Completely agnostic to business logic — only sends emails when asked to by the Composer.
Accessible only by internal services via API key.

Run:
    pip install flask
    python app.py
"""

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# ---------------------------------------------------------------------------
# API key auth
# ---------------------------------------------------------------------------

API_KEY = os.environ.get("NOTIFICATIONS_API_KEY", "stub-api-key")

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
    "welcome":        ["name"],
    "upload_complete": ["name", "title"],
}


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@app.route("/notifications/email", methods=["POST"])
def send_email():
    """
    Accept an email request and queue it for delivery (asynchronous).
    Returns 202 Accepted — guarantees an attempt, not delivery.
    TODO:
      1. Render the chosen template with the supplied data fields
      2. Queue the rendered message for SMTP / third-party delivery
         (e.g. SendGrid, Mailgun, AWS SES)
    """
    err = _require_api_key()
    if err:
        return err

    body = request.get_json(force=True) or {}
    for field in ("to", "subject", "template", "data"):
        if not body.get(field) and body.get(field) != {}:
            return jsonify({"error": f"missing required field: {field}"}), 400

    template_name = body["template"]
    if template_name not in TEMPLATES:
        return jsonify({"error": "template not found"}), 404

    # Validate that all required data fields are present
    required_fields = TEMPLATES[template_name]
    data = body.get("data", {})
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({"error": f"missing data fields for template: {missing}"}), 400

    # TODO: actually render and send the email
    print(
        f"[STUB] Would send email to={body['to']} "
        f"subject='{body['subject']}' template={template_name} data={data}"
    )

    return "", 202


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
