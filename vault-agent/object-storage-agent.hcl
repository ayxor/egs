
pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    config = {
      role_id_file_path   = "/vault/auth/approle-object-storage-agent-role-id"
      secret_id_file_path = "/vault/auth/approle-object-storage-agent-secret-id"
    }
  }
}

template {
  source      = "/etc/vault/templates/object-storage.tpl"
  destination = "/vault/secrets/object-storage.json"
  command = "chmod 640 /vault/secrets/object-storage.json || true"
}

listener "tcp" {
  address = "127.0.0.1:8100"
  tls_disable = true
}

vault {
  address = "http://vault:8200"
}
