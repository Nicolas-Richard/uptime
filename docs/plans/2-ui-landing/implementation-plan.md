# UI Design System, Checks Page, Landing & Make Test — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Tailwind-based design system (CDN), improve the checks list and results page UI with auto-refreshing results, add a public landing page, and a `make test` target.

**Architecture:** Tailwind loaded via CDN in a single base template; all app and landing templates extend it. Checks and results pages get Tailwind styling and a JSON endpoint for results; results page includes an inline polling script. Landing is one Django view at `/` or `/landing/`. Makefile gets a `test` target that runs pytest.

**Tech Stack:** Django templates, Tailwind CSS (Play CDN), vanilla JS (inline), pytest. Design reference: `docs/plans/2-ui-landing/design.md`

---

## Task 1: Base template and Tailwind CDN

**Files:**
- Create: `src/templates/base.html` (or project-level template dir per existing layout)
- Modify: `src/uptime/settings.py` (add or verify `TEMPLATES[0]['DIRS']` includes project templates dir)

**Step 1:** Ensure the project has a global templates directory (e.g. `src/templates/`). If missing, create it and add it to `TEMPLATES[0]['DIRS']` in `settings.py` (e.g. `os.path.join(BASE_DIR, 'templates')` if `BASE_DIR` is `src/`, or `os.path.join(BASE_DIR, '..', 'templates')` if `BASE_DIR` is `src/uptime/`).

**Step 2:** Create `src/templates/base.html`. Include: (1) `<!DOCTYPE html>`, `<html>`, `<head>` with `<meta charset="utf-8">`, `<meta name="viewport" content="width=device-width, initial-scale=1">`, (2) Google Font link for Inter (e.g. `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap`), (3) Tailwind Play CDN script: `<script src="https://cdn.tailwindcss.com"></script>`, (4) `<body class="font-sans antialiased bg-gray-50 text-gray-900">`, (5) optional `<nav>` placeholder (e.g. for "Dashboard", "Log out") in a `{% block nav %}` or fixed structure, (6) `<main class="...">{% block content %}{% endblock %}</main>`, (7) `{% block title %}` in `<title>` so child templates set page title.

**Step 3:** Verify: create a minimal template that extends `base.html` and overrides `content` and `title`; render it from any view (e.g. login or a temporary URL). Load the page and confirm Tailwind and Inter apply (e.g. background and font change).

**Step 4:** Commit.
```bash
git add src/templates/base.html src/uptime/settings.py
git commit -m "feat(ui): add base template with Tailwind CDN and Inter font"
```

---

## Task 2: Design tokens documentation

**Files:**
- Create: `docs/design-system.md`

**Step 1:** Add a short doc listing: primary button classes (e.g. `bg-blue-600 hover:bg-blue-700 text-white font-medium px-4 py-2 rounded-lg`), secondary/outline button, status badge up (e.g. `bg-green-100 text-green-800`), status badge down (`bg-red-100 text-red-800`), card container (`bg-white rounded-lg shadow-sm border border-gray-200 p-4` or similar), table styles. One line per pattern with the exact class list to copy.

**Step 2:** Commit.
```bash
git add docs/design-system.md
git commit -m "docs: add design system token reference"
```

---

## Task 3: Auth pages use base template

**Files:**
- Modify: `src/auth/templates/auth/login.html` (or equivalent login template)
- Modify: logout or any other auth template that renders full pages

**Step 1:** Make the login template extend `base.html` and use `{% block content %}` and `{% block title %}`. Apply Tailwind for the form: container (e.g. max-w-md mx-auto mt-8), input classes (border rounded px-3 py-2), primary button from design-system.md. Keep existing form action and CSRF.

**Step 2:** If there is a separate logout or registration template, extend base and style consistently.

**Step 3:** Load login page; confirm it uses Tailwind and base layout.

**Step 4:** Commit.
```bash
git add src/auth/templates/
git commit -m "feat(ui): auth pages extend base template with Tailwind"
```

---

## Task 4: Checks list page UI

**Files:**
- Modify: `src/checks/templates/checks/check_list.html` (or the template that lists checks)
- Optionally modify: `src/checks/views.py` (ensure context includes latest status per check if not already)

**Step 1:** Make the checks list template extend `base.html`. Use Tailwind: page heading, "Add check" primary button (link to create URL), table or card list. Each row: check name, URL (truncated with `truncate` or slice), status badge (up/down from latest result; use design-system badge classes), last check time, links for View results, Edit, Delete. Use card or table classes from design-system.md. Ensure responsive behavior (e.g. overflow-x-auto for table on small screens).

**Step 2:** If the view does not provide "latest status" or "last_checked" per check, add it (e.g. one query or service call to get latest result per check_id and pass in context).

**Step 3:** Load checks list as a logged-in user; confirm layout and badges.

**Step 4:** Commit.
```bash
git add src/checks/
git commit -m "feat(ui): checks list page with Tailwind and status badges"
```

---

## Task 5: Results JSON endpoint

**Files:**
- Modify: `src/results/views.py` (add or extend view to return JSON)
- Modify: `src/results/urls.py` (if new URL needed)

