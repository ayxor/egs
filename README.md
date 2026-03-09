# Video Editor Service

The Video Editor service is a generic, asynchronous media processing service. It receives a source file via a URL, applies a sequence of requested operations, and delivers the result to a destination URL. It has no knowledge of users, institutions, the Object Storage service, or any other platform component.

All URLs are provided by the Composer at request time, guaranteeing total loose coupling. The Video Editor does not care whether those URLs point to Object Storage, the Composer itself, or any other system.

**This service is accessible only by internal services via API key.**

---

## Processing Model

1. The Composer submits a job with `src_url`, `dst_url`, `progress_url`, and `operations`.
2. The Video Editor fetches the source file via `GET src_url`.
3. It processes the file according to the specified operations.
4. It streams progress updates to `progress_url` via SSE.
5. It delivers the processed file via `PUT dst_url`.

---

## API Reference

Base URL: `http://video-editor:8080`

All requests must include the header `X-API-Key: <key>`.

### Jobs

| Method | Path | Description |
|---|---|---|
| `POST` | `/jobs` | Create and start a new processing job. |
| `GET` | `/jobs/{job_id}` | Poll the current status of a job. |
| `GET` | `/jobs/{job_id}/progress` | Stream real-time job progress via SSE. |
| `GET` | `/jobs/{job_id}/operations` | Retrieve the operations applied to a specific job. |
| `GET` | `/jobs/operations` | List all operations supported by this service. |

---

**POST /jobs**

Creates a processing job and starts it asynchronously. Returns immediately with a `job_id`.

Request body:
```json
{
  "src_url": "https://object-storage/objects/universidade-aveiro/raw/abc123.mp4?token=...",
  "dst_url": "https://object-storage/objects/universidade-aveiro/processed/abc123.mp4?token=...",
  "progress_url": "https://composer/internal/jobs/progress",
  "operations": [
    {
      "type": "watermark",
      "params": {
        "text": "UA",
        "position": "bottom-right",
        "opacity": 0.8
      }
    }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `src_url` | Yes | HTTP URL from which to fetch the source file (GET) |
| `dst_url` | Yes | HTTP URL to which to deliver the processed file (PUT) |
| `progress_url` | No | HTTP URL to which to POST SSE progress updates |
| `operations` | Yes | Ordered list of operations to apply |

| Response | Description |
|---|---|
| `202 Accepted` | `{ "job_id": "job_7f3a1b" }` — job started asynchronously |
| `400 Bad Request` | Missing or invalid required fields |
| `422 Unprocessable Entity` | Unknown or unsupported operation type |

---

**GET /jobs/{job_id}**

Returns the current status of a job. Use this as an alternative to SSE in contexts where streaming is not viable.

| Response | Description |
|---|---|
| `200 OK` | Job status object (see below) |
| `404 Not Found` | Job does not exist |

Response body:
```json
{
  "job_id": "job_7f3a1b",
  "status": "processing",
  "percent": 45,
  "created_at": "2024-03-01T10:00:00Z",
  "updated_at": "2024-03-01T10:01:23Z"
}
```

Status values: `queued` · `processing` · `done` · `failed`

---

**GET /jobs/{job_id}/progress**

Opens a Server-Sent Events stream that emits real-time progress updates. The stream closes automatically when the job reaches `done` or `failed`.

`Content-Type: text/event-stream`

```
data: {"job_id": "job_7f3a1b", "percent": 0, "status": "started"}

data: {"job_id": "job_7f3a1b", "percent": 45, "status": "processing"}

data: {"job_id": "job_7f3a1b", "percent": 100, "status": "done"}
```

| Response | Description |
|---|---|
| `200 OK` | SSE stream opened |
| `404 Not Found` | Job does not exist |

---

**GET /jobs/operations**

Returns the full list of operations supported by this service instance, along with their available parameters.

Response `200 OK`:
```json
{
  "operations": [
    { "type": "watermark", "params": ["text", "position", "opacity"] },
    { "type": "rotate", "params": ["degrees"] }
  ]
}
```

---

**GET /jobs/{job_id}/operations**

Returns the operations that were requested for a specific job.

| Response | Description |
|---|---|
| `200 OK` | Operations applied to the job |
| `404 Not Found` | Job does not exist |

---

## Deployment

> To be completed. A `Dockerfile` and environment variable reference will be provided here, including API key configuration and any dependencies required by the processing operations (e.g. FFmpeg).
