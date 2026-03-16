# Notifications Service

The Notifications service is a generic, template-based email delivery service. It is entirely agnostic to platform business logic — it does not decide when to send emails, to whom, or why. It only sends emails when explicitly instructed to do so by the Composer.

This design makes the service reusable across other projects that require transactional email delivery.

**This service is accessible only by internal services via API key.**

---

## Email Delivery Model

The service accepts a request containing a recipient, subject, template name, and a data object. It persists a `Notification` record in the database, queues the email for delivery, and responds with `202 Accepted` alongside a `notification_id`. The `notification_id` can later be used to query the open/read status of that email.

The `data` object must contain the key-value pairs required by the chosen template. Use `GET /notifications/templates/{template}` to discover which fields a given template expects.

---

## Open Tracking

Each email contains an invisible 1×1 pixel image whose `src` points to:

```
GET /notifications/track/{notification_id}.gif
```

When the recipient opens the email and their mail client renders the HTML body, it fetches this image. The service records the `opened_at` timestamp and updates the notification status from `sent` to `opened`.

> **Note:** This endpoint does **not** require an API key — it must be reachable by external mail clients. Open tracking is best-effort: some mail clients block external images by default.

The `NOTIFICATIONS_BASE_URL` environment variable controls the hostname embedded in the tracking pixel URL. Set it to a publicly reachable address in production.

---

## API Reference

Base URL: `http://notifications:8080`

All requests must include the header `X-API-Key: <key>`, **except** the tracking pixel endpoint.

### Email

| Method | Path | Description |
|---|---|---|
| `POST` | `/notifications/email` | Queue an email for delivery. |

**POST /notifications/email**

Request body:
```json
{
  "to": "professor@ua.pt",
  "subject": "Vídeo submetido com sucesso",
  "template": "upload_complete",
  "data": {
    "name": "Professor Silva",
    "title": "Aula 1 - VHDL"
  }
}
```

| Field | Required | Description |
|---|---|---|
| `to` | Yes | Recipient email address |
| `subject` | Yes | Email subject line |
| `template` | Yes | Name of the template to render |
| `data` | Yes | Key-value pairs required by the template |

Response `202 Accepted`:
```json
{
  "notification_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

| Response | Description |
|---|---|
| `202 Accepted` | Email accepted for delivery; `notification_id` returned |
| `400 Bad Request` | Missing or invalid required fields |
| `404 Not Found` | Template does not exist |

---

### Tracking Pixel

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/notifications/track/{notification_id}.gif` | None | Mark notification as opened; return 1×1 GIF. |

Embedded automatically in every outgoing HTML email. Called by the recipient's mail client on open. Idempotent — only the first request updates the status.

---

### Notification Records

| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications` | List all notifications with open/read status. |
| `GET` | `/notifications/{notification_id}` | Get details of a specific notification. |

**GET /notifications**

Optional query parameters:

| Param | Description |
|---|---|
| `status` | Filter by `sent` or `opened` |
| `to` | Filter by recipient email address |

Response `200 OK`:
```json
{
  "notifications": [
    {
      "notification_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "to": "professor@ua.pt",
      "subject": "Vídeo submetido com sucesso",
      "template": "upload_complete",
      "status": "opened",
      "sent_at": "2024-01-15T10:30:00+00:00",
      "opened_at": "2024-01-15T11:05:00+00:00",
      "tracking_pixel": "http://notifications:8080/notifications/track/3fa85f64-5717-4562-b3fc-2c963f66afa6.gif"
    }
  ]
}
```

**GET /notifications/{notification_id}**

Response `200 OK`:
```json
{
  "notification_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "to": "professor@ua.pt",
  "subject": "Vídeo submetido com sucesso",
  "template": "upload_complete",
  "status": "sent",
  "sent_at": "2024-01-15T10:30:00+00:00",
  "opened_at": null,
  "tracking_pixel": "http://notifications:8080/notifications/track/3fa85f64-5717-4562-b3fc-2c963f66afa6.gif"
}
```

| Response | Description |
|---|---|
| `200 OK` | Notification record returned |
| `404 Not Found` | Notification does not exist |

---

### Templates

| Method | Path | Description |
|---|---|---|
| `GET` | `/notifications/templates` | List all available templates. |
| `GET` | `/notifications/templates/{template}` | Get the fields required by a specific template. |

**GET /notifications/templates**

Response `200 OK`:
```json
{
  "templates": ["welcome", "upload_complete"]
}
```

**GET /notifications/templates/{template}**

Response `200 OK`:
```json
{
  "template": "upload_complete",
  "fields": ["name", "title"]
}
```

| Response | Description |
|---|---|
| `200 OK` | Template details returned |
| `404 Not Found` | Template does not exist |

---

## Available Templates

| Template | Required fields | Triggered when |
|---|---|---|
| `welcome` | `name` | A new user completes registration |
| `upload_complete` | `name`, `title` | A professor's video upload finishes |

---

## Deployment

### Run locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py   # listens on :8080
```

### Environment variables

| Variable | Description |
|---|---|
| `NOTIFICATIONS_API_KEY` | Shared secret expected in the `X-API-Key` header (default: `stub-api-key`) |
| `NOTIFICATIONS_BASE_URL` | Public base URL for tracking pixel links (default: `http://localhost:8080`) |
| `DATABASE_URL` | SQLAlchemy database URL (default: `sqlite:///notifications.db`) |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP server port (default: `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |

### Docker

> To be completed.