**Step 1:** Add a view (or extend the existing results view) that returns recent results for a check as JSON. Same authorization as the HTML results view: resolve check by check_id, verify it belongs to the current tenant, then return the same result set (e.g. list of dicts with timestamp, status, status_code, response_time_ms, error_message). Use `JsonResponse` and ensure the URL is something like `/checks/<check_id>/results/` with `?format=json` or a separate path like `/api/checks/<check_id>/results/`. Document the URL in the template or design-system.

**Step 2:** Test: request the URL with a valid check_id and session; expect 200 and JSON array. Request with another tenant's check_id or unauthenticated; expect 403 or 404.

**Step 3:** Commit.
```bash
git add src/results/views.py src/results/urls.py
git commit -m "feat(results): JSON endpoint for recent results (polling)"
```

---

## Task 6: Results page UI and auto-refresh script

**Files:**
- Modify: `src/results/templates/results/` (the template that shows recent results for one check)

**Step 1:** Make the results template extend `base.html`. Show check name and URL at the top. "Recent results" section: a table with columns timestamp, status (badge), status code, response time (ms), error message. Give the table body (or a wrapper div) an id (e.g. `id="results-table-body"`) so the script can replace it. Add a small paragraph or span "Last updated at <time>" with id e.g. `id="last-updated"`.

**Step 2:** Add an inline `<script>` at the bottom of the template. Script: (1) function that fetches the results JSON endpoint (same URL as current page with `?format=json` or the API path), (2) on success, build rows (or HTML string) with the same Tailwind classes, (3) replace the table body (or container) innerHTML and update "Last updated at" to current time, (4) call `setInterval(yourFetchFunction, 20000)` (20 seconds) and call it once on load. Use `fetch()` and handle errors (e.g. leave table as-is on error). Ensure CSRF or session cookie is sent if required (same-origin usually sends cookies).

**Step 3:** Load the results page for a check; wait 20s or trigger a new check run; confirm the table updates without full page reload.

**Step 4:** Commit.
```bash
git add src/results/templates/
git commit -m "feat(ui): results page Tailwind + auto-refresh via polling"
```

---

## Task 7: Landing page view and template

**Files:**
- Create: `src/landing/` app (or use existing app; if minimal, a single view in an existing app is fine)
- Create: `src/landing/views.py` with `LandingView`
- Create: `src/landing/templates/landing/landing.html` (or `src/templates/landing.html` if no app)
- Modify: `src/uptime/urls.py` (wire `/` or `/landing/` to `LandingView`)
- Modify: `src/uptime/settings.py` (add `landing` to INSTALLED_APPS if new app)

**Step 1:** Create a view that renders a landing template. If you use a separate app, create `landing` app and add it to INSTALLED_APPS. View: no login required; optional—if user is authenticated, redirect to dashboard (e.g. `/dashboard/` or checks list) so logged-in users don't see landing by default.

**Step 2:** Create `landing.html` extending `base.html`. Content: hero (product name + one-line value proposition), short features list (e.g. HTTP monitoring, 1-minute checks, multi-tenant), primary CTA button "Get started" → signup or login URL, secondary "Log in" link. Use Tailwind and design-system tokens.

**Step 3:** Wire URL: either `path('', LandingView.as_view())` for `/` and move current dashboard to `path('dashboard/', ...)` and redirect logged-in `/` to dashboard, or `path('landing/', ...)` and redirect anonymous `/` to `/landing/`. Document choice in design doc or README.

**Step 4:** Load `/` (and `/landing/` if used); confirm unauthenticated users see the landing; logged-in users see dashboard if redirect is implemented.

**Step 5:** Commit.
```bash
git add src/landing/ src/uptime/urls.py src/uptime/settings.py
git commit -m "feat: add landing page with Tailwind"
```

---

## Task 8: Make test target

**Files:**
- Modify: `Makefile` (at repo root)

**Step 1:** Add target `test`. Command must run pytest so that both `tests/` (e.g. core and app tests) and any tests under `src/` are discovered. Example: `pytest tests/ src/ --tb=short -v` or `cd src && python -m pytest ../tests . -v`. Set `DJANGO_SETTINGS_MODULE` if Django tests need it (e.g. `export DJANGO_SETTINGS_MODULE=uptime.settings`). Use the same Python/env as the rest of the project (e.g. no extra activate if make is run from a venv).

**Step 2:** Run `make test` from repo root; confirm existing tests pass (or that the command runs and reports no tests / expected failures if suite is minimal).

**Step 3:** Add one line to README or `docs/local-dev.md`: "Run all tests with `make test`."

**Step 4:** Commit.
```bash
git add Makefile README.md docs/local-dev.md
git commit -m "chore: add make test target and document"
```

---

## Execution handoff

Plan complete and saved to `docs/plans/2-ui-landing/implementation-plan.md`.

**Execution options:**

1. **Subagent-driven (this session)** — Dispatch a subagent per task (or per batch), review between tasks.
2. **Parallel session** — Open a new session in the uptime worktree and use **superpowers:executing-plans** to run the plan with checkpoints.

Which approach do you prefer?
