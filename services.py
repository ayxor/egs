"""HTTP clients for internal platform services."""

import logging

import requests

import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Object Storage
# ═══════════════════════════════════════════════════════════════════════════

def _storage_headers():
    return {"X-API-Key": config.OBJECT_STORAGE_API_KEY}


def ensure_bucket(bucket):
    """Create the bucket if it does not already exist (idempotent)."""
    resp = requests.put(
        f"{config.OBJECT_STORAGE_URL}/buckets/{bucket}",
        headers=_storage_headers(),
        timeout=10,
    )
    # 201 Created or 409 Conflict (already exists) are both acceptable
    return resp.status_code in (201, 409)


def download_object_stream(bucket, key):
    """Download binary data from Object Storage as a stream."""
    resp = requests.get(
        f"{config.OBJECT_STORAGE_URL}/objects/{bucket}/{key}",
        headers=_storage_headers(),
        stream=True,
    )
    return resp


def upload_object_stream(bucket, key, data, content_type="application/octet-stream"):
    """Proxy upload binary data to Object Storage."""
    resp = requests.put(
        f"{config.OBJECT_STORAGE_URL}/objects/{bucket}/{key}",
        headers={**_storage_headers(), "Content-Type": content_type},
        data=data,
    )
    return resp


def upload_object(bucket, key, data, content_type="application/octet-stream"):
    """Upload binary data to Object Storage."""
    resp = requests.put(
        f"{config.OBJECT_STORAGE_URL}/objects/{bucket}/{key}",
        headers={**_storage_headers(), "Content-Type": content_type},
        data=data,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


def delete_object(bucket, key):
    """Delete an object from Object Storage."""
    resp = requests.delete(
        f"{config.OBJECT_STORAGE_URL}/objects/{bucket}/{key}",
        headers=_storage_headers(),
        timeout=10,
    )
    return resp.status_code == 204


def presign_object(bucket, key, method="GET", expires_in=None):
    """Generate a temporary presigned URL for an object."""
    if expires_in is None:
        expires_in = config.PRESIGNED_URL_EXPIRY
    resp = requests.post(
        f"{config.OBJECT_STORAGE_URL}/objects/{bucket}/{key}/presign",
        headers=_storage_headers(),
        json={"method": method, "expires_in": expires_in},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
# Video Editor
# ═══════════════════════════════════════════════════════════════════════════

def _editor_headers():
    return {"X-API-Key": config.VIDEO_EDITOR_API_KEY}


def create_job(src_url, dst_url, progress_url, operations):
    """Submit a processing job to the Video Editor."""
    resp = requests.post(
        f"{config.VIDEO_EDITOR_URL}/jobs",
        headers=_editor_headers(),
        json={
            "src_url": src_url,
            "dst_url": dst_url,
            "progress_url": progress_url,
            "operations": operations,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def stream_job_progress(job_id):
    """Subscribe to the Video Editor SSE stream for a job.

    Yields raw SSE ``data: ...`` lines (each terminated by double-newline).
    """
    resp = requests.get(
        f"{config.VIDEO_EDITOR_URL}/jobs/{job_id}/progress",
        headers=_editor_headers(),
        stream=True,
        timeout=(10, 600),
    )
    resp.raise_for_status()
    for line in resp.iter_lines(decode_unicode=True):
        if line and line.startswith("data:"):
            yield line + "\n\n"


# ═══════════════════════════════════════════════════════════════════════════
# Notifications
# ═══════════════════════════════════════════════════════════════════════════

def _notify_headers():
    return {"X-API-Key": config.NOTIFICATIONS_API_KEY}


def send_email(to, subject, template, data):
    """Queue an email for delivery via the Notifications service.

    Fire-and-forget: logs errors but never raises.
    """
    try:
        resp = requests.post(
            f"{config.NOTIFICATIONS_URL}/notifications/email",
            headers=_notify_headers(),
            json={
                "to": to,
                "subject": subject,
                "template": template,
                "data": data,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to send notification email: %s", exc)
