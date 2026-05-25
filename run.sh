#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)
PARENT_DIR=$(dirname "$REPO_ROOT")

# Branches required by docker-compose.yml build contexts
REQUIRED_BRANCHES=(composer iam object-storage video-editor notifications)

ensure_worktree() {
  local branch="$1"
  local target_dir="$PARENT_DIR/$branch"

  if [[ -d "$target_dir" ]]; then
    echo "[ok] $branch already present at $target_dir"
    return 0
  fi

  echo "[info] Creating worktree for $branch at $target_dir"

  # Make sure we have the branch reference
  if ! git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$branch"; then
    git -C "$REPO_ROOT" fetch origin "$branch"
    git -C "$REPO_ROOT" worktree add -b "$branch" "$target_dir" "origin/$branch"
  else
    git -C "$REPO_ROOT" worktree add "$target_dir" "$branch"
  fi
}

# Check if all required branches are available
for branch in "${REQUIRED_BRANCHES[@]}"; do
  ensure_worktree "$branch"
done

echo "[info] Starting stack from $REPO_ROOT"
cd "$REPO_ROOT"
docker compose up --build -d

echo "[info] Waiting for Keycloak IAM to be ready (this can take up to 20-30 seconds)..."
until [ "$(curl -s -o /dev/null -w "%{http_code}" -H "Host: uastream.com" http://localhost/realms/egs)" -eq 200 ]; do
  sleep 2
done

echo "[info] Keycloak is ready! Seeding database users..."
./seed_users.sh

echo "[info] UAStream platform started and seeded successfully! Configure uastream.com in /etc/hosts and open http://uastream.com to test."
