#!/bin/bash
echo "Adding professor user..."
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh create users -r egs -s username=professor@ua.pt -s enabled=true -s email=professor@ua.pt -s firstName=Professor -s lastName=User
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password -r egs --username professor@ua.pt --new-password professor
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh update users/$(docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh get users -r egs -q username=professor@ua.pt --fields id --format csv --noquotes) -r egs -s 'attributes={"role":["professor"]}'

echo "Adding student user..."
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh create users -r egs -s username=student@ua.pt -s enabled=true -s email=student@ua.pt -s firstName=Student -s lastName=User
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh set-password -r egs --username student@ua.pt --new-password student
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh update users/$(docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh get users -r egs -q username=student@ua.pt --fields id --format csv --noquotes) -r egs -s 'attributes={"role":["student"]}'
echo "Done!"
docker exec egs-keycloak-1 /opt/keycloak/bin/kcadm.sh add-roles -r egs --uusername service-account-egs-platform --cclientid realm-management --rolename manage-users
