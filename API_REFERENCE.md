# UAStream Service API Reference

This document is the consolidated API reference for the service branches under `egs/branches/`.

Repository model:
- Each folder inside `egs/branches/` is a git branch checkout and also a service boundary.
- The branch name is the service name in practice: `composer`, `iam`, `notifications`, `object-storage`, `video-editor`, and `main`.
- The `main` folder is the orchestration and deployment layer, not a standalone business service.

Scope:
- Documents the endpoints that are actually implemented in the branch code.
- Calls out documentation drift where a branch README does not match the code.
- Includes internal endpoints because they are part of the orchestration contract used by `main`.

Source of truth:
- Route handlers in each service `app.py`.
- Service READMEs where they match the code.
- Main README and deployment files for orchestration-level behavior.

## Service Summary

| Branch | Implementation | Notes |
|---|---|---|
| `composer` | Full orchestrator and public app/API | Main platform entrypoint. Handles auth, metadata, orchestration, and the SSE upload flow. |
| `iam` | Keycloak-based identity layer | Realm definition and login theme files only. No custom application code in this branch. |
| `notifications` | Transactional email service with OpenAPI | API-key protected. PostgreSQL-backed. Tracking pixel exposed publicly. |
| `object-storage` | Bucket/key binary storage service | Filesystem backend with RWO PVC. Supports Range requests for streaming. |
| `video-editor` | Async FFmpeg job service | In-memory job state. Pull model — Composer polls for progress and result. |
| `main` | Orchestration, deployment, and system docs | Canonical deployment and documentation layer. |

## Composer API

Composer is the main public entrypoint for UAStream. It serves the UI, handles auth, manages platform metadata, coordinates processing, and proxies internal storage calls.

### Frontend Pages

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/` | No | Home feed page. |
| `GET` | `/library` | No | Video library page. |
| `GET` | `/watch/<video_id>` | No | Watch page for a selected video. |
| `GET` | `/upload` | No | Professor upload page. |
| `GET` | `/studio` | No | Professor studio / management page. |
| `GET` | `/auth` | No | Authentication page. |

### Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/auth/login` | No | Redirects browser to Keycloak login using the authorization code flow. |
| `GET` | `/auth/callback` | No | OAuth callback handler; exchanges the code for tokens and renders the browser session bootstrap page. |
| `GET` | `/auth/logout` | No | Ends the Keycloak SSO session and redirects back to the app. |
| `POST` | `/auth/login` | No | Password-grant proxy to Keycloak; expects `email` and `password`. |
| `POST` | `/auth/refresh` | No | Refresh-token proxy to Keycloak; expects `refresh_token`. |

### Users

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/users` | No | Registers a new user in Keycloak and the local DB; sends a welcome email. |
| `GET` | `/users/me` | Bearer JWT | Returns the authenticated user profile, with a DB fallback if the account is not yet synced locally. |

### Channels

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/channels` | Bearer JWT, professor | Creates a channel. |
| `PUT` | `/channels/<channel_id>` | Bearer JWT, professor/owner | Updates channel metadata. |
| `PATCH` | `/channels/<channel_id>` | Bearer JWT, professor/owner | Same update surface as `PUT`. |
| `DELETE` | `/channels/<channel_id>` | Bearer JWT, professor/owner | Deletes a channel. |
| `GET` | `/channels` | Bearer JWT | Lists channels visible to the current user. |
| `GET` | `/channels/<channel_id>` | Bearer JWT | Returns channel details and videos if visible to the caller. |
| `GET` | `/channels/<channel_id>/subscribers` | Bearer JWT, owner | Lists channel subscribers. |
| `POST` | `/channels/<channel_id>/add-member` | Bearer JWT, professor/owner | Adds a user to a channel by email. |
| `POST` | `/channels/<channel_id>/subscribe` | Bearer JWT | Subscribes or unsubscribes the caller from the channel. |
| `GET` | `/channel/<channel_id>` | Bearer JWT | Singular alias that returns the same channel view surface. |
| `GET` | `/users/me/subscriptions` | Bearer JWT | Lists the current user's channel subscriptions. |
| `GET` | `/videos/subscribed` | Bearer JWT | Returns recent videos from subscribed channels. |

