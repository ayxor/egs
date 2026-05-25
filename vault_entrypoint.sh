#!/bin/sh
set -e

# Start Vault server in the background
vault server -dev -dev-root-token-id=root -dev-listen-address=0.0.0.0:8200 &
VAULT_PID=$!

export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='root'

echo "Waiting for Vault to start..."
until vault status >/dev/null 2>&1; do
  sleep 0.5
done

echo "Vault is up. Seeding static secrets, policies, and tokens..."

# Enable KV v2 at 'secret/' path (if not already enabled)
vault secrets enable -path=secret kv-v2 || true

# 1. Create Secrets (API Keys)
vault kv put secret/object-storage api_key="stub-api-key"
vault kv put secret/video-editor api_key="stub-api-key"
vault kv put secret/notifications api_key="stub-api-key"

# 2. Create Policies
cat <<EOF | vault policy write composer-policy -
path "secret/data/object-storage" { capabilities = ["read"] }
path "secret/data/video-editor" { capabilities = ["read"] }
path "secret/data/notifications" { capabilities = ["read"] }
EOF

cat <<EOF | vault policy write video-editor-policy -
path "secret/data/video-editor" { capabilities = ["read"] }
path "secret/data/object-storage" { capabilities = ["read"] }
EOF

cat <<EOF | vault policy write object-storage-policy -
path "secret/data/object-storage" { capabilities = ["read"] }
EOF

cat <<EOF | vault policy write notifications-policy -
path "secret/data/notifications" { capabilities = ["read"] }
EOF

# 3. Create Predefined Tokens matching the policies
for t in token-composer token-video-editor token-object-storage token-notifications; do
  vault token revoke "$t" >/dev/null 2>&1 || true
done

vault token create -id="token-composer" -policy="composer-policy"
vault token create -id="token-video-editor" -policy="video-editor-policy"
vault token create -id="token-object-storage" -policy="object-storage-policy"
vault token create -id="token-notifications" -policy="notifications-policy"

echo "Vault initialization complete! Keeping Vault server in foreground..."
wait $VAULT_PID
