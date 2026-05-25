#!/bin/bash

echo "Authenticating via kcadm..."
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh config credentials --server http://127.0.0.1:8080 --realm master --user admin --password admin

echo "Granting manage-users to service account..."
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh add-roles -r egs --uusername service-account-egs-platform --cclientid realm-management --rolename manage-users || true

echo "Adding professor user..."
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh create users -r egs -s username=professor@ua.pt -s enabled=true -s email=professor@ua.pt -s firstName=Professor -s lastName=User || true
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password -r egs --username professor@ua.pt --new-password professor
export PROF_ID=$(docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh get users -r egs -q username=professor@ua.pt --fields id --format csv --noquotes | tr -d '\r')
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh update users/${PROF_ID} -r egs -s 'attributes={"role":["professor"]}'

echo "Adding student user..."
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh create users -r egs -s username=student@ua.pt -s enabled=true -s email=student@ua.pt -s firstName=Student -s lastName=User || true
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password -r egs --username student@ua.pt --new-password student
export STUD_ID=$(docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh get users -r egs -q username=student@ua.pt --fields id --format csv --noquotes | tr -d '\r')
docker exec main-keycloak-1 /opt/keycloak/bin/kcadm.sh update users/${STUD_ID} -r egs -s 'attributes={"role":["student"]}'

echo "Seeding complete!"

echo "Syncing users to Composer DB..."
docker exec -i main-db-1 psql -U composer -d composer -c "INSERT INTO users (keycloak_user_id, email, name, role, institution) VALUES ('${PROF_ID}', 'professor@ua.pt', 'Professor User', 'professor', 'Universidade de Aveiro') ON CONFLICT (email) DO UPDATE SET role = 'professor';"
docker exec -i main-db-1 psql -U composer -d composer -c "INSERT INTO users (keycloak_user_id, email, name, role, institution) VALUES ('${STUD_ID}', 'student@ua.pt', 'Student User', 'student', 'Universidade de Aveiro') ON CONFLICT (email) DO UPDATE SET role = 'student';"
