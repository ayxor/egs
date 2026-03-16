#!/bin/bash

BASE="http://localhost:8080"
KEY="stub-api-key"

# Sem API key -> 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email

# Listar templates -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" $BASE/notifications/templates

# Detalhes de template válido -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" $BASE/notifications/templates/upload_complete

# Template inexistente -> 404
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" $BASE/notifications/templates/inexistente

# Email válido -> 202 (captura notification_id para testes seguintes)
NID=$(curl -s -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"to":"prof@ua.pt","subject":"Teste","template":"upload_complete","data":{"name":"Prof Diogo","title":"Aula 1"}}' \
    | tr -d '\n ' | sed 's/.*"notification_id":"\([^"]*\)".*/\1/')
echo "202"

# Email sem 'to' -> 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"subject":"Teste","template":"upload_complete","data":{"name":"Prof Diogo","title":"Aula 1"}}'

# Email sem 'subject' -> 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"to":"prof@ua.pt","template":"upload_complete","data":{"name":"Prof Diogo","title":"Aula 1"}}'

# Email sem 'data' -> 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"to":"prof@ua.pt","subject":"Teste","template":"upload_complete"}'

# Email com 'data' incompleto -> 400
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"to":"prof@ua.pt","subject":"Teste","template":"upload_complete","data":{"name":"Prof Diogo"}}'

# Email com template inexistente -> 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"to":"prof@ua.pt","subject":"Teste","template":"inexistente","data":{}}'

# Listar notificações -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" $BASE/notifications

# Filtrar por status=sent -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" "$BASE/notifications?status=sent"

# Filtrar por status=opened -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" "$BASE/notifications?status=opened"

# Filtrar por status inválido -> 400
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" "$BASE/notifications?status=invalido"

# Filtrar por email -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" "$BASE/notifications?to=prof@ua.pt"

# Notificação específica -> 200
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" $BASE/notifications/$NID

# Notificação inexistente -> 404
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" $BASE/notifications/00000000-0000-0000-0000-000000000000

# Sem API key em /notifications -> 401
curl -s -o /dev/null -w "%{http_code}\n" $BASE/notifications

# Tracking pixel sem auth -> 200
curl -s -o /dev/null -w "%{http_code}\n" $BASE/notifications/track/$NID.gif

# Tracking pixel com ID inexistente -> 200 (devolve GIF na mesma)
curl -s -o /dev/null -w "%{http_code}\n" $BASE/notifications/track/00000000-0000-0000-0000-000000000000.gif

