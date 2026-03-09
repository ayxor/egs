# Composer Service

The Composer is the central orchestrator of the EGS Video Platform. It is the sole external entry point for all client interactions and the only component that communicates with other internal services. No other service calls another service directly.

---

## Responsibilities

- Authenticating and authorising all incoming requests by validating JWTs against the Keycloak public key
- Registering users in Keycloak and storing their profile metadata
- Accepting video uploads, persisting metadata, and coordinating storage and processing
- Orchestrating the Video Editor for processing jobs and relaying real-time progress to clients via SSE
- Generating presigned URLs for clients to stream video directly from Object Storage
- Dispatching email notifications through the Notifications service
- Providing search and listing of videos scoped to the authenticated user's institution

The Composer owns a PostgreSQL database for video metadata (title, description, tags, course, subject, storage key, uploader) and user profile data. It does not store passwords or generate tokens — those are Keycloak's responsibility.

---

## API Reference

All endpoints require the header `Authorization: Bearer <JWT>` unless stated otherwise.

### Authentication

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/auth/login` | No | Login with email and password. Returns `access_token`, `refresh_token`, `expires_in`. |
| `POST` | `/auth/refresh` | No | Refresh an expired access token using a `refresh_token`. |

**POST /auth/login** — Request body:
```json
{ "email": "professor@ua.pt", "password": "..." }
```

**POST /auth/refresh** — Request body:
```json
{ "refresh_token": "..." }
```

---

### Users

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/users` | No | Register a new user. Triggers a welcome email. |
| `GET` | `/users/me` | Yes | Return the authenticated user's profile. |

**POST /users** — Request body:
```json
{
  "email": "professor@ua.pt",
  "password": "...",
  "name": "Professor Silva",
  "role": "professor",
  "institution": "universidade-aveiro",
  "course": "MIECT"
}
```

Responses: `201 Created` `{ "user_id": "..." }` · `400 Bad Request` · `409 Conflict`

**GET /users/me** — Response `200 OK`:
```json
{
  "user_id": "...",
  "email": "professor@ua.pt",
  "name": "Professor Silva",
  "role": "professor",
  "institution": "universidade-aveiro",
  "course": "MIECT"
}
```

---

### Videos

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/videos` | Yes (professor) | Upload a video without processing. |
| `POST` | `/videos/process` | Yes (professor) | Upload a video with Video Editor processing. Returns a `job_id` and opens an SSE stream for progress. |
| `GET` | `/videos` | Yes | List and search videos within the user's institution. |
| `GET` | `/videos/{video_id}` | Yes | Retrieve video metadata and a temporary streaming URL. |
| `DELETE` | `/videos/{video_id}` | Yes (uploader only) | Delete a video and its stored object. |

**POST /videos** — `Content-Type: multipart/form-data`:

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | Yes | Video title |
| `description` | string | No | Video description |
| `tags` | string[] | No | Searchable tags |
| `course` | string | No | Associated course |
| `subject` | string | No | Associated subject |
| `file` | binary | Yes | Raw video bytes |

Responses: `201 Created` `{ "video_id": "..." }` · `400 Bad Request` · `403 Forbidden`

**POST /videos/process** — Same fields as above, plus:

| Field | Type | Required | Description |
|---|---|---|---|
| `operations` | string[] | Yes | Processing operations to apply (e.g. `["watermark"]`) |

Responses: `202 Accepted` `{ "job_id": "..." }` · `400 Bad Request` · `403 Forbidden`

SSE stream emitted during processing:
```
data: {"job_id": "...", "percent": 0, "status": "started"}
data: {"job_id": "...", "percent": 50, "status": "processing"}
data: {"job_id": "...", "percent": 100, "status": "done", "video_id": "..."}
```

**GET /videos** — Query parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | string | — | Search across title, description, and tags |
| `course` | string | — | Filter by course |
| `subject` | string | — | Filter by subject |
| `limit` | integer | 25 | Results per page |
| `offset` | integer | 0 | Number of results to skip |

Response `200 OK`:
```json
{
  "total": 42,
  "limit": 25,
  "offset": 0,
  "results": [
    {
      "video_id": "...",
      "title": "Aula 1 - VHDL",
      "description": "Introdução ao VHDL",
      "tags": ["VHDL", "LSD"],
      "course": "MIECT",
      "subject": "LSD",
      "uploader_id": "...",
      "created_at": "2024-03-01T10:00:00Z"
    }
  ]
}
```

**GET /videos/{video_id}** — Response `200 OK`:
```json
{
  "video_id": "...",
  "title": "Aula 1 - VHDL",
  "stream_url": "<presigned URL>",
  "tags": ["VHDL", "LSD"],
  "course": "MIECT",
  "subject": "LSD",
  "uploader_id": "...",
  "created_at": "2024-03-01T10:00:00Z"
}
```

Responses: `200 OK` · `401 Unauthorized` · `403 Forbidden` (different institution) · `404 Not Found`

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
| `KEYCLOAK_URL` | Keycloak base URL (default: `http://keycloak:8080`) |
| `KEYCLOAK_REALM` | Realm name (default: `egs`) |
| `KEYCLOAK_CLIENT_ID` | Client ID (default: `egs-platform`) |
| `KEYCLOAK_CLIENT_SECRET` | Client secret for service authentication |
| `OBJECT_STORAGE_URL` | Object Storage base URL (default: `http://object-storage:8080`) |
| `OBJECT_STORAGE_API_KEY` | API key for Object Storage |
| `VIDEO_EDITOR_URL` | Video Editor base URL (default: `http://video-editor:8080`) |
| `VIDEO_EDITOR_API_KEY` | API key for Video Editor |
| `NOTIFICATIONS_URL` | Notifications base URL (default: `http://notifications:8080`) |
| `NOTIFICATIONS_API_KEY` | API key for Notifications |
| `DATABASE_URL` | PostgreSQL connection string |

### Docker

> To be completed.
