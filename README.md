# Notifications Service

Generic, template-based transactional email delivery service. Completely agnostic to platform business logic — it does not decide when to send emails, to whom, or why. It only sends emails when explicitly instructed by the Composer.

**Accessible only by internal services via API key.**

---

## How it works

The service accepts a request with a recipient, subject, template name, and a data object. It persists a `Notification` record, sends the email, and responds with `202 Accepted` and a `notification_id`. That ID can later be used to query the open/read status of the email.

Each outgoing email embeds an invisible 1×1 tracking pixel. When the recipient opens the email, their mail client fetches the pixel and the service records the `opened_at` timestamp, updating the status from `sent` to `opened`. Open tracking is best-effort — some mail clients block external images.

---

## API Reference

Once the service is running, the full interactive API documentation is available at:

```
http://localhost:8080/openapi/swagger
```

Click **Authorize** and enter the API key to authenticate requests directly from the browser.

## Deployment

### Run locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Docker

```bash
docker build -t notifications .
docker run -p 8080:8080 notifications
```
