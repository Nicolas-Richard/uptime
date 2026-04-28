# Uptime Monitoring Platform — Design

**Date:** 2025-03-04  
**Status:** Approved  
**Scope:** Minimal multi-tenant SaaS for HTTP(S) uptime checks; Django dashboard, Lambda execution every minute, DynamoDB storage.

---

## 1. Architecture & Repos

**Repos and ownership**

- **Uptime repo** (new repo `uptime`): All application code. Modular monolith (Django + shared check library + Lambda handler). No infra definitions in this repo.
- **Infra repo** (separate Terraform repo): Infra for this product lives in a sandbox AWS account (e.g. subfolder `uptime/` or equivalent). Defines DynamoDB tables, scheduler Lambda, EventBridge rule, IAM.

**Runtime flow**

1. **EventBridge** runs every 1 minute (cron) and invokes **one Lambda**.
2. Lambda reads **active checks** from DynamoDB (`checks` table), runs HTTP checks **in parallel** (asyncio + aiohttp), and writes **results** to DynamoDB (`results` table).
3. **Django** (dashboard) reads/writes checks and results via **boto3** against the same DynamoDB tables. Django holds **users and organizations** (tenant model) in its own DB (SQLite dev, Postgres when deployed); all checks/results access is scoped by `tenant_id` (organization id).

**Summary:** One Lambda, one EventBridge rule, two DynamoDB tables (checks, results), Django as the only UI/API for managing checks and viewing results.

---

## 2. Data Model

**DynamoDB — checks**

- **Table:** `checks`
- **PK:** `tenant_id` (string, e.g. org UUID).
- **SK:** `check_id` (string, e.g. UUID).
- **Attributes:** `name`, `url`, `is_active` (bool), `created_at`, `updated_at`, optional `timeout_seconds` (default e.g. 30).
- **Lambda read:** For "all active checks" either (a) query by `tenant_id` and filter `is_active = true`, or (b) **GSI** with `is_active` as PK and `tenant_id` as SK to avoid full scan. Option (b) preferred at scale.

**DynamoDB — results**

- **Table:** `results`
- **PK:** `check_id`.
- **SK:** `timestamp` (string, e.g. ISO8601 or epoch ms) for time-ordered results per check.
- **Attributes:** `tenant_id`, `status` (e.g. `up` / `down`), `status_code` (int or null), `response_time_ms` (int), `error_message` (optional).
- **Dashboard:** "Recent results for this check" → query by `check_id`, SK descending. "Recent for this tenant" → GSI with `tenant_id` as PK, `timestamp` as SK.

**Django (auth & tenancy)**

- **SQLite (dev) / Postgres (deployed):** `User` (Django auth), `Organization` (tenant: id, name, slug, etc.), `OrganizationMembership` (user ↔ org, optional role). No `Check` model in Django DB; checks live only in DynamoDB. Django uses boto3 to read/write `checks` and `results`, always scoped by current user's `organization_id` (= `tenant_id`).

**Summary:** Single source of truth for checks/results = DynamoDB. Single source of truth for users/tenants = Django DB. `tenant_id` links them and enforces multi-tenant isolation.

---

## 3. Components

**Uptime repo layout (modular monolith)**

- **`src/`** (or **`uptime/`**) — Django project root: `settings`, `urls`, `wsgi`, `asgi`.
- **Modules (Django apps):**
  - **`auth`** — Login/logout, registration (Django auth); **AuthBackend** abstraction (interface) for future SSO; no business logic.
  - **`organizations`** — Organization and Membership models, "current org" for session, tenant-scoping helpers.
  - **`checks`** — Dashboard UI and API for checks: list/create/edit/delete. Talks to DynamoDB via a small **checks service layer** (boto3); all access keyed by `tenant_id` from current user's org.
  - **`results`** — Dashboard UI and API for results: "recent results for this check" (and optionally "recent for this tenant"). Reads from DynamoDB via a **results service layer**; same tenant scoping.
- **`core/`** (or **`shared/`**) — Shared Python package **`uptime_checks`**: pure HTTP check logic (e.g. `run_http_check(url, timeout_seconds) -> status, status_code, response_time_ms, error_message`). Implemented with **asyncio + aiohttp** so Lambda can run many checks concurrently. No Django, no boto3; only stdlib + aiohttp. Single place that "performs one HTTP check."
- **`lambda/`** — Lambda handler: on invoke, (1) create boto3 DynamoDB client, (2) load active checks (query/scan with `is_active` or via GSI), (3) run checks in parallel using `uptime_checks` (asyncio loop), (4) batch-write results to `results` table. Handler is thin; all check logic in `core/uptime_checks`.
- **`scripts/`** — **Local runner** `run_checks_local.py`: loop (e.g. every 60s), read checks from DynamoDB (DynamoDB Local endpoint via env), call `uptime_checks.run_http_check` for each (same async batch as Lambda), write results to DynamoDB Local. No Lambda/EventBridge on the laptop; agents can set breakpoints in the shared library and runner.

**Deployment / infra (Terraform repo only)**

- Lambda code is built from the uptime repo (zip or container image); the Terraform repo references that artifact and deploys the function, EventBridge rule (rate 1 min), and IAM. No application code in the Terraform repo beyond wiring.

**Summary:** One shared `uptime_checks` package (async HTTP check), one Lambda that uses it with high concurrency, one local script that reuses the same package against DynamoDB Local. Django is the only UI/API and remains stateless for checks/results (DynamoDB as store).

---

## 4. Local Dev & Agent Iteration (incl. Per-Worktree Stacks)

