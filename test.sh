#!/usr/bin/env bash

set -u

BASE="${BASE:-http://localhost:8080}"
KEY="${KEY:-stub-api-key}"

UPLOAD_FILE=$(mktemp)
trap 'rm -f "$UPLOAD_FILE"' EXIT
printf 'fake-video-content\n' > "$UPLOAD_FILE"

request_code() {
  local expected="$1"
  shift
  local label="$1"
  shift

  local code
  if ! code=$(curl -s -o /dev/null -w "%{http_code}" "$@"); then
    echo "FAIL $label -> curl execution error"
    return 1
  fi

  if [[ "$code" == "$expected" ]]; then
    echo "OK   $label -> $code"
    return 0
  fi

  echo "FAIL $label -> expected $expected got $code"
  return 1
}

echo "Running Video Editor API status tests against $BASE"

# No API key -> 401
request_code "401" "POST /jobs without API key" -X POST "$BASE/jobs" || exit 1

# DB status without API key -> 401
request_code "401" "GET /db/status without API key" "$BASE/db/status" || exit 1

# DB status with API key -> 200
request_code "200" "GET /db/status" \
  -H "X-API-Key: $KEY" "$BASE/db/status" || exit 1

# List supported operations -> 200
request_code "200" "GET /jobs/operations" \
  -H "X-API-Key: $KEY" "$BASE/jobs/operations" || exit 1

# PUT without API key -> 401
request_code "401" "PUT /jobs/{job_id} without API key" \
  -X PUT "$BASE/jobs/job_put_sem_key" \
  -H "Content-Type: application/json" \
  -d '{"src_url":"https://storage/raw/abc123.mp4","dst_url":"https://storage/processed/abc123.mp4","operations":[{"type":"rotate","params":{"degrees":90}}]}' || exit 1

UPSERT_ID="job_upsert_001"

# PUT create/replace valid job -> 202
request_code "202" "PUT /jobs/{job_id} valid" \
  -X PUT "$BASE/jobs/$UPSERT_ID" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"src_url":"https://storage/raw/abc123.mp4","dst_url":"https://storage/processed/abc123.mp4","operations":[{"type":"rotate","params":{"degrees":90}}]}' || exit 1

# PUT unknown operation -> 422
request_code "422" "PUT /jobs/{job_id} unknown operation" \
  -X PUT "$BASE/jobs/$UPSERT_ID" \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"src_url":"https://storage/raw/abc123.mp4","dst_url":"https://storage/processed/abc123.mp4","operations":[{"type":"inexistente"}]}' || exit 1

# DELETE valid job -> 204
request_code "204" "DELETE /jobs/{job_id}" \
  -X DELETE -H "X-API-Key: $KEY" "$BASE/jobs/$UPSERT_ID" || exit 1

# GET cancelled job -> 200
request_code "200" "GET /jobs/{job_id} cancelled" \
  -H "X-API-Key: $KEY" "$BASE/jobs/$UPSERT_ID" || exit 1

# DELETE missing job -> 404
request_code "404" "DELETE /jobs/job_inexistente" \
  -X DELETE -H "X-API-Key: $KEY" "$BASE/jobs/job_inexistente" || exit 1

# Valid create job with multipart upload -> 202
request_code "202" "POST /jobs valid multipart" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F "dst_url=https://storage/processed/abc123.mp4" \
  -F 'operations=[{"type":"watermark","params":{"text":"UA","position":"bottom-right","opacity":0.8}}]' || exit 1

# Missing file -> 400
request_code "400" "POST /jobs missing file" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "dst_url=https://storage/processed/abc123.mp4" \
  -F 'operations=[{"type":"watermark"}]' || exit 1

# Missing dst_url -> 400
request_code "400" "POST /jobs missing dst_url" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F 'operations=[{"type":"watermark"}]' || exit 1

# Missing operations -> 400
request_code "400" "POST /jobs missing operations" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F "dst_url=https://storage/processed/abc123.mp4" || exit 1

# Empty operations -> 400
request_code "400" "POST /jobs empty operations" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F "dst_url=https://storage/processed/abc123.mp4" \
  -F 'operations=[]' || exit 1

# Invalid operations JSON -> 400
request_code "400" "POST /jobs invalid operations JSON" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F "dst_url=https://storage/processed/abc123.mp4" \
  -F 'operations={invalid-json}' || exit 1

# Unknown operation -> 422
request_code "422" "POST /jobs unknown operation" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F "dst_url=https://storage/processed/abc123.mp4" \
  -F 'operations=[{"type":"inexistente"}]' || exit 1

# Create job and extract JOB_ID for follow-up tests
create_response=$(curl -s -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F "dst_url=https://storage/processed/abc123.mp4" \
  -F 'operations=[{"type":"rotate","params":{"degrees":90}}]')

JOB_ID=$(printf '%s' "$create_response" | sed -n 's/.*"job_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

if [[ -z "$JOB_ID" ]]; then
  echo "FAIL Could not parse job_id from response: $create_response"
  exit 1
fi

echo "Created job: $JOB_ID"

# Get valid job status -> 200
request_code "200" "GET /jobs/{job_id}" \
  -H "X-API-Key: $KEY" "$BASE/jobs/$JOB_ID" || exit 1

# Get missing job status -> 404
request_code "404" "GET /jobs/job_inexistente" \
  -H "X-API-Key: $KEY" "$BASE/jobs/job_inexistente" || exit 1

# Removed endpoint /jobs/{job_id}/operations should not exist -> 404
request_code "404" "GET /jobs/{job_id}/operations removed" \
  -H "X-API-Key: $KEY" "$BASE/jobs/$JOB_ID/operations" || exit 1

# Removed endpoint /jobs/{job_id}/progress should not exist -> 404
request_code "404" "GET /jobs/{job_id}/progress removed" \
  -H "X-API-Key: $KEY" "$BASE/jobs/$JOB_ID/progress" || exit 1

echo "All tests passed."
