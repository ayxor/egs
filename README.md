# UAStream Platform

UAStream is a teaching-focused video streaming platform for higher-education content. Each service lives in its own branch, and the local workspace is expected to mirror that structure.

## Branch Layout

Each branch is a service:

- `main` - stack composition and Traefik entrypoint
- `composer` - web app, orchestration, and platform API
- `iam` - Keycloak realm, theme, and identity configuration
- `object-storage` - binary object store
- `video-editor` - asynchronous media processing worker
- `notifications` - transactional email service

## Architecture

The platform uses a strict orchestrator model. Composer is the only application service that coordinates the others directly. IAM handles identity, Object Storage stores binary assets, Video Editor processes media jobs, and Notifications sends email when Composer requests it.

Public traffic goes through Traefik on `http://uastream.com`. Internal services talk over Docker networks (`services-net`); they are not meant to be exposed on localhost for normal use.

## Security & Secrets Management

API keys for internal communication are managed and securely injected by **HashiCorp Vault**. 
- Vault runs in complete isolation on the `vault-net` network. It is not exposed to the public internet.
- A `vault-init` script automatically provisions the KV secrets engine and sets up granular security policies (least-privilege).
- When Python services boot up, they use an injected `VAULT_TOKEN` to authenticate and fetch their `API_KEY` dynamically into memory using the `hvac` Python library. This ensures zero hardcoded passwords exist in the application code.

## Local Workspace

Clone the branches side-by-side so the compose files can resolve sibling paths:

```bash
mkdir uastream-platform && cd uastream-platform

git clone -b main https://github.com/ayxor/egs.git main
git clone -b composer https://github.com/ayxor/egs.git composer
git clone -b iam https://github.com/ayxor/egs.git iam
git clone -b object-storage https://github.com/ayxor/egs.git object-storage
git clone -b video-editor https://github.com/ayxor/egs.git video-editor
git clone -b notifications https://github.com/ayxor/egs.git notifications
```

## Run The Stack

Start the platform from the `main` branch:

```bash
cd main
docker-compose up -d --build
```

Traefik publishes the public application, Keycloak, notifications, and the storage routes from the compose file. The composer, IAM, storage, editor, and notifications containers are built from the sibling branch directories.

## Service Responsibilities

| Service | Responsibility |
|---|---|
| Traefik | Public entrypoint, reverse proxy, load balancing |
| Vault | Secrets management and dynamic API Key provisioning |
| Composer | Web UI, user registration, auth flow, metadata, orchestration |
| IAM | Login, token issuance, user administration, login theme |
| Object Storage | Bucket/object persistence for raw and processed assets |
| Video Editor | FFmpeg-based processing jobs and progress tracking |
| Notifications | Email delivery and email tracking pixel endpoint |

## Notes

- `uastream.com` is the canonical public hostname for the stack.
- Localhost references are only for internal developer workflows or legacy realm configuration.
- If you change service URLs, update the compose files and the service README files together.