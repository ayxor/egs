pid_file = "/tmp/vault-agent.pid"

auto_auth {
  method "approle" {
    config = {
      role_id_file_path   = "/vault/auth/approle-composer-agent-role-id"
      secret_id_file_path = "/vault/auth/approle-composer-agent-secret-id"
    }
  }
}

template {
  source      = "/etc/vault/templates/composer.tpl"
  destination = "/vault/secrets/composer.json"
  command     = "chmod 640 /vault/secrets/composer.json || true"
}

listener "tcp" {
  address     = "127.0.0.1:8100"
  tls_disable = true
}

vault {
  address = "http://vault:8200"
}