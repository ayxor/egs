# IAM Service (Keycloak)

The IAM service is provided by [Keycloak](https://www.keycloak.org/) and is the sole source of truth for user identity within the EGS Video Platform. It is responsible for issuing and signing JWTs, managing user credentials, and exposing the public key used by the Composer to validate tokens locally.

Keycloak is entirely agnostic to platform business logic. It has no knowledge of videos, courses, subjects, institutions (beyond storing the attribute), or any other service in the system.

**The Composer is the only service that communicates with Keycloak.**

---

## JWT Contents

Every JWT issued by Keycloak contains at minimum:

| Claim | Description |
|---|---|
| `user_id` | Unique identifier of the user |
| `email` | User's email address |
| `role` | Either `professor` or `student` |
| `institution` | The institution the user belongs to (e.g. `universidade-aveiro`) |

---

## API Reference

This specification documents only the endpoints consumed by the Composer. The base URL is `http://keycloak:8080`.

### Public Key (JWKS)

| Method | Path | Auth required | Description |
|---|---|---|---|
| `GET` | `/realms/{realm}/protocol/openid-connect/certs` | No | Returns the Keycloak public key set in JWKS format. Called once by the Composer at startup and cached in memory. |

Response `200 OK`:
```json
{ "keys": [ { ... } ] }
```

---

### Token Endpoint

A single endpoint handles all token operations. The behaviour is determined by the `grant_type` field.

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/realms/{realm}/protocol/openid-connect/token` | Varies | Obtain or refresh a token, or authenticate as a service client. |

**Case 1 — User login** (`grant_type: password`):

Called by the Composer when a user logs in. Returns a user JWT.

```json
{
  "grant_type": "password",
  "client_id": "egs-platform",
  "username": "professor@ua.pt",
  "password": "..."
}
```

| Response | Description |
|---|---|
| `200 OK` | `{ "access_token": "<JWT>", "refresh_token": "...", "expires_in": 3600 }` |
| `401 Unauthorized` | Invalid credentials |

**Case 2 — Token refresh** (`grant_type: refresh_token`):

Called by the Composer when a user's access token has expired.

```json
{
  "grant_type": "refresh_token",
  "client_id": "egs-platform",
  "refresh_token": "..."
}
```

| Response | Description |
|---|---|
| `200 OK` | New `access_token` and `refresh_token` |
| `400 Bad Request` | Invalid or expired refresh token |

**Case 3 — Service authentication** (`grant_type: client_credentials`):

Called by the Composer before creating a new user. Returns a service token with administrative permissions. The `client_secret` is configured during Keycloak setup and provided to the Composer as an environment variable.

```json
{
  "grant_type": "client_credentials",
  "client_id": "egs-platform",
  "client_secret": "..."
}
```

| Response | Description |
|---|---|
| `200 OK` | `{ "access_token": "<service token>" }` |
| `401 Unauthorized` | Invalid client secret |

---

### User Management

| Method | Path | Auth required | Description |
|---|---|---|---|
| `POST` | `/realms/{realm}/users` | Yes — service token | Create a new user in Keycloak. |

Requires `Authorization: Bearer <service token>` obtained via Case 3 above.

Request body:
```json
{
  "email": "professor@ua.pt",
  "credentials": [{ "type": "password", "value": "..." }],
  "attributes": {
    "role": "professor",
    "institution": "universidade-aveiro"
  },
  "enabled": true
}
```

| Response | Description |
|---|---|
| `201 Created` | User created successfully |
| `409 Conflict` | A user with this email already exists |

---

## Deployment

> To be completed. Keycloak is deployed as a Docker container. Realm configuration, client registration, and the `client_secret` provisioning will be documented here alongside the `docker-compose` setup.
