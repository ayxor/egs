# Object Storage Service

The Object Storage service is a generic binary file store. It is entirely agnostic to the type of content it holds — it has no knowledge of videos, users, institutions, or any other platform concept. It accepts, stores, serves, and generates presigned URLs for arbitrary binary objects.

This design makes the service reusable beyond the video platform, for instance for storing PDFs, images, or audio files in other projects.

**This service is accessible only by internal services (Composer, Video Editor) via API key. It does not validate JWTs.**

Objects are organised using a `bucket` as a namespace (one per institution) and a `key` as the file identifier within that bucket (e.g. `raw/abc123.mp4`, `processed/abc123.mp4`).

---

## API Reference

Base URL: `http://object-storage:8080`

All requests must include the header `X-API-Key: <key>`.

### Buckets

| Method | Path | Description |
|---|---|---|
| `PUT` | `/buckets/{bucket}` | Create a new bucket (namespace). |
| `DELETE` | `/buckets/{bucket}` | Delete a bucket and all its contents. |

**PUT /buckets/{bucket}**

| Response | Description |
|---|---|
| `201 Created` | `{ "bucket": "universidade-aveiro" }` |
| `409 Conflict` | Bucket already exists |

**DELETE /buckets/{bucket}**

| Response | Description |
|---|---|
| `204 No Content` | Bucket deleted |
| `404 Not Found` | Bucket does not exist |

---

### Objects

| Method | Path | Description |
|---|---|---|
| `PUT` | `/objects/{bucket}/{key}` | Upload a binary object. |
| `GET` | `/objects/{bucket}/{key}` | Download a binary object. Supports HTTP Range requests. |
| `DELETE` | `/objects/{bucket}/{key}` | Delete an object. |
| `POST` | `/objects/{bucket}/{key}/presign` | Generate a temporary presigned URL for direct access. |

**PUT /objects/{bucket}/{key}**

Request body: raw binary (`Content-Type: application/octet-stream`).

| Response | Description |
|---|---|
| `201 Created` | `{ "bucket": "universidade-aveiro", "key": "raw/abc123.mp4" }` |
| `400 Bad Request` | Invalid bucket or key |

**GET /objects/{bucket}/{key}**

Supports an optional `Range` header for partial content (e.g. video streaming):

```
Range: bytes=0-1023
```

| Response | Description |
|---|---|
| `200 OK` | Full object returned |
| `206 Partial Content` | Partial content returned in response to a Range request |
| `404 Not Found` | Bucket or key does not exist |

**DELETE /objects/{bucket}/{key}**

| Response | Description |
|---|---|
| `204 No Content` | Object deleted |
| `404 Not Found` | Bucket or key does not exist |

**POST /objects/{bucket}/{key}/presign**

Generates a temporary, scoped URL for direct client or service access to an object. `PUT` presigned URLs are used by the Composer to provide the Video Editor with an upload destination.

Request body:
```json
{
  "method": "GET",
  "expires_in": 3600
}
```

| Field | Values | Description |
|---|---|---|
| `method` | `GET` or `PUT` | Whether the URL grants download or upload access |
| `expires_in` | integer (seconds) | How long the URL remains valid |

| Response | Description |
|---|---|
| `200 OK` | `{ "url": "http://...", "expires_at": "2024-03-01T11:00:00Z" }` |
| `404 Not Found` | Bucket or key does not exist |

---

## Deployment

> To be completed. A `Dockerfile` and environment variable reference will be provided here, including API key configuration and the storage backend used.
