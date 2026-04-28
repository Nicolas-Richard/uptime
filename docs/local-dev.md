# Local Development

## Prerequisites

- Python 3.11+
- Docker
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Quick Start

1. **Clone and install:**

   ```bash
   git clone <repo-url> && cd uptime
   uv venv .venv && source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

2. **Configure environment:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` if you need a custom `PORT_OFFSET` (see [Per-Worktree Stacks](#per-worktree-stacks) below).

3. **Start the dev stack** (DynamoDB Local + tables):

   ```bash
   make dev-stack
   ```

4. **Seed demo data** (creates users, orgs, checks, and runs one check cycle):

   ```bash
   make seed
   ```

   This creates three users: `admin`/`check-check-uptime-local`, `alice`/`alice123`, `bob`/`bob123`, two organizations with sample checks, and runs the checks so results are immediately available.

5. **In a second terminal**, start Django:

   ```bash
   source .venv/bin/activate
   make run-django
   ```

6. **In a third terminal**, start the local check runner:

   ```bash
   source .venv/bin/activate
   make run-runner
   ```

7. **Open Django** at `http://localhost:8000` (or `8000 + PORT_OFFSET`).

   Log in with `admin`/`check-check-uptime-local`, go to `/checks/` to see checks with results already populated.

## Per-Worktree Stacks

When running multiple workspaces (e.g. with [Conductor](https://www.conductor.build/)), set `PORT_OFFSET` so each workspace gets its own ports:

| Variable | Default | With `PORT_OFFSET=10` |
|---|---|---|
| `DJANGO_PORT` | 8000 | 8010 |
| `DYNAMODB_LOCAL_PORT` | 8001 | 8011 |

In your `.env`:

```bash
PORT_OFFSET=10
DJANGO_PORT=8010
DYNAMODB_LOCAL_PORT=8011
DYNAMODB_ENDPOINT_URL=http://localhost:8011
```

Then `make dev-stack` and `make run-django` will use the correct ports automatically.

## Makefile Targets

| Target | Description |
|---|---|
| `make dev-stack` | Start DynamoDB Local and create tables |
| `make run-django` | Run Django dev server |
| `make run-runner` | Run local check runner (polls every 60s) |
| `make create-tables` | Create DynamoDB tables (idempotent) |
| `make migrate` | Run Django database migrations |
| `make seed` | Seed demo users, orgs, checks, and results |
| `make test` | Run all tests with pytest |

## Production Configuration

Set these environment variables when deploying:

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | **Required** when `DJANGO_DEBUG=False`; app will refuse to start without it |
| `DJANGO_DEBUG` | Set to `False` in production |
| `ALLOWED_HOSTS` | Comma-separated list of allowed host headers (e.g. `uptime.example.com`) |
