# Uptime Monitoring Platform — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a minimal multi-tenant uptime monitoring SaaS: Django dashboard for HTTP(S) checks, one Lambda running checks every minute with asyncio, results in DynamoDB; local dev and per-worktree stacks (Conductor-friendly) with one script.

**Architecture:** Single Lambda triggered by EventBridge (rate 1 min) reads active checks from DynamoDB, runs HTTP checks in parallel via shared `core.uptime_checks`, writes results to DynamoDB. Django (modular monolith: auth, organizations, checks, results) is the only UI/API and uses boto3 to read/write the same tables, scoped by `tenant_id`. Auth/orgs in Django DB; checks/results only in DynamoDB.

**Tech Stack:** Python 3.11+, Django 5.x, boto3, aiohttp, DynamoDB Local (Docker), pytest. Infra (separate Terraform repo) out of scope in this repo.

**Design reference:** `docs/plans/1-uptime-monitoring/design.md`

---

## Phase 1: Repo bootstrap and shared check library

### Task 1: Python project and dependency layout

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt` (or use pyproject only)
- Create: `.env.example`
- Create: `README.md` (stub with “see docs/local-dev.md”)

**Step 1:** Create `pyproject.toml` with project name `uptime`, Python >=3.11, and dependencies: `django>=5.0`, `boto3`, `aiohttp`, `pytest`, `pytest-asyncio`, `pytest-django` (if needed later). Use a `[project.optional-dependencies] dev` for test deps.

**Step 2:** Create `.env.example` with:
```bash
# Local DynamoDB (DynamoDB Local)
DYNAMODB_ENDPOINT_URL=http://localhost:8001
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=local
AWS_SECRET_ACCESS_KEY=local

