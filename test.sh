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

# Email válido -> 202
curl -s -o /dev/null -w "%{http_code}\n" -X POST $BASE/notifications/email \
    -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
    -d '{"to":"prof@ua.pt","subject":"Teste","template":"upload_complete","data":{"name":"Prof Diogo","title":"Aula 1"}}'

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