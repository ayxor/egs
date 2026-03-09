# Notifications Service

The Notifications service is a generic, template-based email delivery service. It is entirely agnostic to platform business logic — it does not decide when to send emails, to whom, or why. It only sends emails when explicitly instructed to do so by the Composer.

This design makes the service reusable across other projects that require transactional email delivery.

**This service is accessible only by internal services via API key.**

---

## Email Delivery Model

The service accepts a request containing a recipient, subject, template name, and a data object. It queues the email for delivery and responds with `202 Accepted`, indicating that delivery is guaranteed to be attempted, not that it has already occurred. Sending is asynchronous.

The `data` object must contain the key-value pairs required by the chosen template. Use `GET /notifications/templates/{template}` to discover which fields a given template expects.

---

## API Reference

Base URL: `http://notifications:8080`

All requests must include the header `X-API-Key: <key>`.

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

| Response | Description |
|---|---|
| `202 Accepted` | Email accepted for delivery (asynchronous) |
| `400 Bad Request` | Missing or invalid required fields |
| `404 Not Found` | Template does not exist |

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
pip install -r requirements.txt
python app.py   # listens on :8080
```

### Environment variables

| Variable | Description |
|---|---|
| `NOTIFICATIONS_API_KEY` | Shared secret expected in the `X-API-Key` header (default: `stub-api-key`) |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP server port (default: `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |

### Docker

> To be completed.
