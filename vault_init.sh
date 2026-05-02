#!/bin/sh
# Wait for Vault to start
echo "Waiting for Vault to start..."
until wget -q -O - http://vault:8200/v1/sys/health > /dev/null; do
  sleep 1
done

echo "Vault is up. Configuring..."

export VAULT_ADDR='http://vault:8200'
export VAULT_TOKEN='root'

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

# 3. Create Predefined Tokens matching the policies
echo "Creating predefined tokens..."
vault token create -id="token-composer" -policy="composer-policy"
vault token create -id="token-video-editor" -policy="video-editor-policy"
vault token create -id="token-object-storage" -policy="object-storage-policy"
vault token create -id="token-notifications" -policy="notifications-policy"

echo "Vault initialization complete!"
