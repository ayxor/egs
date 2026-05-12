#!/bin/sh
set -e
# Ensure the Vault address/token are available to the CLI before any check
export VAULT_ADDR='http://vault:8200'
export VAULT_TOKEN='root'

echo "Waiting for Vault to start at $VAULT_ADDR..."
until vault status >/dev/null 2>&1; do
  sleep 1
done

echo "Vault is up. Configuring..."

# Enable KV v2 at 'secret/' path (if not already enabled)
vault secrets enable -path=secret kv-v2 || true

# 1. Create Secrets (API Keys)
echo "Storing API keys..."
vault kv put secret/object-storage api_key="stub-api-key"
vault kv put secret/video-editor api_key="stub-api-key"
vault kv put secret/notifications api_key="stub-api-key"

# 2. Create Policies
echo "Creating policies..."

# composer-policy: Needs to read all keys to orchestrate
cat <<EOF | vault policy write composer-policy -
path "secret/data/object-storage" { capabilities = ["read"] }
path "secret/data/video-editor" { capabilities = ["read"] }
path "secret/data/notifications" { capabilities = ["read"] }
EOF

# video-editor-policy: Needs to read its own key AND object-storage key
cat <<EOF | vault policy write video-editor-policy -
path "secret/data/video-editor" { capabilities = ["read"] }
path "secret/data/object-storage" { capabilities = ["read"] }
EOF

# object-storage-policy
cat <<EOF | vault policy write object-storage-policy -
path "secret/data/object-storage" { capabilities = ["read"] }
EOF

# notifications-policy
cat <<EOF | vault policy write notifications-policy -
path "secret/data/notifications" { capabilities = ["read"] }
EOF

# approle policy for the object-storage Vault Agent demo
cat <<EOF | vault policy write object-storage-agent-policy -
path "secret/data/object-storage" { capabilities = ["read"] }
EOF

cat <<EOF | vault policy write composer-agent-policy -
path "secret/data/object-storage" { capabilities = ["read"] }
path "secret/data/video-editor" { capabilities = ["read"] }
path "secret/data/notifications" { capabilities = ["read"] }
EOF

cat <<EOF | vault policy write video-editor-agent-policy -
path "secret/data/video-editor" { capabilities = ["read"] }
path "secret/data/object-storage" { capabilities = ["read"] }
EOF

cat <<EOF | vault policy write notifications-agent-policy -
path "secret/data/notifications" { capabilities = ["read"] }
EOF

# 3. Create Predefined Tokens matching the policies
echo "Creating predefined tokens..."
# Revoke any existing demo tokens to allow idempotent runs (dev-only)
for t in token-composer token-video-editor token-object-storage token-notifications; do
  echo "Revoking existing token (if any): $t"
  vault token revoke "$t" >/dev/null 2>&1 || true
done

# Create tokens (using fixed IDs so compose env can reference them)
vault token create -id="token-composer" -policy="composer-policy"
vault token create -id="token-video-editor" -policy="video-editor-policy"
vault token create -id="token-object-storage" -policy="object-storage-policy"
vault token create -id="token-notifications" -policy="notifications-policy"

# 4. Configure AppRole for the Vault Agent demos
echo "Configuring AppRole for Vault Agent demos..."
vault auth enable approle >/dev/null 2>&1 || true
vault write auth/approle/role/object-storage-agent \
  token_policies="object-storage-agent-policy" \
  token_ttl="1h" \
  token_max_ttl="24h" \
  token_num_uses=0 \
  secret_id_num_uses=0 \
  secret_id_ttl="24h" >/dev/null

vault write auth/approle/role/composer-agent \
  token_policies="composer-agent-policy" \
  token_ttl="1h" \
  token_max_ttl="24h" \
  token_num_uses=0 \
  secret_id_num_uses=0 \
  secret_id_ttl="24h" >/dev/null

vault write auth/approle/role/video-editor-agent \
  token_policies="video-editor-agent-policy" \
  token_ttl="1h" \
  token_max_ttl="24h" \
  token_num_uses=0 \
  secret_id_num_uses=0 \
  secret_id_ttl="24h" >/dev/null

