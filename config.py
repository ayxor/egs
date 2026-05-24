"""Composer configuration — all values come from environment variables."""

import os
import hvac
import time

def get_vault_secret(secret_path, env_fallback, default_val=""):
    vault_addr = os.environ.get("VAULT_ADDR")
    vault_token = os.environ.get("VAULT_TOKEN")

    if not (vault_addr and vault_token):
        return os.environ.get(env_fallback, default_val)

    attempts = 5
    delay = 0.5
    for attempt in range(1, attempts + 1):
        try:
            client = hvac.Client(url=vault_addr, token=vault_token)
            if client.is_authenticated():
                response = client.secrets.kv.v2.read_secret_version(path=secret_path)
                return response['data']['data']['api_key']
            else:
                print(f"Vault auth failed on attempt {attempt}")
        except Exception as e:
            print(f"Failed to fetch {secret_path} from Vault (attempt {attempt}): {e}")

        if attempt < attempts:
            time.sleep(delay)
            delay = min(delay * 2, 5)

    return os.environ.get(env_fallback, default_val)

# Keycloak / IAM
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_PUBLIC_URL = os.environ.get("KEYCLOAK_PUBLIC_URL", KEYCLOAK_URL)
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "egs")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "egs-platform")
KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")

# Internal services
OBJECT_STORAGE_URL = os.environ.get("OBJECT_STORAGE_URL", "http://object-storage:8080")
OBJECT_STORAGE_API_KEY = get_vault_secret("object-storage", "OBJECT_STORAGE_API_KEY")

VIDEO_EDITOR_URL = os.environ.get("VIDEO_EDITOR_URL", "http://video-editor:8080")
VIDEO_EDITOR_API_KEY = get_vault_secret("video-editor", "VIDEO_EDITOR_API_KEY")

NOTIFICATIONS_URL = os.environ.get("NOTIFICATIONS_URL", "http://notifications:8080")
NOTIFICATIONS_API_KEY = get_vault_secret("notifications", "NOTIFICATIONS_API_KEY")

# Self (used to build the progress_url callback for the Video Editor)
COMPOSER_BASE_URL = os.environ.get("COMPOSER_BASE_URL", "http://composer:8080")

# PostgreSQL
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://composer:composer@db:5432/composer")

# Presigned URL validity (seconds)
PRESIGNED_URL_EXPIRY = int(os.environ.get("PRESIGNED_URL_EXPIRY", "3600"))
