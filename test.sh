#!/bin/bash

BASE="http://localhost:5000"
KEY="stub-api-key"

echo "Running tests against $BASE..."

# Create a temporary file for upload testing
echo "Hello, Object Storage!" > test_data.txt

# ---
# 1. Authentication & Authorization
# ---
echo -n "No API key -> "
curl -s -o /dev/null -w "%{http_code}\n" -X GET "$BASE/buckets"

# ---
# 2. Buckets
# ---
echo -n "List all buckets (empty or existing) -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/buckets"

echo -n "Create a new bucket (test-bucket) -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X PUT "$BASE/buckets/test-bucket"

echo -n "Create same bucket again -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X PUT "$BASE/buckets/test-bucket"

echo -n "List buckets with search query -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/buckets?query=test"

# ---
# 3. Objects
# ---
echo -n "Upload object (test-file.txt) to test-bucket -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" \
    -H "Content-Type: application/octet-stream" \
    --data-binary @test_data.txt \
    -X PUT "$BASE/objects/test-bucket?key=test-file.txt"

echo -n "Upload nested object (nested/folder/test-file.txt) to test-bucket -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" \
    -H "Content-Type: application/octet-stream" \
    --data-binary @test_data.txt \
    -X PUT "$BASE/objects/test-bucket?key=nested/folder/test-file.txt"

echo -n "List all objects in test-bucket -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/objects/test-bucket"

echo -n "List objects in test-bucket with search query -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/objects/test-bucket?query=nested"

echo -n "Download object (test-file.txt) -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/objects/test-bucket/test-file.txt"

echo -n "Download object with Range -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -H "Range: bytes=0-5" -X GET "$BASE/objects/test-bucket/test-file.txt"

echo -n "Download non-existent object -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/objects/test-bucket/nonexistent.txt"

# ---
# 4. Interacting with bad identifiers
# ---
echo -n "List objects in non-existent bucket -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X GET "$BASE/objects/non-existent-bucket"

# ---
# 5. Cleanup (Deletion)
# ---
echo -n "Delete object (test-file.txt) -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X DELETE "$BASE/objects/test-bucket?key=test-file.txt"

echo -n "Delete non-existent object -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X DELETE "$BASE/objects/test-bucket?key=test-file.txt"

echo -n "Delete bucket (test-bucket) -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X DELETE "$BASE/buckets/test-bucket"

echo -n "Delete non-existent bucket -> "
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $KEY" -X DELETE "$BASE/buckets/test-bucket"

# Clean up temp file
rm test_data.txt

echo "Done!"
