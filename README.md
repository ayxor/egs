# IAM Service

The IAM service is implemented with [Keycloak](https://www.keycloak.org/) and is the sole source of truth for identity in the EGS Video Platform. It is responsible for authenticating users, issuing and signing tokens, managing credentials, and exposing the public keys required by other services to validate JWTs.

The service is intentionally agnostic to platform business logic. It does not manage videos, storage, jobs, or notifications. Its job is identity, authentication, token issuance, and user administration.

**The Composer is the only platform service that communicates directly with IAM.**

---

## Responsibilities

- Authenticating end users through Keycloak login flows
- Issuing OAuth 2.0 / OpenID Connect tokens for authenticated users
- Exposing JWKS public keys so JWTs can be validated by Composer
- Managing user accounts, credentials, and required actions
- Storing IAM-specific user attributes such as `role` and `institution`
- Providing a service-account path so Composer can create users programmatically
- Serving the custom UAStream login theme used by the EGS platform

The IAM service does not store platform metadata such as uploaded videos, courses, descriptions, or processing jobs. Those concerns belong to the Composer and its database.

---

## API Reference

Base URL: `http://keycloak:8080`

This README documents the IAM endpoints used by the EGS platform integration.

### Realm Metadata / Public Keys

| Method | Path | Description |
|---|---|---|
| `GET` | `/realms/{realm}/.well-known/openid-configuration` | Returns OpenID Connect metadata for the realm. |
| `GET` | `/realms/{realm}/protocol/openid-connect/certs` | Returns the JWKS used by Composer to validate JWTs. |

**GET /realms/{realm}/protocol/openid-connect/certs**

Response `200 OK`:
```json
{
	"keys": [
		{
			"kid": "...",
			"kty": "RSA",
			"alg": "RS256",
			"use": "sig",
			"n": "...",
			"e": "AQAB"
		}
	]
}
```

---

### Token Endpoint

Keycloak uses a single token endpoint for multiple OAuth flows.

| Method | Path | Description |
|---|---|---|
| `POST` | `/realms/{realm}/protocol/openid-connect/token` | Exchange credentials, refresh tokens, or authorization codes for tokens. |

#### Password Grant

Used by the earlier Composer login flow and still useful for direct API testing.

Request body:
```json
{
	"grant_type": "password",
	"client_id": "egs-platform",
	"username": "user",
	"password": "user"
}
```

| Response | Description |
|---|---|
| `200 OK` | Returns `access_token`, `refresh_token`, `expires_in`, and related token metadata |
| `400 Bad Request` | Invalid grant, missing fields, or unmet account requirements |
| `401 Unauthorized` | Invalid client authentication |

#### Refresh Token Grant

Used by Composer to renew access without prompting the user again.

Request body:
```json
{
	"grant_type": "refresh_token",
	"client_id": "egs-platform",
	"refresh_token": "..."
}
```

| Response | Description |
|---|---|
| `200 OK` | Returns a new `access_token` and usually a new `refresh_token` |
| `400 Bad Request` | Refresh token is invalid or expired |

#### Authorization Code Grant

Used by the current browser-based sign-in flow.

Request body:
```json
{
	"grant_type": "authorization_code",
	"client_id": "egs-platform",
	"client_secret": "...",
	"code": "...",
	"redirect_uri": "http://localhost:8090/auth/callback"
}
```

| Response | Description |
|---|---|
| `200 OK` | Returns `access_token`, `refresh_token`, and `id_token` |
| `400 Bad Request` | Invalid code, redirect mismatch, or expired authorization code |

#### Client Credentials Grant

Used by Composer when it needs a service token to create or inspect users.

Request body:
```json
{
	"grant_type": "client_credentials",
	"client_id": "egs-platform",
	"client_secret": "..."
}
```

| Response | Description |
|---|---|
| `200 OK` | Returns a service `access_token` |
| `401 Unauthorized` | Invalid client secret |

---

### Authorization Endpoint

| Method | Path | Description |
|---|---|---|
| `GET` | `/realms/{realm}/protocol/openid-connect/auth` | Starts the browser login flow and redirects the user to the login page or back to the client with a code. |

Typical query parameters used by Composer:

| Parameter | Description |
|---|---|
| `client_id` | Client identifier (`egs-platform`) |
| `response_type` | `code` |
| `scope` | Usually `openid profile email` |
| `redirect_uri` | Callback URL on Composer |

---

### Logout Endpoint

| Method | Path | Description |
|---|---|---|
| `GET` | `/realms/{realm}/protocol/openid-connect/logout` | Terminates the Keycloak SSO session and redirects the browser back to Composer. |

Common query parameters:

| Parameter | Description |
|---|---|
| `post_logout_redirect_uri` | Where the browser should return after logout |
| `client_id` | Client identifier |
| `id_token_hint` | Helps Keycloak identify the session to end |

---

### User Management

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/realms/{realm}/users` | Create a new user via service token / admin privileges. |
| `GET` | `/admin/realms/{realm}/users` | Search or list users. |
| `PUT` | `/admin/realms/{realm}/users/{id}` | Update user attributes or flags. |
| `PUT` | `/admin/realms/{realm}/users/{id}/reset-password` | Set or reset a user password. |

**POST /admin/realms/{realm}/users**

Request body:
```json
{
	"username": "prof",
	"email": "prof@ua.pt",
	"enabled": true,
	"emailVerified": true,
	"attributes": {
		"role": ["professor"],
		"institution": ["universidade-aveiro"]
	},
	"credentials": [
		{
			"type": "password",
			"value": "prof",
			"temporary": false
		}
	]
}
```

| Response | Description |
|---|---|
| `201 Created` | User created successfully |
| `409 Conflict` | Username or email already exists |
| `403 Forbidden` | Service account lacks required roles |

---

## Token Claims

The EGS realm is configured so issued tokens carry the user metadata Composer needs.

| Claim | Description |
|---|---|
| `sub` | Keycloak user identifier |
| `email` | User email |
| `preferred_username` | Login username |
| `name` | Display name when available |
| `role` | EGS role such as `student` or `professor` |
| `institution` | Institution namespace, e.g. `universidade-aveiro` |

These claims are added through protocol mappers defined in the realm configuration.

---

## Deployment

### Local stack

The repository includes a local Docker-based setup for Keycloak and its PostgreSQL database.

```bash
docker compose up -d
```

Default local URLs:

- Keycloak: `http://localhost:8180`
- Composer: `http://localhost:8090`

### Realm configuration

The `egs` realm is imported from `keycloak/realm-egs.json` on fresh startup. This file configures:

- the realm itself
- the `egs-platform` client
- redirect URIs and web origins
- protocol mappers for custom claims
- the `uastream` login theme

### Theme assets

The custom login UI is stored under `keycloak/themes/uastream/login/` and includes:

- `theme.properties`
- `resources/css/uastream.css`
- `messages/messages_en.properties`

### Environment variables

| Variable | Description |
|---|---|
| `KEYCLOAK_ADMIN` | Admin username for the local Keycloak container |
| `KEYCLOAK_ADMIN_PASSWORD` | Admin password for the local Keycloak container |
| `KC_DB_URL` | JDBC URL for the Keycloak PostgreSQL database |
| `KC_DB_USERNAME` | Keycloak database username |
| `KC_DB_PASSWORD` | Keycloak database password |

### Notes

- The login/logout browser flow depends on the client redirect URIs configured in the realm.
- Post-logout redirects rely on the client attribute `post.logout.redirect.uris`.
- A fresh realm import happens only when Keycloak starts with a new database volume.
