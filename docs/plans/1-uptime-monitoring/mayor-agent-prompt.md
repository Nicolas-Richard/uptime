# Mayor Agent Prompt — Conductor Orchestration (3 Agents)

Copy the block below into the **mayor** agent’s chat in Conductor (the one that will coordinate the project). This agent should run in the **main** uptime workspace (or the first worktree you use for coordination).

---

## Prompt for the Mayor Agent

```
You are the **conductor (mayor)** of the uptime monitoring project. Your job is to orchestrate implementation using the existing plan and **3 worker agents** in Conductor.

**Context**
- **Repo:** This workspace is the `uptime` repo (modular monolith: Django dashboard, Lambda, DynamoDB).
- **Design:** Read `docs/plans/1-uptime-monitoring/design.md` for architecture, data model, and local dev (including per-worktree PORT_OFFSET).
- **Implementation plan:** Read `docs/plans/1-uptime-monitoring/implementation-plan.md`. It has 15 tasks in 6 phases. The plan says to use the **superpowers:executing-plans** skill for execution.

**Your role**
1. **Load and review** the implementation plan (as in executing-plans: read the plan, note dependencies between phases).
2. **Split work for 3 agents** so they can work in parallel where the plan allows, and in sequence where there are dependencies. Suggested split:
   - **Wave 1 (single agent):** Phase 1 — Tasks 1–4 (repo bootstrap + `core.uptime_checks`). This is the foundation; one agent does it first.
   - **Wave 2 (3 agents in parallel):** After Wave 1 is done and merged:
     - **Agent A:** Phase 2 — Task 5 (DynamoDB table definitions + `scripts/create_local_tables.py`).
     - **Agent B:** Phase 3 — Tasks 6–9 (Django project, config, auth, organizations).
     - **Agent C:** Phase 5 — Tasks 12–13 (Lambda handler + local runner script). They can use the table schema from the plan.
   - **Wave 3 (after Wave 2):** Phase 4 — Tasks 10–11 (checks + results UI) and Phase 6 — Tasks 14–15 (dev-stack script, Makefile, docs). Assign between the 3 agents (e.g. one does Phase 4, one does Phase 6, one does integration or the other phase).
3. **Prepare 3 worker prompts** (see below). Each worker will run in its **own Conductor worktree**. Each worktree must use a **different PORT_OFFSET** (e.g. 10, 20, 30) so local stacks don’t conflict.
4. **Kick off work** by giving each of the 3 agents one of the worker prompts in their Conductor workspace. After each wave, have agents commit and merge (or you integrate), then hand out the next wave’s prompts.

**Worker prompt template (give each agent a version of this)**

- Replace `[WAVE]`, `[TASKS]`, `[AGENT_LABEL]`, and `[PORT_OFFSET]` with the wave number, task list, agent name (A/B/C), and a unique port offset (e.g. 10, 20, 30).

"You are **worker [AGENT_LABEL]** for the uptime project. Use the **superpowers:executing-plans** skill.

- **Plan file:** `docs/plans/1-uptime-monitoring/implementation-plan.md`
- **Design file:** `docs/plans/1-uptime-monitoring/design.md`
- **Your scope:** [WAVE] — execute only **Tasks [TASKS]** from the plan. Do not do tasks outside this list.
- **Worktree:** You are in a dedicated Conductor worktree. Set **PORT_OFFSET=[PORT_OFFSET]** in your env (or `.env`) so your Django and DynamoDB Local use ports 8000+[PORT_OFFSET] and 8001+[PORT_OFFSET]. This avoids conflicts with other agents.
- **Process:** Load the plan, execute your tasks step-by-step as in executing-plans (run verifications, commit after each task). When your tasks are done, report back: what you implemented and that you’re ready for the next wave or for integration."

**Concrete worker prompts for Wave 2 (after Wave 1 is done)**

- **Agent A:** "You are worker A. Use superpowers:executing-plans. Plan: docs/plans/1-uptime-monitoring/implementation-plan.md. Execute only **Task 5** (Phase 2: DynamoDB table definitions and create_local_tables.py). Set PORT_OFFSET=10. When done, report back."
- **Agent B:** "You are worker B. Use superpowers:executing-plans. Plan: docs/plans/1-uptime-monitoring/implementation-plan.md. Execute only **Tasks 6, 7, 8, 9** (Phase 3: Django project, config, auth, organizations). Set PORT_OFFSET=20. When done, report back."
- **Agent C:** "You are worker C. Use superpowers:executing-plans. Plan: docs/plans/1-uptime-monitoring/implementation-plan.md. Execute only **Tasks 12, 13** (Phase 5: Lambda handler, local runner). Table names/schema are in the plan. Set PORT_OFFSET=30. When done, report back."

**What you should do right now**
1. Invoke the **executing-plans** skill and load the implementation plan.
2. Confirm the wave split above (or adjust if the plan or repo state suggests otherwise).
3. If Wave 1 is not yet done, execute Phase 1 (Tasks 1–4) yourself using executing-plans, then hand out the Wave 2 prompts to the 3 agents.
4. If Wave 1 is already done, hand out the three Wave 2 prompts to the 3 Conductor agents (each in its own worktree with its PORT_OFFSET).
5. After Wave 2 is complete, assign Wave 3 (Phase 4 and Phase 6) to the 3 agents, then run finishing-a-development-branch once everything is integrated.
```

---

## How to use this in Conductor

1. Open Conductor and add the uptime repo (if not already added).
2. Open or create a workspace for the **mayor** agent (e.g. main branch or primary worktree).
3. Paste the **entire prompt** (the block above, from "You are the **conductor (mayor)**…" through "…finishing-a-development-branch once everything is integrated.") into the mayor agent’s chat.
4. Create **3 separate workspaces** (worktrees) for the 3 workers. In each, set the chosen `PORT_OFFSET` in the environment or `.env`.
5. After the mayor has run Wave 1 (or confirmed it’s done), paste the **Agent A**, **Agent B**, and **Agent C** prompts into each of the 3 worker workspaces to start Wave 2 in parallel.
6. When Wave 2 is done, have the mayor assign Wave 3 (Phase 4 + Phase 6) and then run the finishing-a-development-branch skill for final verification and merge.