**Goal:** Agents (and developers) can run and debug the full stack on a laptop without deploying to AWS. When using [Conductor](https://www.conductor.build/) (or multiple worktrees), each agent can bring up a **dedicated** stack with everything correctly wired and no port conflicts.

**Stack on the laptop**

- **Django:** `python manage.py runserver`. Uses SQLite (or local Postgres) for User/Organization/Membership. Settings use env for DynamoDB endpoint and optional AWS credentials.
- **DynamoDB Local:** Run in Docker (e.g. `amazon/dynamodb-local`). Port is **configurable** so multiple stacks can run on the same machine.
- **Local runner:** `scripts/run_checks_local.py` (or `python -m core.runner`). Same loop as production: read checks from DynamoDB (DynamoDB Local when `DYNAMODB_ENDPOINT_URL` is set), run checks via `uptime_checks`, write results. Agents can set breakpoints in `uptime_checks` and in the runner.

**Per-worktree / Conductor-friendly stacks**

- **Configurable ports via env:** All local services use env-driven ports so each worktree can choose a unique range:
  - **Option A:** `PORT_OFFSET` (e.g. 0, 10, 20) → Django = `8000 + PORT_OFFSET`, DynamoDB Local = `8001 + PORT_OFFSET`.
  - **Option B:** Explicit `DJANGO_PORT` and `DYNAMODB_LOCAL_PORT`. Document defaults (e.g. 8000, 8001) for single-stack use.
  - `DYNAMODB_ENDPOINT_URL=http://localhost:${DYNAMODB_LOCAL_PORT}` so Django and the runner point at the correct DynamoDB Local for that stack.
- **Single "bring up stack" path:** One script or `make` target (e.g. `make dev-stack` or `./scripts/dev-stack.sh`) that: (1) starts DynamoDB Local on the configured port, (2) creates local tables if needed, (3) optionally starts Django and the local runner. The agent sets `PORT_OFFSET` (or equivalent) for that worktree and runs the same command; no manual port or URL guessing.
- **Documentation:** README or `docs/local-dev.md` states: "For a dedicated worktree, set `PORT_OFFSET` (e.g. 10 for 8010/8011) and run `make dev-stack`; Django will be on 8000+PORT_OFFSET, DynamoDB Local on 8001+PORT_OFFSET." Conductor users set these in the workspace env so each agent's stack is correctly wired and discoverable.

**Config / env**

- **`.env.example`** in the repo: `DYNAMODB_ENDPOINT_URL`, `AWS_REGION`, `PORT_OFFSET` (or `DJANGO_PORT` / `DYNAMODB_LOCAL_PORT`), optional `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (dummy for DynamoDB Local). Django and the runner read the same vars; switching to real AWS is changing env (or unsetting `DYNAMODB_ENDPOINT_URL`).
- **Tables:** Script or Django management command that creates the same `checks` and `results` tables locally (same keys/GSI as Terraform). One command to bootstrap local tables.

**Optional:** How to run the Lambda handler locally (e.g. `python -c "from lambda.handler import handler; handler({}, None)"`) against DynamoDB Local for one-off invocations.

**Summary:** One DynamoDB endpoint env var, DynamoDB Local + Django + local runner, same `uptime_checks` code path. Ports and wiring are env-driven so multiple per-worktree stacks can run side by side; one script brings up the stack so agents (and Conductor) get a consistent, documented setup. Production = same code, different endpoint and real Lambda on EventBridge.

---

## 5. Auth Abstraction & Error Handling

**Auth**

- **Django auth** for v1: username/password (and/or email); `User`, `Organization`, `OrganizationMembership` in Django DB. Session stores current `organization_id`; all DynamoDB access is scoped by that `tenant_id`.
- **AuthBackend abstraction:** Auth is behind a small interface (e.g. `AuthBackend` with `authenticate(request)`, `get_user(id)`). Default implementation uses Django's built-in auth; later an adapter can call an OAuth/OIDC provider without changing callers. No SSO implementation in v1—only the abstraction and the Django implementation.

**Error handling**

- **Check execution:** Timeouts and connection errors yield a result record with `status=down`, `error_message` set. No retries in v1 (one attempt per check per minute). Lambda and local runner catch exceptions per check so one failure does not abort the batch.
- **Django ↔ DynamoDB:** On boto3 errors (throttling, service errors), return 5xx or a user-friendly message; optionally log and surface "temporary error, retry" in the UI.
- **Lambda:** Log errors and failed check IDs; consider CloudWatch alarms on Lambda errors or DLQ if added later. Not required for minimal v1.

**Testing**

- **Unit tests** for `uptime_checks.run_http_check` (e.g. mock HTTP server returning 200, 5xx, timeout).
- **Integration tests** for Django checks/results APIs against DynamoDB Local (or a test table).
- **Local runner:** Manual or scripted run against DynamoDB Local to confirm the same code path as Lambda.

---

## 6. Decisions Summary

| Topic | Decision |
|-------|----------|
| Repos | Application in new repo `uptime`; infra in a separate Terraform repo (sandbox AWS account) |
| Architecture | Single Lambda, EventBridge every 1 min, DynamoDB for checks + results |
| Concurrency | Option 1: single Lambda with internal parallelism (asyncio + aiohttp); target e.g. 5k checks in ~30s |
| Data store | Checks and results in DynamoDB; users/orgs in Django DB (SQLite/Postgres) |
| Multi-tenant | `tenant_id` (org id) in all DynamoDB keys/GSIs; Django scopes all access by current org |
| Auth | Django auth v1; AuthBackend abstraction for future SSO |
| Local dev | DynamoDB Local + env-driven ports + single "dev-stack" script; per-worktree stacks (Conductor-friendly) |
| Scale-out path | Document Option 2 (dispatcher + per-check Lambdas) for future use |
