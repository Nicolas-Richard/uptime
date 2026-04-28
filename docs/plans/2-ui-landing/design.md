# UI Design System, Checks Page, Landing Page & Make Test — Design

**Date:** 2025-03-04  
**Status:** Approved  
**Scope:** Tailwind CSS (CDN), base template and design tokens; improved checks list and results page with auto-refresh; public landing page; `make test` target.

---

## 1. Design System & Tailwind Integration

**Scope:** Introduce Tailwind CSS via CDN and a minimal, consistent base for the app and landing page.

- **Tailwind:** Load the Tailwind Play CDN script in the base template (e.g. `templates/base.html`). No Node/npm; all styling via utility classes in Django templates.
- **Base template:** One `base.html` that: (1) loads Tailwind CDN, (2) optionally a Google font (e.g. Inter) for a modern look, (3) defines a simple layout (e.g. main content area, optional top nav), (4) `{% block content %}` and `{% block title %}`. All app and landing templates extend this base.
- **Design tokens (in code):** No `tailwind.config.js`. Use Tailwind defaults: a consistent spacing scale, `rounded-lg` for cards, `shadow-sm` / `shadow` for elevation, one primary button style (e.g. `bg-blue-600 text-white px-4 py-2 rounded-lg`), status colors (e.g. green for up, red for down, gray for unknown). Document these in a short "Design system" subsection in the implementation plan or in `docs/` so future pages stay consistent.
- **Where it applies:** Auth pages (login/logout), dashboard shell (nav, layout), checks list and check detail, results page, and landing page all use this base and the same token conventions.

---

## 2. Checks Page UI & Results Auto-Refresh

**Checks list page:**
- Use Tailwind for layout: clear heading, "Add check" primary button, table or card list of checks. Each row/card: check name, URL (truncated), status badge (up/down from latest result or "—"), last check time, actions (View results, Edit, Delete). Responsive: stack on small screens if needed. Use the shared button and badge styles from Section 1.

**Check detail / results page:**
- Same base template. Show check name and URL; then "Recent results" with a table: timestamp, status (badge), status code, response time (ms), optional error message. **Auto-refresh:** A small inline script (no separate JS build) runs on this page: every 15–30 seconds it calls a JSON endpoint (e.g. `GET /checks/<id>/results/?format=json` or a dedicated API URL) that returns the same recent results. The script replaces the results table body (or a dedicated container) with the new data, keeping Tailwind classes. Show "Last updated at <time>" and optionally a brief "Updating…" state. New results appear as they land (within the polling interval).

**JSON endpoint:**
- Reuse the existing results view or add a view that returns the same result set as JSON (e.g. `JsonResponse(list_of_result_dicts)`). Ensure tenant/check ownership is enforced the same as for the HTML view.

---

## 3. Landing Page

**Purpose:** A single public page that showcases the product for unauthenticated visitors.

- **URL:** `/` (root). If the app today uses `/` for the dashboard, either move the dashboard to e.g. `/dashboard/` and put the landing at `/`, or put the landing at `/landing/` and redirect `/` to `/landing/` for anonymous users and to `/dashboard/` for logged-in users. Prefer landing at `/` for a clean first impression.
- **Content (minimal):** Hero with product name and one-line value proposition; short "Features" (e.g. HTTP monitoring, 1-minute checks, results in one place, multi-tenant); primary CTA "Sign up" or "Get started" linking to registration or login; optional secondary "Log in" for returning users. All styled with the same Tailwind base and design tokens (Section 1). No dashboard data; static or server-rendered copy only.
- **Technical:** One Django view (e.g. `LandingView`) that renders a template `landing.html` extending `base.html`. No auth required; logged-in users can still see it or be redirected to dashboard depending on product choice above.

---

## 4. Make Test

**Goal:** One command to run the full test suite so agents and developers can run tests consistently.

- **Implementation:** Add a `test` target in the repo `Makefile`. The target runs the project's test runner (e.g. `pytest`) with a defined configuration: include `tests/`, use existing `pyproject.toml` or `pytest.ini` if present, and any env (e.g. `DJANGO_SETTINGS_MODULE`) needed for Django tests. Example: `make test` → `cd src && pytest ../tests -v` (or equivalent so both `src` and `core` tests run). Document in README or `docs/local-dev.md` that `make test` runs all tests.
- **No new tests required** for this task; the target only invokes the current suite. Optional: add one trivial test to verify the Makefile target (e.g. a test that always passes) if the suite is empty in some branches.

---

## 5. Decisions Summary

| Topic | Decision |
|-------|----------|
| Tailwind | CDN (Play CDN); no npm/build |
| Base template | Single `base.html` with Tailwind, optional Inter font, blocks |
| Design tokens | Document in plan/docs; use Tailwind defaults |
| Results auto-refresh | Polling every 15–30s; JSON endpoint; inline script |
| Landing | One view at `/` or `/landing/`; static copy; same base template |
| Make test | `make test` runs pytest with correct paths and env |
