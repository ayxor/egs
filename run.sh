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
    echo "[info] Updating $branch in $target_dir"
    git -C "$target_dir" fetch origin "$branch"
    git -C "$target_dir" pull --ff-only origin "$branch"
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
