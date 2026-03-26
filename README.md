# UAStream

A teaching-focused video streaming platform designed to centralise and enhance access to academic lecture content within higher education institutions.

---

## Overview

### Problem

Lecture recordings are scattered across disconnected platforms, lack structured metadata, and offer no meaningful search capabilities. Students struggle to locate topic-specific content, and institutions have no unified, permission-controlled environment for managing academic video.

### Solution

The UAStream Video Platform addresses these gaps through a modular, service-oriented architecture that integrates identity management, video processing, object storage, and notification delivery into a single cohesive system. The platform is built around loose coupling and clear service boundaries, making it straightforward to operate, extend, and onboard new institutions.

### Key Advantages

| Advantage | Description |
|---|---|
| Service-Based Architecture | Each concern is isolated in an independent, replaceable service |
| Inter-Institution Interoperability | Middleware-driven design supports multiple institutions without coupling |
| Technology-Agnostic Integration | Services communicate over standard HTTP; no vendor lock-in |
| Horizontal Scalability | Each service scales independently to meet demand |
| Reusable Infrastructure | Storage, notifications, and video processing are generic and reusable across projects |
| Easy Institutional Onboarding | New institutions are provisioned through a single bucket and user registration flow |

---

## Architecture

The platform is built on a strict **Orchestration Pattern** utilizing highly decoupled, agnostic microservices. The **Composer** acts as the central brain, API gateway, and sole orchestrator. 

A core principle of this architecture is **Strict Service Isolation** (the "Pull/Polling Model"). Worker services like the **Video Editor** and **Object Storage** are entirely stateless, sandboxed, and agnostic. They *never* initiate outbound network requests to other internal services (no webhooks, no callbacks, no shared volumes). They simply expose HTTP endpoints, receive payloads, execute their isolated tasks, and wait for the orchestrator to pull the results.

```text
       ┌──────────────┐
       │  Web Client  │
       └──────┬───────┘
              │ (HTTP/REST & SSE)
              ▼
       ┌──────────────┐
       │   Composer   │ (API Gateway & Orchestrator)
       └──────┬───────┘
              │
    ┌─────────┼─────────┬─────────┐
    ▼         ▼         ▼         ▼
  IAM       Editor   Storage    Notify
(Keycloak) (No call) (No call) (No call)
           (out)     (out)     (out)
```

### The "Pull" Data Flow (Video Processing Example)
To guarantee isolation, worker services completely lack awareness of the ecosystem. The flow is strictly top-down:
1. **Ingest & Dispatch:** The Composer receives a raw video from the user and HTTP `POST`s the binary payload directly to the Video Editor along with the requested edit operations (e.g., watermark, trim).
2. **Isolated Processing:** The Editor saves the file to its own ephemeral storage (`/tmp/video_editor_jobs`) and begins asynchronous processing via FFmpeg. It synchronously returns a generic `job_id`.
3. **Progress Polling (SSE):** The Composer connects to the Editor's Server-Sent Events (SSE) endpoint (`GET /jobs/<job_id>/progress`) to read real-time encoding progress and seamlessly pipes this stream back to the client browser.
4. **Result Extraction:** Once the Editor's SSE stream reports `status: "done"`, the Composer makes explicit HTTP `GET` requests to download the generated `dst.mp4` and `thumb.jpg` bytes from the Editor.
5. **Final Storage:** The Composer then uploads these artifacts to the Object Storage service, updates its local metadata database, and signals completion.

### Service Roles
| Service | State Level | Responsibility |
|---|---|---|
| **[Composer](../../tree/composer)** | Stateful (DB) | The sole orchestrator. Manages API traffic, verifies JWT boundaries, coordinates file transfers across containers, and handles all business logic. |
| **[Video Editor](../../tree/video-editor)** | Ephemeral / Sandbox | An agnostic worker. Exposes endpoints to ingest file bytes, runs heavy `ffmpeg` tasks, and passively serves finished files. Zero knowledge of the parent platform. |
| **[Object Storage](../../tree/object-storage)** | Persistent (Disk) | Dumb blob storage. Safely stores binary files and generates presigned URLs for client video playback. |
| **[IAM / Keycloak](../../tree/iam-keycloak)** | Persistent (DB) | Identity Provider. Issues JWTs and enforces user roles. |
| **[Notifications](../../tree/notifications)** | Stateless | Provides an endpoint to shoot out standardized emails and events on command. |

---

## Team

| Name | NMEC |
|---|---|
|André Marques  |87818  |
|  |  |
|  |  |
|  |  |

---

## Deployment

To deploy the platform locally, you will need to clone all the service branches side-by-side. Our architecture relies on a mono-repo where each microservice lives in its own branch. 

### 1. Setup the workspace directory structure
Create a parent directory to hold all the services together:
```bash
mkdir uastream-platform && cd uastream-platform

git clone -b main https://github.com/ayxor/egs.git main
git clone -b composer https://github.com/ayxor/egs.git composer
git clone -b iam https://github.com/ayxor/egs.git iam
git clone -b object-storage https://github.com/ayxor/egs.git object-storage
git clone -b video-editor https://github.com/ayxor/egs.git video-editor
git clone -b notifications https://github.com/ayxor/egs.git notifications
```

### 2. Start the Orchestration
Once the structure matches, enter the `main` directory and run the global composition:
```bash
cd main
docker-compose up -build -d
```
All services are mapped inside the `docker-compose.yml` to build directly from their sibling local directories.