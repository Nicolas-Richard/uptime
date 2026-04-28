# Security & Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix security issues and harden configuration identified in code review: open redirect in login, production SECRET_KEY/ALLOWED_HOSTS, and defensive parsing in the Lambda handler.

**Architecture:** Auth login will validate the `next` redirect URL so only same-origin paths are allowed. Settings will require SECRET_KEY when not in DEBUG and make ALLOWED_HOSTS configurable via env. Lambda handler will parse `timeout_seconds` defensively with a safe default and clamp.

**Tech Stack:** Django (auth, settings), Python (Lambda handler). Design reference: `docs/plans/3-security/design.md`

---

## Task 1: Fix open redirect in login

**Files:**
- Modify: `src/auth/views.py` (login_view redirect logic)
- Test: `tests/test_auth_redirect.py` (create)

**Step 1: Write the failing test**

Create `tests/test_auth_redirect.py`:

```python
"""Tests for login redirect safety (no open redirect)."""
import pytest
from django.test import Client
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_login_redirect_rejects_absolute_url():
    """next=https://evil.com in URL must not redirect to evil.com."""
    User.objects.create_user(username="u", password="p")
    client = Client()
    response = client.post(
        "/auth/login/?next=https://evil.com",
        {"username": "u", "password": "p"},
        follow=False,
    )
    assert response.status_code == 302
    assert response["Location"] != "https://evil.com"
    assert response["Location"].startswith("/")


@pytest.mark.django_db
def test_login_redirect_allows_relative_path():
    """next=/checks/ in URL must redirect to /checks/ after login."""
    User.objects.create_user(username="u", password="p")
    client = Client()
    response = client.post(
        "/auth/login/?next=/checks/",
        {"username": "u", "password": "p"},
        follow=False,
    )
    assert response.status_code == 302
    assert response["Location"] == "/checks/"
```

**Step 2: Run test to verify it fails (open redirect currently allowed)**

Run: `cd src && DJANGO_SETTINGS_MODULE=uptime.settings python -m pytest ../tests/test_auth_redirect.py -v`  
Expected: First test may pass (if redirect goes to /) or fail; second should pass. After implementation, both must pass with redirect validation.

**Step 3: Implement safe redirect helper and use it in login_view**

In `src/auth/views.py`:

- Add a helper that returns a safe redirect URL: only allow `next` if it is a non-empty string that starts with `/` and does not start with `//` (no protocol-relative or absolute URLs). Otherwise return `"/"` or `"/checks/"`.
- In `login_view`, after successful auth, set `redirect_to = get_safe_redirect_url(request.GET.get("next"))` and `return redirect(redirect_to)`. (Keep using `request.GET` for `next` so redirect target comes from the URL, e.g. `/auth/login/?next=/checks/`.)

Example helper:

```python
def get_safe_redirect_url(next_url: str | None) -> str:
    """Return next_url if it is a safe same-origin path, else default."""
    if not next_url or not isinstance(next_url, str):
        return "/"
    next_url = next_url.strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return "/"
```

**Step 4: Run tests**

Run: `cd src && DJANGO_SETTINGS_MODULE=uptime.settings python -m pytest ../tests/test_auth_redirect.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/auth/views.py tests/test_auth_redirect.py
git commit -m "fix(auth): prevent open redirect via next parameter"
```

---

## Task 2: Require SECRET_KEY in production

**Files:**
- Modify: `src/uptime/settings.py`

**Step 1: Add production SECRET_KEY check**

In `src/uptime/settings.py`, after the existing `SECRET_KEY = os.environ.get(...)` block:

- If `DEBUG` is False and `SECRET_KEY` is the default value `"django-insecure-dev-only-change-in-production"`, raise `ImproperlyConfigured` with a message like "Set DJANGO_SECRET_KEY in production."
- Use: `from django.core.exceptions import ImproperlyConfigured` and a conditional after both `DEBUG` and `SECRET_KEY` are defined.

Example:

```python
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

if not DEBUG and SECRET_KEY == "django-insecure-dev-only-change-in-production":
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in production.")
```

(Ensure `ImproperlyConfigured` is imported.)

**Step 2: Verify**

Run: `cd src && DJANGO_DEBUG=False python -c "from uptime.settings import SECRET_KEY; print('ok')"`  
Expected: ImproperlyConfigured.  
Run: `cd src && DJANGO_DEBUG=False DJANGO_SECRET_KEY=test-key python -c "from uptime.settings import SECRET_KEY; print('ok')"`  
Expected: ok.

