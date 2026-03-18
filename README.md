# Object Storage Service

The Object Storage service is a generic binary file store. It is entirely agnostic to the type of content it holds — it has no knowledge of videos, users, institutions, or any other platform concept. It accepts, stores, and serves arbitrary binary objects.

This design makes the service reusable beyond the video platform, for instance for storing PDFs, images, or audio files in other projects.

**This service is accessible only by internal services (Composer, Video Editor) via API key. It does not validate JWTs.**

Objects are organised using a `bucket` as a namespace (one per institution) and a `key` as the file identifier within that bucket (e.g. `raw/abc123.mp4`, `processed/abc123.mp4`).

---

## API Reference

Base URL: `http://object-storage:5000`

All requests must include the header `X-API-Key: <key>`.

### Buckets

| Method | Path | Description |
|---|---|---|
| `GET` | `/buckets` | List all buckets (paginated). |
| `PUT` | `/buckets/{bucket}` | Create a new bucket (namespace). |
| `DELETE` | `/buckets/{bucket}` | Delete a bucket and all its contents. |

**GET /buckets**

Supports pagination query parameters: `limit` (default: 50) and `offset` (default: 0).
Also supports a `query` parameter to substring search bucket names `?query=substring`.

| Response | Description |
|---|---|
| `200 OK` | `{ "buckets": ["universidade-aveiro"], "total": 1, "limit": 50, "offset": 0, "query": "" }` |

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
| `GET` | `/objects/{bucket}` | List all object keys in a bucket (paginated). |
| `PUT` | `/objects/{bucket}?key={key}` | Upload a binary object. |
| `GET` | `/objects/{bucket}/{key}` | Download a binary object. Supports HTTP Range requests. |
| `DELETE` | `/objects/{bucket}?key={key}` | Delete an object. |

**GET /objects/{bucket}**

Supports pagination query parameters: `limit` (default: 50) and `offset` (default: 0).
Also supports a `query` parameter to substring search item keys `?query=substring`.

| Response | Description |
|---|---|
| `200 OK` | `{ "objects": ["raw/abc123.mp4"], "total": 1, "limit": 50, "offset": 0, "query": "" }` |
| `404 Not Found` | Bucket does not exist |

**PUT /objects/{bucket}?key={key}**

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

**DELETE /objects/{bucket}?key={key}**

| Response | Description |
|---|---|
| `204 No Content` | Object deleted |
| `404 Not Found` | Bucket or key does not exist |

---

## Deployment

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py   # listens on :5000
```

### Environment variables

| Variable | Description |
|---|---|
| `OBJECT_STORAGE_API_KEY` | Shared secret expected in the `X-API-Key` header (default: `stub-api-key`) |
| `OBJECT_STORAGE_DATA_DIR` | Path to the directory where data corresponds to (default: `./data`) |

### Storage Backend and Folder Structure

The current iteration of the application uses the local file system to store and persist binary objects.
The chosen root structure resides in a `data/` directory.

```text
data/
└── {bucket-name}/
    └── {object-key-path...}
```

- Each bucket corresponds to a top-level directory inside `data/` (e.g. `data/universidade-aveiro/`).
- Keys are mapped directly as files or nested folders in that specific bucket's directory (e.g. key `raw/abc123.mp4` lives at `data/universidade-aveiro/raw/abc123.mp4`).

### Docker

> To be completed.
