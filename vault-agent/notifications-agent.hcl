pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    config = {
      role_id_file_path   = "/vault/auth/approle-notifications-agent-role-id"
      secret_id_file_path = "/vault/auth/approle-notifications-agent-secret-id"
    }
  }
}

template {
  source      = "/etc/vault/templates/notifications.tpl"
  destination = "/vault/secrets/notifications.json"
  command     = "chmod 640 /vault/secrets/notifications.json || true"
}

listener "tcp" {
  address     = "127.0.0.1:8100"
  tls_disable = true
}

vault {
  address = "http://vault:8200"
}