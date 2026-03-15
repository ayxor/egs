# IAM Service (Keycloak)

This branch is the IAM integration branch.

It contains the Keycloak realm configuration used by EGS, the custom login theme, and the Compose setup required to run and validate IAM flows locally.

The Composer consumes IAM through OAuth/OIDC endpoints, while Keycloak remains the source of truth for identities and credentials.

## What Is In This Branch

- `keycloak/realm-egs.json`: realm export/import definition (realm, client, mappers, redirects)
- `keycloak/themes/uastream/login/`: custom login theme (CSS + messages)
- `keycloak.yaml`: IAM OpenAPI contract used in EGS docs
- `docker-compose.yml`: local stack wiring for Keycloak + Postgres

## Core IAM Endpoints Used By Composer

- `GET /realms/{realm}/protocol/openid-connect/certs`
- `POST /realms/{realm}/protocol/openid-connect/token`
- `POST /realms/{realm}/users` (service-account flow)

## Local Run

```bash
docker compose up -d
```

Key local URLs:

- Keycloak: `http://localhost:8180`
- Composer: `http://localhost:8090`

## Important Notes

- Realm import is applied from `keycloak/realm-egs.json` on fresh Keycloak DB volume.
- Custom login theme is mounted from `keycloak/themes/uastream`.
- Logout redirect support uses client attribute `post.logout.redirect.uris`.

## Branch Policy

- IAM/Keycloak work goes to `iam`.
- Composer-specific application work goes to `composer`.
