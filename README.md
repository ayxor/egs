# Composer Service

Composer is the application and orchestration service for UAStream. It serves the web UI, handles authentication, owns the main platform API, and coordinates IAM, storage, video processing, and notifications.

## Role In The Stack

Composer is the only service that should orchestrate cross-service business flows. It is responsible for turning user actions into the right sequence of calls to Keycloak, Object Storage, Video Editor, and Notifications.

Public access goes through Traefik on `http://uastream.com`. Composer is exposed there as the main application entrypoint.

## What It Does

- Serves the UAStream pages (`/`, `/library`, `/watch/<video_id>`, `/upload`, `/auth`)
- Handles login and registration flows with Keycloak
- Creates users through the Keycloak admin API
- Validates JWTs for protected API routes
- Enforces ownership and role checks
- Uploads raw media to Object Storage
- Creates and monitors Video Editor jobs
- Persists platform metadata in PostgreSQL
- Sends email notifications through the Notifications service
- Generates stream URLs for playback

## Main Endpoints

### Frontend

- `GET /`
- `GET /library`
- `GET /watch/<video_id>`
- `GET /upload`
- `GET /auth`

### Authentication

- `POST /auth/login`
- `POST /auth/refresh`

### Users

- `POST /users`
- `GET /users/me`

### Videos

- `POST /videos`
- `POST /videos/process`
- `GET /videos`
- `GET /videos/{video_id}`
- `DELETE /videos/{video_id}`

### Internal

- `POST /internal/jobs/progress`

## Dependencies

- IAM / Keycloak
- Object Storage
- Video Editor
- Notifications
- PostgreSQL

All URLs and secrets come from environment variables in `config.py`.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORT=8090 python app.py
```

Open the app at:

- `http://127.0.0.1:8090/`

## Environment Variables

- `KEYCLOAK_URL`
- `KEYCLOAK_PUBLIC_URL`
- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_CLIENT_SECRET`
- `OBJECT_STORAGE_URL`
- `OBJECT_STORAGE_API_KEY`
- `VIDEO_EDITOR_URL`
- `VIDEO_EDITOR_API_KEY`
- `NOTIFICATIONS_URL`
- `NOTIFICATIONS_API_KEY`
- `DATABASE_URL`
- `COMPOSER_BASE_URL`
- `PORT`