# Per-worktree ports (default: 0)
PORT_OFFSET=0
# Derived: Django = 8000 + PORT_OFFSET, DynamoDB Local = 8001 + PORT_OFFSET
```

**Step 3:** Create minimal `README.md` pointing to `docs/plans/1-uptime-monitoring/design.md` and `docs/local-dev.md` (to be added later).

**Step 4:** Commit.
```bash
git add pyproject.toml .env.example README.md
git commit -m "chore: add project deps and env example"
```

---

### Task 2: core.uptime_checks — failing test

**Files:**
- Create: `core/__init__.py`
- Create: `core/uptime_checks.py` (empty or stub)
- Create: `tests/__init__.py`
- Create: `tests/test_uptime_checks.py`

**Step 1:** Write the failing test for `run_http_check`. Signature: `async def run_http_check(url: str, timeout_seconds: float = 30) -> tuple[str, int | None, int, str | None]` returning `(status, status_code, response_time_ms, error_message)`. Status is `"up"` or `"down"`. Test: mock or real HTTP server returns 200 → status `"up"`, status_code 200, response_time_ms >= 0, error_message None.

**Step 2:** Run test to verify it fails.
```bash
pytest tests/test_uptime_checks.py -v
```
Expected: FAIL (e.g. `run_http_check` not defined or wrong signature).

**Step 3:** Commit.
```bash
git add core/ tests/
git commit -m "test: add failing test for run_http_check"
```

---

### Task 3: core.uptime_checks — minimal implementation

**Files:**
- Modify: `core/uptime_checks.py`

**Step 1:** Implement `async def run_http_check(url: str, timeout_seconds: float = 30) -> tuple[str, int | None, int, str]`. Use `aiohttp.ClientSession`, single GET request, measure time, return `("up", status_code, round(elapsed * 1000), "")` on success; on timeout/connection error return `("down", None, 0, str(e))`.

**Step 2:** Run test.
```bash
pytest tests/test_uptime_checks.py -v
```
Expected: PASS.

**Step 3:** Commit.
```bash
git add core/uptime_checks.py
git commit -m "feat(core): implement run_http_check"
```

---

### Task 4: core.uptime_checks — test 5xx and timeout

**Files:**
- Modify: `tests/test_uptime_checks.py`

**Step 1:** Add test: server returns 503 → status `"down"`, status_code 503, error_message empty or status indicates down. (Design: “down” on failure; you may define 5xx as “down”.)

**Step 2:** Add test: request times out → status `"down"`, status_code None, error_message non-empty. Use a mock server that sleeps or use aiohttp’s timeout.

**Step 3:** Run tests; fix implementation if needed.
```bash
pytest tests/test_uptime_checks.py -v
```

**Step 4:** Commit.
```bash
git add core/uptime_checks.py tests/test_uptime_checks.py
git commit -m "test(core): 5xx and timeout; fix run_http_check for down cases"
```

---

## Phase 2: DynamoDB tables and local bootstrap

### Task 5: DynamoDB table definitions and local create script

**Files:**
- Create: `scripts/dynamodb_tables.json` (or .py that defines table schemas)
- Create: `scripts/create_local_tables.py`

**Step 1:** Define `checks` table: PK `tenant_id` (S), SK `check_id` (S); GSI `is_active-tenant_id` with PK `is_active` (S), SK `tenant_id` (S). Attribute definitions for `name`, `url`, `is_active`, `created_at`, `updated_at`, `timeout_seconds`.

**Step 2:** Define `results` table: PK `check_id` (S), SK `timestamp` (S); GSI `tenant_id-timestamp` with PK `tenant_id` (S), SK `timestamp` (S). Attributes: `tenant_id`, `status`, `status_code`, `response_time_ms`, `error_message`.

**Step 3:** Implement `scripts/create_local_tables.py`: read `DYNAMODB_ENDPOINT_URL` from env (default for local), create boto3 client with endpoint_url, create both tables and GSI if not exist. Idempotent (describe_table first).

**Step 4:** Run against DynamoDB Local (assume Docker already running on 8001).
```bash
export DYNAMODB_ENDPOINT_URL=http://localhost:8001 AWS_REGION=us-east-1
python scripts/create_local_tables.py
```
Expected: Tables created.

**Step 5:** Commit.
```bash
git add scripts/
git commit -m "feat: add DynamoDB table definitions and local create script"
```

---

## Phase 3: Django project and auth/organizations

### Task 6: Django project skeleton

**Files:**
- Create: `src/manage.py`
- Create: `src/uptime/__init__.py`
- Create: `src/uptime/settings.py`
- Create: `src/uptime/urls.py`
- Create: `src/uptime/wsgi.py`
- Create: `src/uptime/asgi.py`

**Step 1:** Create Django project under `src/` (e.g. `django-admin startproject uptime src` or manual). In `settings.py`: use `os.environ.get("DJANGO_SETTINGS_MODULE")`, `SECRET_KEY` from env, `DEBUG=True` from env, `ALLOWED_HOSTS` include `localhost` and `127.0.0.1`. Database: SQLite `db.sqlite3` in project root for dev. Install `django` and run `python manage.py check`.

**Step 2:** Add env for DynamoDB: read `DYNAMODB_ENDPOINT_URL`, `AWS_REGION` in settings (or a small `src/uptime/config.py`) so other modules can use them. Don’t create tables yet.

**Step 3:** Commit.
```bash
git add src/
git commit -m "chore: add Django project skeleton and DynamoDB env"
```

---

### Task 7: Port and DynamoDB endpoint from env

**Files:**
- Create: `src/uptime/config.py`
- Modify: `src/uptime/settings.py`

**Step 1:** In `config.py`, define: `PORT_OFFSET = int(os.environ.get("PORT_OFFSET", "0"))`, `DJANGO_PORT = 8000 + PORT_OFFSET`, `DYNAMODB_LOCAL_PORT = 8001 + PORT_OFFSET`. Build `DYNAMODB_ENDPOINT_URL` from env; if not set, use `http://localhost:{DYNAMODB_LOCAL_PORT}` when `PORT_OFFSET` is used (or require explicit `DYNAMODB_ENDPOINT_URL` for local). Document in code.

**Step 2:** In `settings.py`, use `config.DYNAMODB_ENDPOINT_URL` and ensure runserver can bind to `config.DJANGO_PORT` (e.g. document “run with `python manage.py runserver 0.0.0.0:8000` or use PORT_OFFSET”).

**Step 3:** Update `.env.example` to show `PORT_OFFSET` and that Django is 8000+PORT_OFFSET, DynamoDB Local 8001+PORT_OFFSET.

**Step 4:** Commit.
```bash
git add src/uptime/config.py src/uptime/settings.py .env.example
git commit -m "feat: port and DynamoDB endpoint from env for per-worktree stacks"
```

---

### Task 8: Auth app and AuthBackend abstraction

**Files:**
- Create: `src/auth/__init__.py`
- Create: `src/auth/backends.py`
- Create: `src/auth/views.py`
- Create: `src/auth/urls.py`
- Create: `src/auth/templates/auth/login.html` (minimal)

**Step 1:** Define `AuthBackend` protocol/ABC in `auth/backends.py`: `authenticate(request) -> User | None`, `get_user(user_id) -> User | None`. Implement `DjangoAuthBackend` that uses Django’s `authenticate()` and `User.objects.get` so existing login works through this interface.

**Step 2:** In `auth/views.py`, login view that uses the backend; logout view. Use Django’s `LoginView`/`LogoutView` or thin wrappers that call the backend. Template: simple form with username/password.

