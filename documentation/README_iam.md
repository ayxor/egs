# IAM Service

The IAM branch is a Keycloak-based identity service. It is the single source of truth for authentication, token issuance, user accounts, and the UAStream login theme.

Composer is the only application service that talks to IAM directly.

Note: The files in this folder contain the realm definition and user login theme configurations that are mounted directly into the official Keycloak Docker image used in the stack. Stale Python Flask replica files have been removed.

## Responsibilities

- Authenticate users through Keycloak login flows
- Issue OAuth 2.0 / OpenID Connect tokens
- Expose JWKS keys for JWT validation
- Manage users, credentials, and required actions
- Store user attributes such as `role` and `institution`
- Provide a service-account path for Composer user creation
- Serve the custom UAStream login theme

IAM does not store platform metadata such as videos, jobs, or notifications.

## API Reference

### Public URLs

- Public host: `http://uastream.com`
- Internal service URL: `http://keycloak:8080`

### Realm Metadata / JWKS

| Method | Path | Description |
|---|---|---|
| `GET` | `/realms/{realm}/.well-known/openid-configuration` | OpenID Connect metadata |
| `GET` | `/realms/{realm}/protocol/openid-connect/certs` | JWKS used by Composer |

### Token Endpoint

| Method | Path | Description |
|---|---|---|
| `POST` | `/realms/{realm}/protocol/openid-connect/token` | Password, refresh token, authorization code, and client credentials grants |

Composer uses the authorization code flow for browser sign-in and client credentials for user creation.

### Authorization Endpoint

| Method | Path | Description |
|---|---|---|
| `GET` | `/realms/{realm}/protocol/openid-connect/auth` | Starts the browser login flow |

### Logout Endpoint

| Method | Path | Description |
|---|---|---|
| `GET` | `/realms/{realm}/protocol/openid-connect/logout` | Ends the SSO session |

### User Management

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/realms/{realm}/users` | Create a user with service-account privileges |
| `GET` | `/admin/realms/{realm}/users` | Search or list users |
| `PUT` | `/admin/realms/{realm}/users/{id}` | Update a user |
| `PUT` | `/admin/realms/{realm}/users/{id}/reset-password` | Reset a user password |

The Composer service account must have `realm-management -> manage-users` for registration to work.

## Token Claims

Tokens carry the metadata Composer needs:

| Claim | Description |
|---|---|
| `sub` | Keycloak user id |
| `email` | User email |
| `preferred_username` | Login name |
| `name` | Display name |
| `role` | `student`, `professor`, etc. |
| `institution` | Institution namespace |

## Runtime

The realm is imported from `keycloak/realm-egs.json` on fresh startup. It configures the `egs-platform` client, redirect URIs, protocol mappers, and the `uastream` theme.

Theme assets live under `keycloak/themes/uastream/login/`.

Local Keycloak runs in Docker and is reached through the stack managed by the `main` branch.

## Deployment

### Environment Variables

- `KEYCLOAK_ADMIN`
- `KEYCLOAK_ADMIN_PASSWORD`
- `KC_DB_URL`
- `KC_DB_USERNAME`
- `KC_DB_PASSWORD`

### Dev Mode vs Production Mode (`start-dev` vs `start`)

Keycloak is currently configured to run with `/opt/keycloak/bin/kc.sh start` in production mode.

#### 1. Production Mode (`start`) — Current Configuration

The live deployment uses `start` mode with the following flags:

- `--http-enabled=true` — Allows plain HTTP behind the Traefik reverse proxy.
- `--hostname-strict=false` — Disables strict hostname validation so Keycloak accepts requests routed through Traefik.
- `--proxy-headers=xforwarded` — Tells Keycloak to trust `X-Forwarded-*` headers set by Traefik for correct redirect URI construction.

#### 2. Why Not `start-dev`?

`start-dev` uses in-memory-only session caches with no clustering. Running more than one replica in `start-dev` causes `Code not valid` / `expired_code` errors because each pod is an isolated island — an authorization code created on Pod A is invisible to Pod B. In production mode, Keycloak enables Infinispan distributed caches and the pods form a proper cluster.

#### 3. Clustering and Session Replication

In production mode, Keycloak uses Infinispan for distributed session caches (`authenticationSessions`, `sessions`, `clientSessions`, etc.). Pod discovery uses the default `JDBC_PING` protocol over the shared PostgreSQL database (`kc-db`). The `NetworkPolicy` must allow JGroups traffic between Keycloak pods on ports `7800` (JGroups) and `57800` (FD_SOCK).

#### 4. Sticky Sessions Requirement

Regardless of whether dev or production mode is used, **cookie-based sticky session affinity must be enabled at the Ingress level** (via Traefik Service annotations) when running `replicas > 1`. This ensures a user's browser remains sticky to the same Keycloak pod throughout the authentication flow, avoiding load-balancing session mismatches and `expired_code` errors.

## Notes

- Redirect URIs must match the public hostname when the stack is behind Traefik.
- `uastream.com` is the canonical public host for browser flows.
- Keycloak is running as the official docker image `quay.io/keycloak/keycloak:26.1`.
