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
| **[Composer](../composer)** | Stateful (DB) | The sole orchestrator. Manages API traffic, verifies JWT boundaries, coordinates file transfers across containers, and handles all business logic. |
| **[Video Editor](../video-editor)** | Ephemeral / Sandbox | An agnostic worker. Exposes endpoints to ingest file bytes, runs heavy `ffmpeg` tasks, and passively serves finished files. Zero knowledge of the parent platform. |
| **[Object Storage](../object-storage)** | Persistent (Disk) | Dumb blob storage. Safely stores binary files and generates presigned URLs for client video playback. |
| **[IAM / Keycloak](../iam)** | Persistent (DB) | Identity Provider. Issues JWTs and enforces user roles. |
| **[Notifications](../notifications)** | Stateless | Provides an endpoint to shoot out standardized emails and events on command. |

*(Note: Public traffic goes through Traefik on `http://uastream.com`. Internal services talk over Docker networks.)*

---

## Team

| Name | NMEC |
|---|---|
| André Marques | 87818 |
| | |
| | |
| | |

---

## Secrets Management

### Vault Architecture

This platform uses **HashiCorp Vault** for centralized secrets management. Each service holds configuration (database URLs, API keys, credentials) in Vault, rather than hardcoding them or managing them via environment variables.

#### How Secrets Flow to Services

1. **Vault Server** (`http://vault:8200`) — Stores and serves all secrets to authorized services via HTTP API
2. **Vault Tokens** — Each service holds a token with restricted permissions; tokens never expire in this demo
3. **Secrets Retrieval** — Services read secrets from Vault on startup or poll the API as needed

#### Secret Delivery Patterns (Demo & Production)

This project demonstrates **two patterns** for getting secrets into services:

| Pattern | File | Use Case | Status |
|---|---|---|---|
| **Static Token (Dev Mode)** | `docker-compose.dev.yml` | Local development with quick iteration; Vault in dev mode (no persistence, all secrets lost on restart) | **Demo** ✅ |
| **Vault Agent Sidecars (POC)** | `docker-compose.agent.yml` | Demonstration of how professional secret delivery works; Agent containers render secrets to shared volumes | **POC/Educational** ✅ |
| **Production (External Vault)** | `docker-compose.yml` (standalone) | Real deployments use external Vault cluster with proper auth (AppRole, JWT, etc.); services use client libraries to fetch secrets | **Production Template** 🔒 |

### Development Deployment (Quick Start)

To run locally with **Vault dev mode + static tokens** (all data resets on restart):