**Step 3:** Add `auth` to `INSTALLED_APPS`, include `auth.urls` in root `urls.py`. Run `manage.py check`.

**Step 4:** Commit.
```bash
git add src/auth/ src/uptime/settings.py src/uptime/urls.py
git commit -m "feat(auth): add AuthBackend abstraction and Django login/logout"
```

---

### Task 9: Organizations app (tenant model)

**Files:**
- Create: `src/organizations/__init__.py`
- Create: `src/organizations/models.py`
- Create: `src/organizations/admin.py`
- Create: `src/organizations/views.py` (optional: “switch org” or list orgs)

**Step 1:** Create models: `Organization` (id UUID, name, slug, created_at), `OrganizationMembership` (user FK, organization FK, role CharField, unique_together (user, organization)). Add `Organization` and `OrganizationMembership` to `organizations/models.py`.

**Step 2:** Migration.
```bash
cd src && python manage.py makemigrations organizations && python manage.py migrate
```

**Step 3:** Middleware or context processor: set `request.current_organization` from session (e.g. `organization_id`). Helper `get_current_tenant_id(request)` returning `str(organization.id)` for use in DynamoDB calls.

**Step 4:** Register in admin; add `organizations` to `INSTALLED_APPS`. Commit.
```bash
git add src/organizations/ src/uptime/settings.py
git commit -m "feat(organizations): add Organization and Membership; current tenant from session"
```

---

## Phase 4: Checks and results (Django + DynamoDB)

### Task 10: Checks service layer (boto3)

**Files:**
- Create: `src/checks/__init__.py`
- Create: `src/checks/services.py`
- Create: `src/checks/views.py`
- Create: `src/checks/urls.py`
- Create: `src/checks/templates/checks/` (list, create, edit, delete)

**Step 1:** In `checks/services.py`, implement: `list_checks(tenant_id)`, `get_check(tenant_id, check_id)`, `create_check(tenant_id, name, url, timeout_seconds=30)`, `update_check(tenant_id, check_id, **kwargs)`, `delete_check(tenant_id, check_id)`. Use boto3 DynamoDB client with `endpoint_url` from config; table name from settings (e.g. `checks`). Generate `check_id` (uuid4) on create; set `created_at`, `updated_at`, `is_active=True`.

**Step 2:** Write integration test (optional, can use DynamoDB Local): create check, get check, list checks, update, delete. Skip if no DynamoDB Local in CI; document “run with DynamoDB Local”.

**Step 3:** Views: list checks for current tenant; create form; edit form; delete confirmation. All use `get_current_tenant_id(request)` and pass to service. Templates: table of checks with links to edit, “Add check” button.

**Step 4:** Add `checks` to `INSTALLED_APPS`, include `checks.urls` under `/checks/`. Require login; require membership in an organization (redirect to “create or join org” if none). Commit.
```bash
git add src/checks/
git commit -m "feat(checks): DynamoDB service layer and CRUD UI for checks"
```

---

### Task 11: Results service layer and UI

**Files:**
- Create: `src/results/__init__.py`
- Create: `src/results/services.py`
- Create: `src/results/views.py`
- Create: `src/results/urls.py`
- Create: `src/results/templates/results/` (e.g. recent for a check)

**Step 1:** In `results/services.py`, implement: `get_recent_results(tenant_id, check_id, limit=50)`. Query DynamoDB `results` table by `check_id`, SK descending, limit; verify `tenant_id` matches (or filter). Return list of dicts with `timestamp`, `status`, `status_code`, `response_time_ms`, `error_message`.

**Step 2:** View: “Recent results for check X”. URL like `/checks/<check_id>/results/`. Ensure check belongs to current tenant (fetch check first via checks service). Render table of results.

**Step 3:** Add `results` to `INSTALLED_APPS`, include `results.urls`. Link from check list/detail to “View results”. Commit.
```bash
git add src/results/ src/checks/ (if links added)
git commit -m "feat(results): results service and UI for recent check results"
```

---

## Phase 5: Lambda and local runner

### Task 12: Lambda handler

**Files:**
- Create: `lambda/__init__.py`
- Create: `lambda/handler.py`
- Create: `lambda/requirements.txt` or use shared `core` (package `core` with handler in deployment)

**Step 1:** In `handler.py`, define `handler(event, context)`. (1) Create boto3 DynamoDB client (endpoint from env for local; no endpoint in prod). (2) Scan or query `checks` table for active checks — use GSI `is_active-tenant_id` with `is_active = "true"` (or query per tenant and filter). (3) For each check, call `asyncio.run(run_checks_batch(checks))` where `run_checks_batch` uses `core.uptime_checks.run_http_check` in parallel (asyncio.gather). (4) Batch-write results to `results` table (PutItem per result: check_id, timestamp, tenant_id, status, status_code, response_time_ms, error_message). Use asyncio loop in handler; ensure Lambda has network access.

