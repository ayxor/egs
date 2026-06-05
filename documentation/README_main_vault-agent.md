# HashiCorp Vault Implementation and Specifications

This directory contains the configurations and templates for HashiCorp Vault. In the UAStream platform, Vault functions as the centralized secrets manager, ensuring that API keys, database credentials, and system tokens are not hardcoded or committed to git.

The platform supports two active deployment tracks (Kubernetes for production, Docker Compose for local development) and includes a proof-of-concept (PoC) reference for future security hardening via Vault Agent sidecars.

---

## 1. Production Kubernetes Deployment (Raft Backend & Auto-Unsealer)

In the production Kubernetes cluster, Vault is deployed as a stateful, resilient service under the manifest [2-vault.yaml](../k8s/manifests/2-vault.yaml).

### Architecture & Lifecycle
* **Storage Backend:** Vault runs in production mode using the **Raft integrated storage engine**. Data is persisted via a `PersistentVolumeClaim` (`vault-data-claim`, RWO) mounted to `/vault/data`.
* **The Auto-Unsealer Sidecar:** Since Vault initializes in a sealed state, the platform deploys a self-healing helper container (`vault-unsealer`) within the Vault pod. This sidecar runs an idempotent shell script (`unseal.sh` mounted from a ConfigMap) that:
  1. Checks if Vault is initialized. If not, initializes it and saves the unseal keys and root token to a Kubernetes Secret (`vault-unseal-keys`).
  2. If Vault is sealed, retrieves the keys from the Secret and unseals it.
  3. Mounts the KV-v2 engine at the `secret/` path and seeds the initial service tokens and API keys.
  4. Configures least-privilege read access policies (e.g. `composer-policy`).

### Microservice Secret Consumption
Active microservices in the Kubernetes cluster connect to Vault directly using the **`hvac` (HashiCorp Vault API client)** Python package:
* Pods load the Vault address (`VAULT_ADDR`) and their scoped static token (`VAULT_TOKEN`) from the centralized `uastream-secrets` Kubernetes Secret.
* Services fetch keys programmatically on startup (e.g., retrieving database URLs, SMTP credentials, or downstream service API keys) rather than reading rendered files from disk.

---

## 2. Local Development Deployment (Docker Compose)

For local testing, Vault is defined inside the main [docker-compose.yml](../docker-compose.yml).

### Dev Mode Mechanics
* **Startup Script:** The service runs using the custom entrypoint [vault_entrypoint.sh](../vault_entrypoint.sh) which runs Vault in **in-memory development mode** (`vault server -dev -dev-root-token-id=root`).
* **Seeding:** The entrypoint script waits for Vault to become responsive and then automatically performs the same KV engine mounting, secret seeding, and policy creation as the production unsealer.
* **Storage:** Data is ephemeral and resides solely in memory, ensuring clean state boundaries for local iterations.

---

## 3. Vault Agent Sidecar Proof of Concept (PoC)

The HCL and `.tpl` files located in this directory (`vault-agent/`) are **not currently active** in either the Docker Compose stack or the production Kubernetes manifests. They represent a reference architecture for a **hardened secret delivery pipeline** using AppRole authentication.

### Purpose of the PoC Files
In a hardened production model, applications should not have direct access to a long-lived `VAULT_TOKEN`. Instead:
1. **AppRole Authentication:** Each microservice container runs alongside a **Vault Agent sidecar** container.
2. **Dynamic Authentication:** The sidecar is provisioned with a short-lived AppRole role ID and secret ID mounted from the cluster secrets.
3. **Secret Rendering:** The Vault Agent logs in via AppRole, fetches the service's specific credentials, and renders them dynamically to a shared memory volume (e.g. `/vault/secrets/<service>.json`) using Consul-template syntax.
4. **Volume Sharing:** The main application container reads the JSON file from the shared volume, removing any direct network calls to Vault from the application code.

### Inventory of PoC Files

* **Agent Configurations (`*.hcl`):**
  - [composer-agent.hcl](composer-agent.hcl): Configures auth, listener, caching, and mounts template/destination paths for Composer.
  - [video-editor-agent.hcl](video-editor-agent.hcl): Scoped agent configurations for the video transcoding service.
  - [object-storage-agent.hcl](object-storage-agent.hcl): Scoped agent configurations for the binary store.
  - [notifications-agent.hcl](notifications-agent.hcl): Scoped agent configurations for the notifications service.

* **Template Blueprints (`templates/*.tpl`):**
  - `templates/composer.tpl`: Renders downstream service API keys.
  - `templates/video-editor.tpl`: Renders processing callback keys.
  - `templates/object-storage.tpl`: Renders binary access keys.
  - `templates/notifications.tpl`: Renders email transmission credentials.

These files are preserved in the repository as a blueprint for future infrastructure hardening.