vault write auth/approle/role/notifications-agent \
  token_policies="notifications-agent-policy" \
  token_ttl="1h" \
  token_max_ttl="24h" \
  token_num_uses=0 \
  secret_id_num_uses=0 \
  secret_id_ttl="24h" >/dev/null

ROLE_ID="$(vault read -field=role_id auth/approle/role/object-storage-agent/role-id)"
SECRET_ID="$(vault write -f -field=secret_id auth/approle/role/object-storage-agent/secret-id)"
COMPOSER_ROLE_ID="$(vault read -field=role_id auth/approle/role/composer-agent/role-id)"
COMPOSER_SECRET_ID="$(vault write -f -field=secret_id auth/approle/role/composer-agent/secret-id)"
VIDEO_EDITOR_ROLE_ID="$(vault read -field=role_id auth/approle/role/video-editor-agent/role-id)"
VIDEO_EDITOR_SECRET_ID="$(vault write -f -field=secret_id auth/approle/role/video-editor-agent/secret-id)"
NOTIFICATIONS_ROLE_ID="$(vault read -field=role_id auth/approle/role/notifications-agent/role-id)"
NOTIFICATIONS_SECRET_ID="$(vault write -f -field=secret_id auth/approle/role/notifications-agent/secret-id)"

# Persist the created token IDs to the shared vault-data volume so other
# services or agent sidecars can read them during this demo (demo-only).
OUT_DIR="/vault/data"
if [ ! -w "$OUT_DIR" ]; then
  if [ -d "/vault/file" ] && [ -w "/vault/file" ]; then
    OUT_DIR="/vault/file"
  else
    OUT_DIR=""
  fi
fi
if [ -n "$OUT_DIR" ]; then
  echo "token-composer" > "$OUT_DIR/token-composer" || echo "Could not write token-composer to $OUT_DIR"
  echo "token-video-editor" > "$OUT_DIR/token-video-editor" || echo "Could not write token-video-editor to $OUT_DIR"
  echo "token-object-storage" > "$OUT_DIR/token-object-storage" || echo "Could not write token-object-storage to $OUT_DIR"
  echo "token-notifications" > "$OUT_DIR/token-notifications" || echo "Could not write token-notifications to $OUT_DIR"
  echo "$ROLE_ID" > "$OUT_DIR/approle-object-storage-agent-role-id" || echo "Could not write approle role_id to $OUT_DIR"
  echo "$SECRET_ID" > "$OUT_DIR/approle-object-storage-agent-secret-id" || echo "Could not write approle secret_id to $OUT_DIR"
  echo "$COMPOSER_ROLE_ID" > "$OUT_DIR/approle-composer-agent-role-id" || echo "Could not write composer role_id to $OUT_DIR"
  echo "$COMPOSER_SECRET_ID" > "$OUT_DIR/approle-composer-agent-secret-id" || echo "Could not write composer secret_id to $OUT_DIR"
  echo "$VIDEO_EDITOR_ROLE_ID" > "$OUT_DIR/approle-video-editor-agent-role-id" || echo "Could not write video-editor role_id to $OUT_DIR"
  echo "$VIDEO_EDITOR_SECRET_ID" > "$OUT_DIR/approle-video-editor-agent-secret-id" || echo "Could not write video-editor secret_id to $OUT_DIR"
  echo "$NOTIFICATIONS_ROLE_ID" > "$OUT_DIR/approle-notifications-agent-role-id" || echo "Could not write notifications role_id to $OUT_DIR"
  echo "$NOTIFICATIONS_SECRET_ID" > "$OUT_DIR/approle-notifications-agent-secret-id" || echo "Could not write notifications secret_id to $OUT_DIR"
else
  echo "No writable vault volume found; tokens not persisted to disk. Tokens:" 
  echo " token-composer token-video-editor token-object-storage token-notifications"
fi

echo "Vault initialization complete!"
