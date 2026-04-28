# Security & Hardening — Design

**Date:** 2025-03-05  
**Status:** Draft  
**Scope:** Address security and hardening issues from code review: login redirect, production config, Lambda parsing.

---

## 1. Issues Addressed

| Issue | Severity | Fix |
|-------|----------|-----|
| Open redirect via `next` in login | High | Validate `next` is a same-origin path (starts with `/`, not `//`) before redirecting |
| Default SECRET_KEY in production | High | Require `DJANGO_SECRET_KEY` when `DEBUG` is False; raise `ImproperlyConfigured` otherwise |
| Fixed ALLOWED_HOSTS | Medium | Read `ALLOWED_HOSTS` from env (comma-separated); default `localhost,127.0.0.1,0.0.0.0` |
| Lambda `timeout_seconds` parsing | Medium | Defensive parse with default 30s and clamp to 1–300s |

---

## 2. Environment Variables (production)

| Variable | Purpose |
|----------|---------|
| `DJANGO_SECRET_KEY` | Required when `DEBUG=False`; must be set in production |
| `DJANGO_DEBUG` | Set to `False` in production |
| `ALLOWED_HOSTS` | Comma-separated list of allowed host headers (e.g. `uptime.example.com`) |

---

## 3. Implementation

See `docs/plans/3-security/implementation-plan.md` for task-by-task steps.
