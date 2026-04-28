#!/usr/bin/env bash
# Start the local dev stack: DynamoDB Local + table creation.
# Respects PORT_OFFSET (default 0) for per-worktree port isolation.

set -euo pipefail

PORT_OFFSET="${PORT_OFFSET:-0}"
DYNAMODB_LOCAL_PORT="${DYNAMODB_LOCAL_PORT:-$((8001 + PORT_OFFSET))}"
DJANGO_PORT="${DJANGO_PORT:-$((8000 + PORT_OFFSET))}"

export PORT_OFFSET DYNAMODB_LOCAL_PORT DJANGO_PORT
export DYNAMODB_ENDPOINT_URL="${DYNAMODB_ENDPOINT_URL:-http://localhost:${DYNAMODB_LOCAL_PORT}}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTAINER_NAME="uptime-dynamodb-${PORT_OFFSET}"

# Start DynamoDB Local, reusing existing container if already running on the right port.
if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    echo "DynamoDB Local container '${CONTAINER_NAME}' already running."
else
    echo "Starting DynamoDB Local on port ${DYNAMODB_LOCAL_PORT}..."
    docker compose -f "$PROJECT_DIR/compose.yml" up -d
fi

echo "Creating local tables..."
"$PROJECT_DIR/.venv/bin/python" "$SCRIPT_DIR/create_local_tables.py"

echo ""
echo "DynamoDB Local on port ${DYNAMODB_LOCAL_PORT}."
echo "Run Django:  make run-django"
echo "Run runner:  make run-runner"
echo "Django URL:  http://localhost:${DJANGO_PORT}"