```bash
cd main
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

This combines:
- **`docker-compose.yml`** — Main orchestration (services, databases, Traefik, Vault server)
- **`docker-compose.dev.yml`** — Dev-only overrides:
  - `VAULT_SKIP_MLOCK=true` — Disables memory locking (not available in Docker)
  - `SKIP_SETCAP=true` — Disables Linux capabilities (not available in Docker)
  - Static hardcoded tokens for each service (e.g., `token-composer`, `token-object-storage`)

⚠️ **This setup is ephemeral** — restarting Vault wipes all secrets. Suitable for development only.

### Vault Agent Sidecar Demo (Educational POC)

To see how production systems deliver secrets securely without hardcoding tokens:

```bash
cd main
docker-compose -f docker-compose.yml -f docker-compose.agent.yml up --build -d
```

**What happens:**

1. Vault runs in dev mode (same as above)
2. **Agent sidecars** spawn for each service (e.g., `composer-agent`, `video-editor-agent`, `notifications-agent`)
3. Each Agent:
   - Authenticates to Vault using a shared token from `vault_init.sh`
   - Reads secret templates from `vault-agent/templates/` (e.g., `.env` format)
   - **Renders secrets into shared volumes** (e.g., `composer-secrets:/vault/secrets`)
4. Services read the rendered secrets from the shared volume instead of fetching them directly from Vault

This pattern demonstrates professional secret management in containerized environments — services never see raw tokens or have direct Vault access.

### Production Deployment (Recommended)

For real deployments, **do not use `.dev` or `.agent`** overrides. Instead:

1. **Run Vault externally** (managed service or HA cluster) — NOT in a container
2. **Use proper auth methods** — AppRole, Kubernetes auth, JWT, etc. (not static tokens)
3. **Let services fetch secrets** — Use Vault client libraries (Python `hvac`, Go, etc.) to fetch secrets on-demand
4. **Remove `VAULT_SKIP_MLOCK`** and `SKIP_SETCAP` — These are dev-only hacks

Example production command:
```bash
cd main
export VAULT_ADDR=https://vault.prod.example.com:8200
export VAULT_NAMESPACE=uastream
docker-compose up --build -d
```

Each service would use its configured auth method to obtain a temporary token and fetch secrets dynamically.

---

## Deployment

To deploy locally, use `run.sh`. It creates or updates git worktrees for each service branch (side-by-side) and then starts the stack with Docker Compose.

### 1. Clone the main branch
```bash
mkdir uastream-platform && cd uastream-platform
git clone -b main https://github.com/ayxor/egs.git main
```

<<<<<<< HEAD
### 2. Run the orchestrator bootstrap
```bash
cd main
./run.sh
```

`run.sh` ensures the service branches (`composer`, `iam`, `object-storage`, `video-editor`, `notifications`) are checked out as sibling directories via git worktrees, keeps them up to date, and then runs Docker Compose. All services are mapped inside [docker-compose.yml](docker-compose.yml) to build directly from those sibling directories.

### 3. Start the Orchestration (Development)
Once the structure matches, enter the `main` directory and run the development composition:
```bash
cd main
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build -d
```

For the Vault Agent demo:
```bash
docker-compose -f docker-compose.yml -f docker-compose.agent.yml up --build -d
```

All services are mapped inside `docker-compose.yml` to build directly from their sibling local directories.

## Kubernetes Handoff (For Deployers)

This repository currently contains a development-focused Vault POC. The following notes are a concise handoff for the teammate who will deploy this to Kubernetes.

- Purpose: Provide a minimal, actionable checklist so the deployer can move from the dev/demo compose setup to a K8s-ready Vault + app deployment.
- Scope: This is a handoff for Path B (minimal, ops-handled production work). It does not perform the full hardening here.

### Quick deployer checklist

- Run a production Vault (Helm/managed) instead of the `vault` container in this repo.
  - Recommended: `hashicorp/vault` Helm chart (enable HA and Raft storage).
  - Example Helm bits (reference only):
    ```bash
    helm repo add hashicorp https://helm.releases.hashicorp.com
    helm install vault hashicorp/vault --set "server.ha.enabled=true" --set "server.ha.raft.enabled=true" --set "server.dataStorage.enabled=true"
    ```
- Use Kubernetes auth for service authentication (enable `auth/kubernetes` in Vault) rather than static tokens or container-mounted secret files.
- Use the Vault Agent Injector (or Vault CSI) to inject secrets into pods rather than running sidecar agents as root in app containers.
- Persist Vault storage with PVs or external storage (do not run Vault in dev mode). Ensure backups and snapshot strategy.
- Remove dev-only flags from any K8s manifests (`VAULT_SKIP_MLOCK`, `SKIP_SETCAP`) and ensure appropriate PodSecurityPolicy / SecurityContext settings.
- Ensure services run with non-root users and minimal privileges (university security scanners will flag root agents).

### Files of interest for context

- `docker-compose.agent.yml` — demonstrates the sidecar/Agent pattern used in the POC
- `vault-agent/` — example `agent.hcl` configs and templates used to render secrets
- `vault_init.sh` — script that seeds Vault and creates AppRole roles (useful for reference; in K8s you will create roles/policies via CI or operator)

### Handoff notes (minimal guidance for the deployer)

- This repo's Vault is intentionally dev-mode for reproducibility. Replace it with a Helm/managed Vault before production use.
- The deployer should: (1) provision Vault HA+Raft, (2) enable `auth/kubernetes`, (3) create roles/policies for each service, and (4) configure the Vault Injector or CSI driver to populate secrets into pods.
- If you want, I can later prepare Helm manifests and a minimal K8s example (namespace, ServiceAccount, Role, RoleBinding, and Injector annotation examples) to make the handoff turnkey.

---

*Status: minimal handoff added; full K8s migration documented as a future task.*
>>>>>>> db9bc77 (chore(docs+vault): add Kubernetes handoff; include Vault POC files)
