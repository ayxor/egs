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

# List supported operations -> 200
request_code "200" "GET /jobs/operations" \
  -H "X-API-Key: $KEY" "$BASE/jobs/operations" || exit 1

# Valid create job with multipart upload -> 202
request_code "202" "POST /jobs valid multipart" \
  -X POST "$BASE/jobs" \
      -H "X-API-Key: $KEY" \
      -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
      -F 'operations=[{"type":"watermark","params":{"text":"UA","position":"bottom-right","opacity":0.8}}]' || exit 1

# Missing file -> 400
request_code "400" "POST /jobs missing file" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F 'operations=[{"type":"watermark"}]' || exit 1

# Missing operations -> 400
request_code "400" "POST /jobs missing operations" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" || exit 1

# Invalid operations JSON -> 400
request_code "400" "POST /jobs invalid operations JSON" \
  -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
  -F 'operations={invalid-json}' || exit 1

# Create job and extract JOB_ID for follow-up tests
create_response=$(curl -s -X POST "$BASE/jobs" \
  -H "X-API-Key: $KEY" \
  -F "file=@$UPLOAD_FILE;filename=demo.mp4" \
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

echo "All tests passed."
