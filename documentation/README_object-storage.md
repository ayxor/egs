# Object Storage Service

Object Storage is the binary file store branch. It is agnostic to UAStream business logic and stores arbitrary objects by bucket and key.

## Role In The Stack

- Composer uploads and reads platform media from here
- Video Editor writes processed files here
- The service authenticates with API keys, not JWTs

This branch is the byte-level storage backend, so the README focuses on bucket names, key paths, and direct download semantics rather than higher-level media workflows.

## API Reference

Internal base URL: `http://object-storage:5000`

All requests must include `X-API-Key: <key>`.

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
| `PUT` | `/objects/{bucket}?key={key}` | Upload a binary object (Query Style). |
| `PUT` | `/objects/{bucket}/{key}` | Upload a binary object (Path-Key Style). |
| `GET` | `/objects/{bucket}/{key}` | Download a binary object. Supports HTTP Range requests. |
| `DELETE` | `/objects/{bucket}?key={key}` | Delete an object (Query Style). |
| `DELETE` | `/objects/{bucket}/{key}` | Delete an object (Path-Key Style). |

**GET /objects/{bucket}**

Supports pagination query parameters: `limit` (default: 50) and `offset` (default: 0).
Also supports a `query` parameter to substring search item keys `?query=substring`.

| Response | Description |
|---|---|
| `200 OK` | `{ "objects": ["raw/abc123.mp4"], "total": 1, "limit": 50, "offset": 0, "query": "" }` |
| `404 Not Found` | Bucket does not exist |

**PUT /objects/{bucket}?key={key}**  
**PUT /objects/{bucket}/{key}**

Request body: raw binary (`Content-Type: application/octet-stream`).

| Response | Description |
|---|---|
| `201 Created` | `{ "bucket": "universidade-aveiro", "key": "raw/abc123.mp4" }` |
| `400 Bad Request` | Invalid bucket or key |

*Note: The path-style format `/objects/{bucket}/{key}` is the preferred method used internally by the Composer orchestrator to store and retrieve files.*

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
**DELETE /objects/{bucket}/{key}**

| Response | Description |
|---|---|
| `204 No Content` | Object deleted |
| `404 Not Found` | Bucket or key does not exist |

**POST /objects/{bucket}/{key}/presign**

This endpoint returns a temporary download token for public-style access through the platform routing layer.
The current implementation is a stub and should be treated as a placeholder, not a hardened production presign service.

---

## Runtime

### Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py   # listens on :5000 by default
```

*Note on Ports:* When running `app.py` directly, it listens on port `5000`. When deployed within the Docker container/Kubernetes cluster, it listens on port `8080` as configured by the Dockerfile (`FLASK_RUN_PORT=8080`).

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

The service is built and started from the `object-storage` branch through the `main` stack compose file.

## Notes

- Buckets are used as institution namespaces.
- Keys map directly to file paths inside each bucket.
- `uastream.com` is the public hostname for the stack, but object storage itself is an internal service.
- Range requests are the main mechanism for direct playback and chunked delivery.

### Production Scaling & Replicas (ReadWriteOnce Constraints)
In the current Kubernetes deployment, the `object-storage` service runs as a single replica (`replicas: 1`) using a `ReadWriteOnce` (RWO) Persistent Volume.
* **Why it is not scaled to >1 replica:**
  1. A `ReadWriteOnce` volume can only be mounted to a single node. Setting `replicas: 2` would trigger a `Multi-Attach error` when the pods are scheduled on different nodes.
  2. Changing the volume type to `ReadWriteMany` (RWX) to scale the service would introduce network filesystem (NFS) performance overhead and latency during high-throughput range-request video streaming chunking.
* **Production Path:** To scale this service in a real production-grade deployment, the filesystem storage backend should be replaced with an S3-compatible API backend (like AWS S3 or a MinIO cluster). This removes the need for local persistent volumes, making the service completely stateless and infinitely scalable.

---

## Diagrams

### Service Architecture & Flowchart

This diagram details the Object Storage's internal layout, illustrating direct range requests for chunked video playback and the generation of SHA256 HMAC presigned tokens.

```mermaid
flowchart TB
    Client["🌐 Client / Browser"]
    Orch["🧠 Composer Orchestrator"]
    
    subgraph ObjectStorage["Object Storage Container"]
        API["REST API\n(Verify Token or X-API-Key)"]
        Presigner["POST /objects/{bucket}/{key}/presign\n(Generate SHA256 HMAC Token)"]
        RangeHandler["GET /objects/{bucket}/{key}\n(Range Header check)"]
        
        subgraph Disk["Local Disk Backend"]
            BucketDir["data/{bucket-name}/"]
            NestedDir["raw/ | processed/ | thumbnails/"]
            BinaryFile[["video.mp4 | thumbnail.jpg"]]
        end
    end

    Orch -->|1. Request Presigned URL| Presigner
    Presigner -->|2. Return signed URL with expiry token| Orch
    Orch -->|3. Send signed URL| Client

    Client -->|4. GET video stream with Range: bytes=X-Y| API
    API --> RangeHandler
    RangeHandler -->|5. Verify signature token & expiry| RangeHandler
    RangeHandler -->|6. file.seek(X) & read(Y-X)| BinaryFile
    RangeHandler -->|7. Return 206 Partial Content + Range Header| Client

    BucketDir --> NestedDir
    NestedDir --> BinaryFile
```
