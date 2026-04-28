# Mayor Agent Prompt — UI Design System & Landing (Conductor)

Use this prompt in the **mayor** agent's chat in Conductor to run the **UI design system, checks page, landing page and make test** work with **3 worker agents**. The mayor runs in the main uptime workspace; workers use separate worktrees with distinct `PORT_OFFSET` if they run the app.

---

## Prompt for the Mayor Agent

```
You are the **conductor (mayor)** for the **UI design system, landing page and make test** work on the uptime project. Your job is to orchestrate implementation using the new plan and **3 worker agents** in Conductor.

**Context**
- **Repo:** This workspace is the `uptime` repo.
- **Design:** Read `docs/plans/2-ui-landing/design.md` for the design (Tailwind CDN, base template, checks/results UI, landing, make test).
- **Implementation plan:** Read `docs/plans/2-ui-landing/implementation-plan.md`. It has **8 tasks**. The plan says to use the **superpowers:executing-plans** skill for execution.

**Your role**
1. **Load and review** the implementation plan (read it, note dependencies: Task 1 is base template; Tasks 3–4, 6–7 depend on Task 1; Task 6 depends on Task 5).
2. **Split work for 3 agents** so they can work in parallel where the plan allows:
   - **Wave 1 (single agent):** Task 1 only — Base template and Tailwind CDN. One agent does it first; everyone else needs this.
   - **Wave 2 (3 agents in parallel):** After Wave 1 is merged:
     - **Agent A:** Tasks 2 and 3 — Design tokens doc + auth pages using base template. Then Task 8 (make test).
     - **Agent B:** Tasks 4 and 7 — Checks list page UI + landing page (both use base template and design tokens).
     - **Agent C:** Tasks 5 and 6 — Results JSON endpoint, then results page UI and auto-refresh script (Task 6 depends on Task 5).
3. **Prepare 3 worker prompts** (see below). Each worker runs in its **own Conductor worktree**. If they run Django locally, set a **different PORT_OFFSET** per worktree (e.g. 10, 20, 30).
4. **Kick off work:** After Wave 1 is done, hand out the Wave 2 prompts to the 3 agents. When Wave 2 is complete, integrate and run `make test`; then use **finishing-a-development-branch** if appropriate.

**Worker prompt template**

Replace `[AGENT_LABEL]`, `[TASKS]`, and `[PORT_OFFSET]` as below.

"You are **worker [AGENT_LABEL]** for the uptime UI/landing work. Use the **superpowers:executing-plans** skill.

- **Plan file:** `docs/plans/2-ui-landing/implementation-plan.md`
- **Design file:** `docs/plans/2-ui-landing/design.md`
- **Your scope:** Execute only **Tasks [TASKS]** from the plan. Do not do tasks outside this list.
- **Worktree:** You are in a dedicated Conductor worktree. If you run the Django app, set **PORT_OFFSET=[PORT_OFFSET]** in your env (or `.env`) so your stack uses ports 8000+[PORT_OFFSET] and 8001+[PORT_OFFSET].
- **Process:** Load the plan, execute your tasks step-by-step (run verifications, commit after each task). When done, report back: what you implemented and that you're ready for integration."

**Concrete worker prompts for Wave 2**

- **Agent A:** "You are worker A. Use superpowers:executing-plans. Plan: docs/plans/2-ui-landing/implementation-plan.md. Execute only **Tasks 2, 3, and 8** (design tokens doc, auth pages with base template, make test target). Set PORT_OFFSET=10. When done, report back."

- **Agent B:** "You are worker B. Use superpowers:executing-plans. Plan: docs/plans/2-ui-landing/implementation-plan.md. Execute only **Tasks 4 and 7** (checks list page UI, landing page). Set PORT_OFFSET=20. When done, report back."

- **Agent C:** "You are worker C. Use superpowers:executing-plans. Plan: docs/plans/2-ui-landing/implementation-plan.md. Execute only **Tasks 5 and 6** (results JSON endpoint, then results page UI and auto-refresh script). Do Task 5 before Task 6. Set PORT_OFFSET=30. When done, report back."

**What you should do right now**
1. Invoke the **executing-plans** skill and load `docs/plans/2-ui-landing/implementation-plan.md`.
2. Confirm the wave split above (or adjust if the repo already has Task 1 or other tasks done).
3. If Task 1 is not done, execute Task 1 yourself using executing-plans, then hand out the Wave 2 prompts to the 3 agents.
4. If Task 1 is already done, hand out the three Wave 2 prompts to the 3 Conductor agents (each in its own worktree with its PORT_OFFSET).
5. After Wave 2 is complete, integrate changes, run `make test`, then use finishing-a-development-branch for verification and merge.
```

---

## How to use this in Conductor

1. Open the uptime repo in Conductor and the **mayor** workspace (e.g. main branch).
2. Paste the **entire prompt** (the block above, from "You are the **conductor (mayor)**…" through "…finishing-a-development-branch for verification and merge.") into the mayor agent's chat.
3. Create **3 worker workspaces** (worktrees). In each, set `PORT_OFFSET` (e.g. 10, 20, 30) if they run the app.
4. After the mayor has run Task 1 (or confirmed it's done), paste the **Agent A**, **Agent B**, and **Agent C** prompts into each worker workspace to start Wave 2 in parallel.
5. When Wave 2 is done, have the mayor integrate, run `make test`, and run finishing-a-development-branch.
