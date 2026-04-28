# Plans

Implementation plans and design docs are grouped by **work** (initiative). Each folder contains everything needed to run or understand that piece of work.

## Directory layout

| Folder | Work | Contents |
|--------|------|----------|
| **1-uptime-monitoring/** | Core product: Django dashboard, Lambda, DynamoDB, local dev | `design.md`, `implementation-plan.md`, `mayor-agent-prompt.md` |
| **2-ui-landing/** | UI design system (Tailwind), checks/results UI, landing page, make test | `design.md`, `implementation-plan.md`, `mayor-agent-prompt.md` |
| **3-security/** | Security hardening: login redirect, SECRET_KEY/ALLOWED_HOSTS, Lambda timeout parsing | `design.md`, `implementation-plan.md` |

- **design.md** — Design doc (architecture, decisions, scope).
- **implementation-plan.md** — Bite-sized tasks for agents; use the **executing-plans** skill to run it.
- **mayor-agent-prompt.md** — Prompt for a Conductor mayor agent to orchestrate 3 workers on this plan.

## Quick reference

- **1 — Core product (15 tasks):** `1-uptime-monitoring/implementation-plan.md` + `1-uptime-monitoring/mayor-agent-prompt.md`
- **2 — UI & landing (8 tasks):** `2-ui-landing/implementation-plan.md` + `2-ui-landing/mayor-agent-prompt.md`
- **3 — Security (5 tasks):** `3-security/implementation-plan.md`