### Videos

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/videos` | Bearer JWT, professor | Uploads a video without Video Editor processing. Expects multipart form fields such as `title`, `file`, `description`, `tags`, `course`, `subject`, and `channel_id`. |
| `POST` | `/videos/process` | Bearer JWT, professor | Uploads a video with processing. Expects multipart form fields including `title`, `file`, and `operations` as JSON. Returns an SSE stream while Composer polls the Video Editor. |
| `GET` | `/videos/me` | Bearer JWT, professor | Lists videos uploaded by the authenticated professor. |
| `PUT` | `/videos/<video_id>` | Bearer JWT, professor/uploader | Updates video metadata. |
| `PATCH` | `/videos/<video_id>` | Bearer JWT, professor/uploader | Same update surface as `PUT`. |
| `GET` | `/videos` | Bearer JWT | Searches videos within the caller's institution. Supports `q`, `course`, `subject`, `limit`, and `offset`. |
| `GET` | `/videos/<video_id>` | Bearer JWT | Returns metadata and a presigned streaming URL. |
| `DELETE` | `/videos/<video_id>` | Bearer JWT, uploader | Soft-deletes the video and removes stored objects. |

### Internal

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/internal/storage/<bucket>/<path:key>` | Internal JWT / trusted service path | Proxies read access to Object Storage. |
| `PUT` | `/internal/storage/<bucket>/<path:key>` | Internal JWT / trusted service path | Proxies write access to Object Storage. |
| `POST` | `/internal/jobs/progress` | Internal service callback | Receives Video Editor progress updates. |
| `GET` | `/metrics` | No | Prometheus metrics endpoint. |


## IAM Branch

The `iam` branch is documented as Keycloak-based IAM, but the observed `app.py` currently mirrors the Composer Flask application instead of exposing Keycloak endpoints.

### Observed State

- The code imports Composer-style modules such as `auth`, `db`, and `services`.
- The route table is effectively the same as the Composer API surface.
- No Keycloak-standard endpoints are implemented in this branch's `app.py`.

### Documentation Impact

- The IAM README and the implementation are not aligned.
- If the branch is meant to be the real IAM service, the code is stale or in the wrong branch.
- If the branch is intentionally a copy, that needs to be stated clearly in the README.

### Practical Reference

Because the current code surface mirrors Composer, the implemented endpoints are the same as the Composer section above.

## Notifications API

Notifications sends templated emails and tracks opens with a pixel endpoint. It is protected by `X-API-Key` except for the tracking pixel and the OpenAPI routes.

### Email and Records

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/notifications/email` | `X-API-Key` | Sends an email using a named template. Expects `to`, `subject`, `template`, and `data`. Returns `202 Accepted` with a `notification_id`. |
| `GET` | `/notifications` | `X-API-Key` | Lists notification records. Supports `status` and `to` filters. |
| `GET` | `/notifications/<notification_id>` | `X-API-Key` | Returns one notification record. |
| `GET` | `/notifications/track/<notification_id>.gif` | No | Tracking pixel; marks the notification as opened on first fetch. |
| `GET` | `/metrics` | No | Prometheus metrics endpoint. |

### Template Introspection

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/notifications/templates` | `X-API-Key` | Lists available template names. |
| `GET` | `/notifications/templates/<template>` | `X-API-Key` | Returns the required fields for a template. |

### Template Contracts

| Template | Required fields |
|---|---|
| `welcome` | `name` |
| `upload_complete` | `name`, `title` |
| `new_video` | `name`, `course`, `professor_name`, `title` |

### Notifications Documentation Notes

- The service already has OpenAPI support, which is better than the other branches.
- The README should explicitly list the template names, required fields, and the exact `202` response behavior.
- The docs should also mention that delivery is attempted, not guaranteed, and that the service can return `202` with a warning if SMTP fails after the record is created.

## Object Storage API

Object Storage stores arbitrary binary objects on disk by bucket and key. It accepts either an API key or a presigned stub token for downloads.

