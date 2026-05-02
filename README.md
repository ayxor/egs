# Notifications Service

Notifications is the UAStream transactional email service. It is a small, API-key-protected worker that only sends email when Composer asks it to.

## Role In The Stack

- Composer is the only service that should call Notifications
- The service does not decide business events on its own
- It sends template-based email and records delivery/open status

## How It Works

The service accepts a recipient, subject, template name, and data payload. It stores a `Notification` record, renders the template, sends the email, and returns `202 Accepted` with a `notification_id`.

Outgoing messages include a tracking pixel so open events can be recorded best-effort. Some mail clients block external images, so open tracking is not guaranteed.

## Public URL

- API docs: `http://uastream.com/openapi/swagger`
- Public tracking endpoint: `http://uastream.com/notifications/track/...`

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Docker

```bash
docker build -t notifications .
docker run -p 8080:8080 notifications
```

## Notes

- SMTP settings are provided by the stack environment, not hardcoded in the service.
- The service is reachable publicly through Traefik, but it is still treated as an internal platform component.
