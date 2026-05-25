# UA DETI Kubernetes Deployment Playbook

This playbook outlines the exact, step-by-step tasks required to configure your local machine, authenticate with the University of Aveiro (DETI) Kubernetes cluster, build/push images, and interact with the live deployed environment.

---

## 🔒 Step 1: Establish University VPN Connection
Before executing any tasks, you **must** be connected to the University of Aveiro's secure network.
* **Requirements:** Ensure your Check Point SNX VPN client is running and authenticated. 
* **Validation:** Without the VPN active, the cluster control plane IP (`193.136.82.35`) and internal DNS servers will be completely unreachable from your local machine.

---

## ⚙️ Step 2: Local Hostname Resolution (`/etc/hosts`)
You must tell your local operating system how to route requests for the platform domains and the internal University Docker registry.

1. Open `/etc/hosts` with administrator privileges:
   ```bash
   sudo nano /etc/hosts
   ```
2. Remove any old local dev mappings for `uastream.com` (such as `127.0.0.1 uastream.com`).
3. Add the following entry to map the domain, dashboard, and registry to the cluster master node:
   ```text
   193.136.82.35 uastream.com grafana.uastream.com registry.deti
   ```
4. Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## 🐋 Step 3: Configure Docker for the DETI Registry
The University hosts an insecure internal Docker registry at `registry.deti` (IP `193.136.82.35`). You must configure your local Docker daemon to trust it so you can push your built images.

1. Create or edit `/etc/docker/daemon.json` as root:
   ```bash
   sudo mkdir -p /etc/docker && sudo nano /etc/docker/daemon.json
   ```
2. Paste the following configuration:
   ```json
   {
     "insecure-registries": ["registry.deti"],
     "default-address-pools": [{"base": "10.139.0.0/16", "size": 24}]
   }
   ```
3. Save the file and restart your local Docker service to apply changes:
   ```bash
   sudo systemctl restart docker
   ```

---

## 🔑 Step 4: Configure Cluster Access (Kubeconfig)
Authenticate your local `kubectl` command-line tool with the live cluster using the working Service Account kubeconfig provided by your teammate.

1. Create your user's Kubernetes config directory:
   ```bash
   mkdir -p ~/.kube
   ```
2. Copy your teammate's kubeconfig yaml directly to the default config file location:
   ```bash
   cp -vf /home/joaquima/egs/k8s/tenant-grupo8-egs-deti-ua-pt-kubeconfig(2).yaml ~/.kube/config
   ```
3. Verify your connection to the cluster:
   ```bash
   kubectl get pods
   ```
   *(You should immediately see the running green list of databases, keycloak, composer, vault, and monitoring services!)*

---

## 🌐 Step 5: Accessing the Live Services
Once your `/etc/hosts` is updated and the cluster is running, you can access the platform services directly from your web browser:

| Service | Address | Default Credentials | Description |
| :--- | :--- | :--- | :--- |
| 🎬 **UAStream Website** | [http://uastream.com](http://uastream.com) | **Professor:** `professor@ua.pt` / `professor`<br>**Student:** `student@ua.pt` / `student` | Main video streaming portal. Sign-in redirects through Keycloak. |
| 📊 **Grafana Dashboard** | [http://grafana.uastream.com](http://grafana.uastream.com) | **Username:** `admin`<br>**Password:** `admin` | Real-time monitoring panels preloaded with your 7 custom dashboards. |

---

## 🛠️ Step 6: Building & Pushing Custom Code (Onboarding Devs)
If you modify a microservice's code on your local branch (e.g. adding a new feature to the `composer` or `notifications` service) and want to deploy it to the live Kubernetes cluster:

1. **Build and Tag the Image:**
   Build the Docker image locally, targeting the internal university registry and your group's specific namespace:
   ```bash
   # Example: Building the notifications service
   cd /home/joaquima/egs/egs/branches/notifications
   docker build --platform linux/amd64 -t registry.deti/tenant-grupo8-egs-deti-ua-pt/notifications:v1 .
   ```
2. **Push the Image to the DETI Registry:**
   ```bash
   docker push registry.deti/tenant-grupo8-egs-deti-ua-pt/notifications:v1
   ```
3. **Trigger a Rolling Update in Kubernetes:**
   Restart the pods in the cluster so they automatically pull the newly pushed image from the registry:
   ```bash
   kubectl rollout restart deployment notifications
   ```
