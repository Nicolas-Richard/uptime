# Uptime Monitoring Platform

Multi-tenant SaaS for HTTP(S) uptime checks. A single Lambda runs all active checks every minute via EventBridge, stores results in DynamoDB, and a Django dashboard lets users manage checks and view results — all scoped by tenant.

## Components

- **Django dashboard** (`src/`) — multi-tenant UI for managing checks and viewing results. Auth, organizations, checks, and results as modular apps.
- **Lambda handler** (`lambda_handler/`) — reads active checks from DynamoDB, runs HTTP checks in parallel (asyncio + aiohttp), writes results back.
- **`core.uptime_checks`** (`core/`) — shared async HTTP check library used by both the Lambda and the local runner.
- **Scripts** (`scripts/`) — `dev-stack.sh` (start local stack), `create_local_tables.py` (bootstrap DynamoDB), `run_checks_local.py` (local check runner).

## Links

- [Design doc](docs/plans/1-uptime-monitoring/design.md)
- [Local development guide](docs/local-dev.md)
