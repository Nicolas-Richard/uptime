"""Per-worktree configuration derived from environment variables.

PORT_OFFSET controls port allocation for parallel worktrees:
  - DJANGO_PORT = 8000 + PORT_OFFSET (default 8000)
  - DYNAMODB_LOCAL_PORT = 8001 + PORT_OFFSET (default 8001)
  - DYNAMODB_ENDPOINT_URL defaults to http://localhost:{DYNAMODB_LOCAL_PORT}

Set PORT_OFFSET in .env (e.g. 10 for ports 8010/8011, 20 for 8020/8021).
Explicit DJANGO_PORT / DYNAMODB_LOCAL_PORT override the derived values.
"""
import os

PORT_OFFSET = int(os.environ.get("PORT_OFFSET", "0"))

DJANGO_PORT = int(os.environ.get("DJANGO_PORT", str(8000 + PORT_OFFSET)))

DYNAMODB_LOCAL_PORT = int(os.environ.get("DYNAMODB_LOCAL_PORT", str(8001 + PORT_OFFSET)))

DYNAMODB_ENDPOINT_URL = os.environ.get(
    "DYNAMODB_ENDPOINT_URL",
    f"http://localhost:{DYNAMODB_LOCAL_PORT}",
)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
