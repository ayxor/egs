# Composer Service

The Composer is the core application service of UAStream.

It is not a stub and not a passive gateway. It is the runtime entity that orchestrates IAM, video processing, storage, and notifications so the platform works end-to-end for professors and students.

The same Composer service also serves the web application pages (frontend).

## What The Composer Does

- Serves the UAStream web app pages (`/`, `/library`, `/watch/<video_id>`, `/upload`, `/auth`)
- Authenticates users through Keycloak token flows
- Validates JWTs for protected API operations
- Registers users (including role and institution metadata)
- Enforces role and ownership rules (for example, only professors can upload)
- Uploads raw videos to Object Storage
- Triggers processing jobs in Video Editor (including watermark workflows)
- Tracks processing progress and relays updates
- Persists user/video/job metadata in PostgreSQL
- Sends publication and lifecycle notifications through Notifications service
- Issues presigned stream URLs so clients can watch directly from storage

## Core Architecture Role

The Composer is the single orchestrator in this project.

- Frontend requests arrive at Composer
- Composer coordinates service calls in the correct order
- Internal services do not need to call each other directly for platform business logic

## Frontend Pages

- `GET /` - Home feed
- `GET /library` - Video library and search
- `GET /watch/<video_id>` - Watch page
- `GET /upload` - Upload studio (professor flow)
- `GET /auth` - Login / registration page

## API Endpoints

### Authentication

- `POST /auth/login`
- `POST /auth/refresh`

### Users

- `POST /users`
- `GET /users/me`

### Videos

- `POST /videos` (professor)
- `POST /videos/process` (professor, watermark/processing flow)
- `GET /videos`
- `GET /videos/{video_id}`
- `DELETE /videos/{video_id}` (uploader)

### Internal Callback

- `POST /internal/jobs/progress`

## Data Owned By Composer

Composer owns and manages PostgreSQL metadata tables for:

- user profiles
- videos
- processing jobs

Passwords and credential verification are delegated to Keycloak.

## Dependencies

- IAM / Keycloak
- Object Storage
- Video Editor
- Notifications
- PostgreSQL

All dependency endpoints and credentials are configured through environment variables in `config.py`.

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PORT=8090 python app.py
```

Then open:

- `http://127.0.0.1:8090/`

## Required Environment Variables

- `KEYCLOAK_URL`
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
