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

The platform follows an orchestration pattern. The **Composer** is the single external entry point and the sole orchestrator of all other services. No service calls another service directly.

```
Client
  │
  ▼
Composer  ──►  IAM (Keycloak)
  │
  ├──►  Object Storage
  ├──►  Video Editor
  └──►  Notifications
```

| Service | Responsibility |
|---|---|
| [Composer](../../tree/composer) | API gateway, business logic, metadata database, orchestration |
| [IAM / Keycloak](../../tree/iam-keycloak) | Identity and access management, JWT issuance and signing |
| [Object Storage](../../tree/object-storage) | Binary file storage, presigned URL generation |
| [Video Editor](../../tree/video-editor) | Asynchronous video processing with real-time SSE progress |
| [Notifications](../../tree/notifications) | Transactional email delivery via templates |

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

> To be completed. Each service ships with a `Dockerfile` and the platform is orchestrated via `docker-compose`. Deployment instructions will be added here once the infrastructure configuration is finalised.
