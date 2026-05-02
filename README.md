# IAM Service

The IAM branch is a Keycloak-based identity service. It is the single source of truth for authentication, token issuance, user accounts, and the UAStream login theme.

Composer is the only application service that talks to IAM directly.

## Responsibilities

- Authenticate users through Keycloak login flows
- Issue OAuth 2.0 / OpenID Connect tokens
- Expose JWKS keys for JWT validation
- Manage users, credentials, and required actions
- Store user attributes such as `role` and `institution`
- Provide a service-account path for Composer user creation
- Serve the custom UAStream login theme

IAM does not store platform metadata such as videos, jobs, or notifications.

## Public URLs

- Public host: `http://uastream.com`
- Internal service URL: `http://keycloak:8080`

## API Reference

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

## Deployment

The realm is imported from `keycloak/realm-egs.json` on fresh startup. It configures the `egs-platform` client, redirect URIs, protocol mappers, and the `uastream` theme.

Theme assets live under `keycloak/themes/uastream/login/`.

Local Keycloak runs in Docker and is reached through the stack managed by the `main` branch.

## Environment Variables

- `KEYCLOAK_ADMIN`
- `KEYCLOAK_ADMIN_PASSWORD`
- `KC_DB_URL`
- `KC_DB_USERNAME`
- `KC_DB_PASSWORD`

## Notes

- Redirect URIs must match the public hostname when the stack is behind Traefik.
- `uastream.com` is the canonical public host for browser flows.
- A realm import happens only when Keycloak starts with a fresh database volume.
