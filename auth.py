"""Authentication layer — Keycloak JWKS caching and token operations."""

import logging

import requests
from jose import jwt, JWTError

import config

logger = logging.getLogger(__name__)

_jwks = None


# ---------------------------------------------------------------------------
# JWKS (public key set — fetched once at startup)
# ---------------------------------------------------------------------------

def fetch_jwks():
    """Fetch and cache the Keycloak JWKS; called once on startup."""
    global _jwks
    url = (
        f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}"
        "/protocol/openid-connect/certs"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        _jwks = resp.json()
        logger.info("Keycloak JWKS fetched and cached")
    except Exception as exc:
        logger.warning("Failed to fetch JWKS from Keycloak: %s", exc)
        _jwks = None


def decode_token(token):
    """Validate and decode a JWT using the cached JWKS.

    Returns the full decoded payload dict.
    Raises jose.JWTError on any validation failure.
    """
    global _jwks
    if _jwks is None:
        fetch_jwks()
    if _jwks is None:
        raise JWTError("JWKS not available — Keycloak may be unreachable")

    try:
        return jwt.decode(
            token,
            _jwks,
            algorithms=["RS256"],
            audience=config.KEYCLOAK_CLIENT_ID,
            # Keycloak tokens may not carry an 'aud' matching the client_id
            # depending on realm configuration; disable strict aud check.
            options={"verify_aud": False},
        )
    except JWTError:
        # Retry once with a fresh JWKS in case keys rotated or startup fetch failed.
        fetch_jwks()
        if _jwks is None:
            raise
        return jwt.decode(
            token,
            _jwks,
            algorithms=["RS256"],
            audience=config.KEYCLOAK_CLIENT_ID,
            options={"verify_aud": False},
        )


# ---------------------------------------------------------------------------
# Token endpoint helpers (proxied by Composer on behalf of clients)
# ---------------------------------------------------------------------------

_TOKEN_URL = None


def _token_url():
    global _TOKEN_URL
    if _TOKEN_URL is None:
        _TOKEN_URL = (
            f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}"
            "/protocol/openid-connect/token"
        )
    return _TOKEN_URL


def login(email, password):
    """Authenticate a user via Keycloak (grant_type=password).

    Returns (http_status, response_body_dict).
    """
    resp = requests.post(
        _token_url(),
        data={
            "grant_type": "password",
            "client_id": config.KEYCLOAK_CLIENT_ID,
            "username": email,
            "password": password,
        },
        timeout=10,
    )
    return resp.status_code, resp.json()


def refresh_token(refresh_token_value):
    """Refresh an access token via Keycloak (grant_type=refresh_token).

    Returns (http_status, response_body_dict).
    """
    resp = requests.post(
        _token_url(),
        data={
            "grant_type": "refresh_token",
            "client_id": config.KEYCLOAK_CLIENT_ID,
            "refresh_token": refresh_token_value,
        },
        timeout=10,
    )
    return resp.status_code, resp.json()


def exchange_authorization_code(code, redirect_uri):
    """Exchange an OAuth authorization code for tokens.

    Returns (http_status, response_body_dict).
    """
    resp = requests.post(
        _token_url(),
        data={
            "grant_type": "authorization_code",
            "client_id": config.KEYCLOAK_CLIENT_ID,
            "client_secret": config.KEYCLOAK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=10,
    )
    try:
        data = resp.json()
    except ValueError:
        data = {"error": "non_json_response", "error_description": resp.text}
    return resp.status_code, data


def get_service_token():
    """Obtain a service-level token from Keycloak (grant_type=client_credentials).

    Returns the raw access_token string.
    Raises on failure.
    """
    resp = requests.post(
        _token_url(),
        data={
            "grant_type": "client_credentials",
            "client_id": config.KEYCLOAK_CLIENT_ID,
            "client_secret": config.KEYCLOAK_CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# User management (Admin REST API)
# ---------------------------------------------------------------------------

def create_keycloak_user(service_token, email, password, first_name, last_name, role, institution):
    """Create a new user in Keycloak.

    Returns (http_status, keycloak_user_id_or_error_body).
    On 201 the second element is the Keycloak user UUID string.
    """
    url = (
        f"{config.KEYCLOAK_URL}/admin/realms/{config.KEYCLOAK_REALM}/users"
    )

    body = {
        "username": email,
        "email": email,
        "firstName": first_name,
        "lastName": last_name,
        "emailVerified": True,
        "enabled": True,
        "credentials": [
            {"type": "password", "value": password, "temporary": False}
        ],
        "attributes": {
            "role": role,
            "institution": institution,
        },
    }
    resp = requests.post(
        url,
        json=body,
        headers={"Authorization": f"Bearer {service_token}"},
        timeout=10,
    )

    if resp.status_code == 201:
        # Keycloak returns the new user's ID in the Location header
        location = resp.headers.get("Location", "")
        keycloak_user_id = location.rsplit("/", 1)[-1] if location else ""
        return 201, keycloak_user_id

    return resp.status_code, resp.json() if resp.content else {}