**Step 2:** Add small `run_checks_batch(checks: list[dict]) -> list[dict]` that returns list of result dicts; handler then does batch_write. Handle per-check exceptions so one failure doesn’t abort the batch.

**Step 3:** Test locally: set `DYNAMODB_ENDPOINT_URL` to DynamoDB Local, create one check, run `python -c "from lambda.handler import handler; handler({}, None)"`. Verify one result row in `results` table.

**Step 4:** Commit.
```bash
git add lambda/
git commit -m "feat(lambda): handler to run all active checks and write results to DynamoDB"
```

---

### Task 13: Local runner script

**Files:**
- Create: `scripts/run_checks_local.py`

**Step 1:** Script: in a loop (e.g. `while True`), (1) create DynamoDB client from env (`DYNAMODB_ENDPOINT_URL`), (2) load all active checks (same query as Lambda), (3) call same `run_checks_batch` logic (or import from lambda module), (4) batch-write results, (5) `time.sleep(60)`. Use same table names as Lambda. Log “Ran N checks” each iteration.

**Step 2:** Run manually against DynamoDB Local with one check; verify results appear. Document in README: “Run DynamoDB Local, create tables, add a check via Django, then `python scripts/run_checks_local.py`.”

**Step 3:** Commit.
```bash
git add scripts/run_checks_local.py
git commit -m "feat: local runner script for dev (no Lambda)"
```

---

## Phase 6: Dev stack and docs

### Task 14: Single “dev-stack” script and Makefile

**Files:**
- Create: `scripts/dev-stack.sh`
- Create: `Makefile`

**Step 1:** `scripts/dev-stack.sh`: (1) Read `PORT_OFFSET` from env (default 0). (2) Start DynamoDB Local in Docker on port `8001 + PORT_OFFSET` if not already running (e.g. `docker run -d -p 8001:8000 amazon/dynamodb-local` — or map host port to 8001+PORT_OFFSET). (3) Run `scripts/create_local_tables.py` with `DYNAMODB_ENDPOINT_URL=http://localhost:8001` (or 8001+PORT_OFFSET). (4) Print: “DynamoDB Local on port X. Run Django: python src/manage.py runserver 0.0.0.0:8000” (or 8000+PORT_OFFSET). Optionally start Django and runner in background or in separate terminals; document “run in two other terminals: make run-django, make run-runner”.

**Step 2:** Makefile targets: `dev-stack` (run dev-stack.sh), `run-django` (cd src && python manage.py runserver 0.0.0.0:$(DJANGO_PORT)), `run-runner` (python scripts/run_checks_local.py), `create-tables` (python scripts/create_local_tables.py). Use PORT_OFFSET from env.

**Step 3:** Test: `PORT_OFFSET=10 make dev-stack` (or equivalent); verify DynamoDB Local and tables; then run Django and runner manually. Commit.
```bash
git add scripts/dev-stack.sh Makefile
git commit -m "feat: dev-stack script and Makefile for per-worktree local dev"
```

---

### Task 15: docs/local-dev.md and README

**Files:**
- Create: `docs/local-dev.md`
- Modify: `README.md`

**Step 1:** Write `docs/local-dev.md`: (1) Prereqs: Python 3.11+, Docker. (2) Clone repo, copy `.env.example` to `.env`, set `PORT_OFFSET` if using a dedicated worktree (e.g. 10 for ports 8010/8011). (3) Run `make dev-stack` (or `./scripts/dev-stack.sh`). (4) In another terminal: migrations `cd src && python manage.py migrate`, create superuser, run `make run-django`. (5) In a third terminal: `make run-runner`. (6) Open Django at http://localhost:8000 (or 8000+PORT_OFFSET); create org, add check, see results after runner cycle. (7) For Conductor: set `PORT_OFFSET` per workspace so each agent has its own ports.

**Step 2:** Update `README.md`: project description, link to design doc, link to `docs/local-dev.md`, list of main components (Django, Lambda, core.uptime_checks, scripts).

**Step 3:** Commit.
```bash
git add docs/local-dev.md README.md
git commit -m "docs: local-dev and README for Conductor/per-worktree setup"
```

---

## Execution handoff

Plan complete and saved to `docs/plans/1-uptime-monitoring/implementation-plan.md`.

**Two execution options:**

1. **Subagent-driven (this session)** — I dispatch a fresh subagent per task (or per phase), review between tasks, fast iteration.
2. **Parallel session (separate)** — Open a new session in the uptime worktree and use **superpowers:executing-plans** for batch execution with checkpoints.

Which approach do you prefer?
