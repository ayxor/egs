# Grafana Observability

This folder contains the Grafana side of UAStream observability.
It explains what we measure, why we measure it, and how the dashboards are organized.

## Purpose

Grafana is the human-facing layer on top of Prometheus.
Prometheus scrapes the service `/metrics` endpoints, and Grafana turns those time series into dashboards that show health, traffic, latency, errors, saturation, and pipeline state.

The goal is not just to watch servers.
The goal is to answer three questions quickly:

- Is the platform healthy right now?
- Which service is failing or slowing down?
- Is the problem in the app, the worker pipeline, or the infrastructure?

## Data Source

The dashboards use the default Prometheus datasource defined in [provisioning/datasources/datasource.yml](provisioning/datasources/datasource.yml).

The datasource points to `http://prometheus:9090` inside the stack.

## Dashboard Provisioning

Grafana loads dashboards from [provisioning/dashboards/dashboards.yaml](provisioning/dashboards/dashboards.yaml).

That provider watches [provisioning/dashboards/files](provisioning/dashboards/files) and refreshes the JSON dashboards automatically.

## Dashboard Catalog

### 01. UAStream Platform Overview Dashboard

File: [platform_overview.json](provisioning/dashboards/files/platform_overview.json)

Why it exists:

- Gives the quickest at-a-glance health view for the whole platform
- Surfaces ingress health, service health, active jobs, queue pressure, and request/error hot spots
- Helps answer “is something broken?” before drilling into one service

### 02. UAStream Composer API Dashboard

File: [composer_api.json](provisioning/dashboards/files/composer_api.json)

Why it exists:

- Composer is the main public entrypoint and orchestration layer
- Its traffic, error rate, and latency show whether user-facing flows are stable
- It is usually the first place to look when uploads, auth, or playback workflows misbehave

### 03. UAStream Video Processing Dashboard

File: [video_processing.json](provisioning/dashboards/files/video_processing.json)

Why it exists:

- Video processing is asynchronous and can fail independently from the UI
- This dashboard shows backlog, job states, completion/failure ratio, and worker ingress traffic
- It helps distinguish a slow pipeline from a broken web request path

### 04. UAStream IAM Keycloak Dashboard

File: [iam_keycloak.json](provisioning/dashboards/files/iam_keycloak.json)

Why it exists:

- Identity issues often look like app failures to users
- Login rate, token handling, DB pool health, cache behavior, CPU, and memory help isolate IAM problems
- It is the quickest way to see whether auth failures are coming from Keycloak or the app

### 05. UAStream Object Storage Dashboard

File: [storage.json](provisioning/dashboards/files/storage.json)

Why it exists:

- Storage is the byte backend for uploads, processed videos, and thumbnails
- Throughput, errors, and latency tell you whether media access is healthy
- Range-based playback and direct object access depend on this service staying responsive

### 06. UAStream Notifications Dashboard

File: [notifications.json](provisioning/dashboards/files/notifications.json)

Why it exists:

- Notifications is a background delivery service, so failures can be silent without metrics
- Delivery states, send success/failure ratio, and API traffic show whether mail is flowing
- The dashboard helps confirm that user-facing events are actually being delivered

### 07. UAStream Infrastructure USE Dashboard

File: [infrastructure_use.json](provisioning/dashboards/files/infrastructure_use.json)

Why it exists:

- This is the infrastructure-level view rather than an application view
- It uses the USE model: utilization, saturation, and errors for pods and namespace resources
- It helps answer whether the cluster itself is the bottleneck

## Observability Model

UAStream uses two common patterns:

- **RED** for request-driven services: rate, errors, duration
- **USE** for infrastructure: utilization, saturation, errors

That split is intentional.
RED is best for HTTP services like Composer, Object Storage, Notifications, and IAM.
USE is best for pod and namespace capacity issues.

The platform overview combines both so operators can move from symptom to root cause faster.

## What To Add To A New Service

When adding another service dashboard, the usual checklist is:

- expose a `/metrics` endpoint
- add a Prometheus scrape target
- create one RED-style dashboard for service traffic
- add a panel or two to the platform overview if the service is user-critical
- document the dashboard in this README

## Access

In the local compose stack, Grafana is started from the `main` branch and uses the provisioning files in this folder.

In the Kubernetes deployment, Grafana is exposed through `http://grafana.uastream.com`.

## Related Docs

- [main README](../README.md)
- [Deployment architecture](../k8s/deployment_architecture.md)
- [Kubernetes playbook](../k8s/deti_deployment_playbook.md)