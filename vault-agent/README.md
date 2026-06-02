# Vault Agent Sidecars

This folder contains the Vault Agent configurations used by the UAStream services.
Each file describes one sidecar-style agent that authenticates to Vault with AppRole and renders a service-specific JSON secret file.

## Purpose

The Vault Agent is the secret delivery layer for the demo stack.
It reads an AppRole role ID and secret ID, authenticates against Vault, renders a template, and writes the result into a shared secret volume for the application container.

This keeps API keys out of the service images and out of the compose files.

## How It Works

1. Vault is started in dev mode by the platform stack.
2. The `vault-init` job seeds KV secrets and creates policies plus static tokens.
3. Each service pod or container gets an AppRole role ID and secret ID.
4. Vault Agent authenticates with AppRole.
5. Vault Agent renders the matching template into `/vault/secrets/*.json`.
6. The service reads that file instead of hardcoding credentials.

## Files

### Agent configurations

| File | Service | Output |
|---|---|---|
| `composer-agent.hcl` | Composer | `/vault/secrets/composer.json` |
| `video-editor-agent.hcl` | Video Editor | `/vault/secrets/video-editor.json` |
| `object-storage-agent.hcl` | Object Storage | `/vault/secrets/object-storage.json` |
| `notifications-agent.hcl` | Notifications | `/vault/secrets/notifications.json` |

### Template files

| File | Renders from Vault path | Purpose |
|---|---|---|
| `templates/composer.tpl` | `secret/data/object-storage`, `secret/data/video-editor`, `secret/data/notifications` | Composer API keys for downstream services |
| `templates/video-editor.tpl` | `secret/data/video-editor`, `secret/data/object-storage` | Worker keys for processing and storage callbacks |
| `templates/object-storage.tpl` | `secret/data/object-storage` | Storage service API key |
| `templates/notifications.tpl` | `secret/data/notifications` | Notifications service API key |

## Agent Behavior

All four agents share the same basic shape:

- `auto_auth` uses the `approle` method
- `role_id_file_path` points to a file under `/vault/auth/`
- `secret_id_file_path` points to a matching `/vault/auth/` file
- `template` reads from `/etc/vault/templates/*.tpl`
- `destination` writes a JSON secret into `/vault/secrets/`
- `listener` binds to `127.0.0.1:8100`
- `vault.address` points to `http://vault:8200`

The local listener is there for agent control and health behavior; the app itself reads the rendered file from disk.

## Rendered Secret Shape

The rendered files are simple JSON payloads.
Examples:

- `composer.json` contains `object_storage_api_key`, `video_editor_api_key`, and `notifications_api_key`
- `video-editor.json` contains `video_editor_api_key` and `object_storage_api_key`
- `object-storage.json` contains `api_key`
- `notifications.json` contains `notifications_api_key`

## Security Model

This is a demo-grade secret flow, not a full production hardening story.

- Vault runs in dev mode in the stack
- Tokens are seeded by the `vault-init` job
- AppRole files are mounted into the agent environment
- Policies are scoped per service so each agent only reads the secrets it needs

## Relationship To The Main Stack

The Vault Agent configs are used alongside the main stack files under [k8s/manifests](../k8s/manifests/) and the compose-based demo stack in [docker-compose.yml](../docker-compose.yml).

The matching bootstrap job is documented in [k8s/deployment_architecture.md](../k8s/deployment_architecture.md).

## Notes

- These files are configuration only; they are not standalone services.
- The agent templates should stay aligned with the keys created by `vault-init`.
- If you add a new service secret, update both the Vault policy and the matching template.