**Step 3: Commit**

```bash
git add src/uptime/settings.py
git commit -m "fix(settings): require DJANGO_SECRET_KEY when DEBUG is False"
```

---

## Task 3: Configurable ALLOWED_HOSTS

**Files:**
- Modify: `src/uptime/settings.py`
- Modify: `.env.example` (document ALLOWED_HOSTS)

**Step 1: Read ALLOWED_HOSTS from env**

In `src/uptime/settings.py`, replace the fixed `ALLOWED_HOSTS = ["localhost", ...]` with:

- `ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").strip().split(",")` (strip each element if you want to allow `"localhost, example.com"`), or split and strip: `[h.strip() for h in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")]`.

**Step 2: Update .env.example**

Add a line:

```
# Comma-separated list for production (e.g. uptime.example.com)
# ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
```

**Step 3: Verify**

Run: `cd src && python -c "from uptime.settings import ALLOWED_HOSTS; print(ALLOWED_HOSTS)"`  
Expected: default list.  
Run: `cd src && ALLOWED_HOSTS=app.example.com python -c "from uptime.settings import ALLOWED_HOSTS; print(ALLOWED_HOSTS)"`  
Expected: `['app.example.com']` (or with strip: `['app.example.com']`).

**Step 4: Commit**

```bash
git add src/uptime/settings.py .env.example
git commit -m "feat(settings): configurable ALLOWED_HOSTS via env"
```

---

## Task 4: Defensive timeout_seconds parsing in Lambda

**Files:**
- Modify: `lambda_handler/handler.py` (_load_active_checks or helper that builds check dict)

**Step 1: Add a helper to parse timeout_seconds safely**

In `lambda_handler/handler.py`, add:

```python
def _parse_timeout_seconds(item: dict) -> float:
    """Parse timeout_seconds from DynamoDB item; default 30, clamp to 1-300."""
    raw = item.get("timeout_seconds")
    if not raw:
        return 30.0
    val = raw.get("N") if isinstance(raw, dict) else None
    if val is None:
        return 30.0
    try:
        secs = float(val)
    except (TypeError, ValueError):
        return 30.0
    return max(1.0, min(300.0, secs))
```

**Step 2: Use it when building check dicts in _load_active_checks**

Replace the current line that sets `"timeout_seconds": float(item.get("timeout_seconds", {}).get("N", "30"))` with:

`"timeout_seconds": _parse_timeout_seconds(item)`

(Or inline the logic once if you prefer not to add a helper.)

**Step 3: Verify**

Run a quick local test: from project root, with DynamoDB Local and a check item that has no `timeout_seconds`, or `timeout_seconds` as N "30" or invalid; ensure the handler runs and uses 30 or clamped value. Optionally add a unit test in `tests/test_lambda_handler.py` that mocks items and asserts `_parse_timeout_seconds` returns expected values (e.g. missing → 30, "45" → 45, "400" → 300, "0" → 1).

**Step 4: Commit**

```bash
git add lambda_handler/handler.py
git commit -m "fix(lambda): defensive timeout_seconds parsing and clamp 1-300s"
```

---

## Task 5: Document security configuration

**Files:**
- Create: `docs/plans/3-security/design.md` (short)
- Modify: `docs/local-dev.md` or `README.md` (one line each for SECRET_KEY and ALLOWED_HOSTS in production)

**Step 1: Add design.md**

Create `docs/plans/3-security/design.md` with a short summary: fixes applied (open redirect, SECRET_KEY in production, ALLOWED_HOSTS from env, Lambda timeout parsing), and a table of env vars: `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `DJANGO_DEBUG`.

**Step 2: Update local-dev or README**

In `docs/local-dev.md` (or README), add under production/deployment: "Set `DJANGO_SECRET_KEY` and `ALLOWED_HOSTS` (comma-separated) when deploying; leave `DJANGO_DEBUG=False`."

**Step 3: Commit**

```bash
git add docs/plans/3-security/design.md docs/local-dev.md README.md
git commit -m "docs: security configuration and 3-security plan summary"
```

---

## Execution handoff

Plan complete and saved to `docs/plans/3-security/implementation-plan.md`.

**Execution options:**

1. **Subagent-driven (this session)** — Dispatch a fresh subagent per task, review between tasks.
2. **Parallel session (separate)** — Open a new session in the uptime worktree and use **superpowers:executing-plans** to run the plan with checkpoints.

Which approach do you prefer?