### Buckets

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/buckets` | `X-API-Key` | Lists buckets with `limit`, `offset`, and `query`. |
| `PUT` | `/buckets/<bucket>` | `X-API-Key` | Creates a bucket. |
| `DELETE` | `/buckets/<bucket>` | `X-API-Key` | Deletes a bucket and its contents. |

### Objects

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/objects/<bucket>` | `X-API-Key` | Lists object keys in a bucket. Supports `limit`, `offset`, and `query`. |
| `PUT` | `/objects/<bucket>` | `X-API-Key` | Uploads an object when the key is passed as `?key=` or `X-Object-Key`. |
| `PUT` | `/objects/<bucket>/<path:key>` | `X-API-Key` | Uploads an object using the path key form. |
| `GET` | `/objects/<bucket>/<path:key>` | `X-API-Key` or presigned token | Downloads an object. Supports `Range` for partial content. |
| `DELETE` | `/objects/<bucket>` | `X-API-Key` | Deletes an object when the key is passed as `?key=`. |
| `DELETE` | `/objects/<bucket>/<path:key>` | `X-API-Key` | Deletes an object using the path key form. |
| `POST` | `/objects/<bucket>/<path:key>/presign` | `X-API-Key` | Generates a stub presigned URL with `token=stub-presign` and an expiry timestamp. |
| `GET` | `/metrics` | No | Prometheus metrics endpoint. |

### Object Storage Documentation Notes

- The README documents the query-string form of object upload and delete, but the code also exposes path-key routes.
- Presigned URLs are currently a stub implementation, so the security model should be documented as temporary rather than production-grade.
- The `GET` download route supports `Range` requests and should document the `206 Partial Content` response explicitly.

## Video Editor API

Video Editor accepts jobs, runs FFmpeg work in the background, and exposes progress and result endpoints. The implemented code is more limited than the README claims.

### Implemented Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/jobs` | `X-API-Key` | Creates a processing job from multipart form data. Expects `file` and `operations` JSON. |
| `GET` | `/jobs/operations` | `X-API-Key` | Lists supported operations. |
| `GET` | `/jobs/<job_id>` | `X-API-Key` | Returns job state and progress. |
| `GET` | `/jobs/<job_id>/progress` | `X-API-Key` | Streams progress as SSE. |
| `GET` | `/jobs/<job_id>/result` | `X-API-Key` | Downloads the processed video. |
| `GET` | `/jobs/<job_id>/thumbnail` | `X-API-Key` | Downloads the thumbnail. |
| `GET` | `/metrics` | No | Prometheus metrics endpoint. |

### What the Code Actually Supports

- Multipart job creation with `file` and `operations`.
- Supported operations: `watermark`, `rotate`, `trim`, and `resize`.
- In-memory job state plus on-disk job artifacts under `/tmp/video_editor_jobs`.
- SSE progress updates with `status`, `percent`, `message`, and optional `error`.

### Video Editor Documentation Notes

- The README and OpenAPI spec (`video-editor.yaml`) have been reconciled with the actual `app.py` implementation (Option B: pull model with in-memory state, removing SQLite/cancellation/upsert endpoints).
- The test suite (`test.sh`) has been successfully aligned and verified against the running codebase.

## Cross-Service Documentation Status

All main documentation gaps identified in the service branch files have been resolved:

1. **Composer**: The README now documents the full route surface (including OIDC authentication callback, studio views, subscriptions, and channels APIs).
2. **IAM**: Unused Flask application replica files inside the `iam` folder have been deleted, leaving only the Keycloak realm and theme configuration files which are mounted into Keycloak. The README has been corrected.
3. **Video Editor**: The documentation, OpenAPI spec, and test suite have been aligned to reflect the database-less, cancel-less in-memory logic.
4. **Object Storage**: The README now correctly details path-based object routes (`/objects/{bucket}/{key}`) used by the Composer orchestrator and notes the local vs. container port details.
5. **Consolidated Reference**: This document serves as the canonical endpoint inventory and documentation audit log.
