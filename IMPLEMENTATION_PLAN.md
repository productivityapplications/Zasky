# Zasky — Autonomous Implementation Plan

**Sequence is fixed:** complete operator intake → private chat round-trip foundation → backend/data/auth → core domain behavior → AI/chat integration → end-to-end verification → chat UX refinement → documentation → demo video → final regression and authorized release.

No website/frontend deployment, reference-image phase, mockup phase or visual-design skill is required because Zasky has no frontend in the MVP.

## Operating rules

- Read the whole handoff and inspect the repository/environment before changing files.
- Run one consolidated intake. Do not ask for routine approvals or repeat answered questions.
- Do not begin implementation with a critical unanswered input.
- After intake, execute phases sequentially without operator approval pauses.
- At every checkpoint: implement → test → inspect → fix → commit → update `AI_HANDOFF.md` and `docs/BUILD_LOG.md` → continue.
- Stop only for a real blocker or authorization boundary. Continue unaffected work.
- Never claim a service, test, deployment, backup or video succeeded without evidence.
- Never print, commit or place secrets in prompts, source control, logs or demo materials.

## Phase 0 — Operator intake and readiness

**Objective:** Resolve all product-specific operating inputs and verify the external platform before coding.

**Dependencies:** Operator access to Switch, Discord, VPS and OpenAI accounts as relevant.

**Tasks:**
1. Read all project documents, repository rules, existing `AGENTS.md`, current Git status and existing source without modifying anything.
2. Populate `OPERATOR_INTAKE.md` with answer/source, required status, validation evidence and authorization boundary.
3. Confirm Switch deployment URL/version, workspace, agent registration state and current protocol docs.
4. Confirm Discord server/private channel and bridge connection; record exact room ID and owner Switch participant ID.
5. Confirm OpenAI key availability, model tool-calling capability, account budget/quotas and monthly hard spend ceiling.
6. Confirm VPS, OS, persistent volume, SSH, firewall and monthly infrastructure cost ceiling.
7. Confirm owner timezone, weekly availability, fixed events, prep/commute/transition buffers, reminder times and seed plans.
8. Confirm data privacy, retention, backup destination, demo audience/data/redactions/output path and production release authority.
9. Verify a Switch test workspace/channel can be used without exposing production personal data.
10. Mark every critical item PASS/BLOCKED; optional choices use defaults in `CONFIGURATION.md`.

**Expected files:** `OPERATOR_INTAKE.md` updated; `AI_HANDOFF.md` phase 0 record; build log entry.  
**Tests/evidence:** credential presence checks without printing values; DNS/TLS reachability; Switch registration status; Discord bridge echo; VPS SSH; model capability check; budget authority recorded.  
**Acceptance:** all critical inputs pass; no secret printed; exact boundaries recorded.  
**Git checkpoint:** `docs: complete zasky operator readiness intake`.  
**Next:** Phase 1.  
**Blocker behavior:** If a critical credential/service does not exist, pause only affected integration; proceed with isolated local tests if safe. Do not invent IDs, credentials or spend authority.

## Phase 1 — Repository foundation + Switch chat shell

**Objective:** Prove Zasky can live in the selected private room through Switch.

**Tasks:**
1. Create/inspect Python project, lock dependencies and configure lint/type/test commands.
2. Establish package structure, settings validation, structured logging and safe `.env.example`.
3. Build Switch WebSocket lifecycle and required HTTP operations.
4. Implement exact room/owner/addressed-event filtering and event deduplication skeleton.
5. Implement one deterministic echo/ready response; no planner/model features yet.
6. Create Dockerfile and Compose service; non-root user, persistent data mount, health endpoints.
7. Deploy to protected test VPS if access is ready; never use production personal data.
8. Record exact host/service version/commit and room round-trip evidence.

**Expected files:** `pyproject.toml`, lockfile, `src/zasky/`, `Dockerfile`, `compose.yaml`, `.env.example`, tests, `README.md` starter.  
**DB/API/UI changes:** none beyond operational cursor/dedup state if needed; private health endpoints; Discord room remains the UI.  
**Tests:** Switch event parsing; auth/room filtering; duplicate event; WebSocket heartbeat; reconnect; `gap`; `taken_over`; health checks.  
**Acceptance:** owner sends a message to private Discord room and receives Zasky's response in that room; unauthorized sender/room receives no private data; one writer only.  
**Git checkpoint:** `feat: establish switch-connected zasky service`.  
**Next:** Phase 2.

## Phase 2 — Database, migrations, configuration and security foundation

**Objective:** Build durable state and enforce single-owner data boundaries.

**Tasks:**
1. Implement SQLAlchemy models matching `docs/DATA_MODEL.md`.
2. Create initial Alembic migration and indexes/constraints.
3. Implement owner singleton config, timezone parsing and validated settings.
4. Enforce SQLite WAL, foreign keys, busy timeout, single writer lock and persistent path.
5. Implement append-only audit log and event dedupe repository.
6. Implement encrypted backup command, retention policy and restore test.
7. Add private health/readiness and startup migration checks.
8. Implement access-control test fixtures with fake non-owner IDs.

**Expected files:** `src/zasky/storage/`, `migrations/`, config module, `ops/backup`, model tests.  
**Tests:** migrations up/down where safe; FK enforcement; unique constraints; backup/restore; wrong owner ID; missing config; database locked/failure behavior.  
**Acceptance:** all core entities persist; integrity checks pass after restore; no cross-owner access path exists.  
**Git checkpoint:** `feat: add durable domain schema and owner access boundary`.  
**Next:** Phase 3.

## Phase 3 — Core domain logic, seven tools and deterministic planner

**Objective:** Implement the product's actual rules independently of the LLM.

**Tasks:**
1. Implement the seven exact tool schemas and Pydantic validation.
2. Implement goals and monthly commitment create/update behavior.
3. Implement owner-supplied weekly placement proposal and capacity arithmetic.
4. Implement proposal lifecycle, code generation, TTL and revision conflict detection using `planning_scope_revisions`; compare/increment every affected scope atomically.
5. Implement exact approval/rejection command parser outside LLM.
6. Implement `plan_day` with week-pool-only selection, one-must/three-max rules and battery shaping.
7. Implement backplan/latest-wake calculation.
8. Implement `reconcile` with current day/week arithmetic and proposal-only behavior.
9. Implement `park_task`, resume and `complete_task`.
10. Implement read-only query and deadline-risk calculations.
11. Implement no-invented-task enforcement and fixed-event protection in domain functions.

**Expected files:** `domain/`, `planner/`, tool schema modules, unit tests, updated `docs/API.md`.  
**Tests:** every invariant from `PROJECT_SPEC.md`; property/table-driven capacity and schedule tests; stale approval; rejected/expired proposal; low-battery rules; invented task injection; fixed-event overlap.  
**Acceptance:** domain test suite proves all product invariants; seven tools only; approval parser cannot be bypassed by model output.  
**Git checkpoint:** `feat: implement planning, reconcile and approval domain`.  
**Next:** Phase 4.

## Phase 4 — AI orchestration and live chat integration

**Objective:** Make natural-language interaction reliable without giving the model authority over state.

**Tasks:**
1. Implement OpenAI Responses API adapter with configured model and strict tool schemas.
2. Add system prompt containing locked product invariants.
3. Build minimal context selector (current date/time, relevant goal/commitment/week/day state, pending proposal, bounded recent room context).
4. Add tool call loop max 5 cycles; max 2 state-changing proposal-producing intents per inbound message.
5. Enforce Pydantic validation and deterministic domain services for every call.
6. Implement transparent provider error, invalid tool output and budget-exceeded responses.
7. Track requests, token usage and spend; warning at 80%, hard stop at 100%.
8. Wire the inbound Switch event path end-to-end.

**Expected files:** `agent/`, `integrations/openai/`, prompt version, cost ledger, integration tests.  
**Tests:** intent-to-tool mapping, invalid model arguments, hallucinated IDs, prompt injection, retry safety, provider timeout, model quota, cost ceiling.  
**Acceptance:** owner can conduct month/week/day/reconcile interactions through Discord; no model path writes without an approved domain transaction; cost stop is enforced.  
**Git checkpoint:** `feat: connect zasky planning tools to responses api`.  
**Next:** Phase 5.

## Phase 5 — End-to-end functionality and security gate

**Objective:** Prove the primary experience under realistic happy and failure paths before chat polish.

**Critical E2E journeys:**
1. Owner creates a year goal with evidence.
2. Owner adds monthly commitment and deadline/consequence.
3. Owner places explicit work items into a week; capacity/slack calculated; approve proposal.
4. Owner asks for tomorrow; battery check; day plan uses only week pool; backplan shown; approve.
5. Owner reports "back, two-hour call, it's 4pm"; reconcile proposal; week feasibility evidence shown; owner approves.
6. Owner parks task with resume note, resumes it, then completes it.
7. Owner queries today/week/month/deadlines.
8. Non-owner attempts read and write; no data leaks.
9. Duplicate/replayed event and simultaneous approval do not duplicate writes.
10. Restart after disconnect and recover cursor/context safely.

**Failure-path requirements:** Switch down, model down, DB busy, stale proposal, expired proposal, fixed-event conflict, low battery, insufficient capacity, duplicate task, invalid tool payload, monthly budget reached, backup restore.

**Acceptance gate:**
- Unit and integration tests pass.
- Critical E2E tests pass in isolated test Discord/Switch workspace.
- No unresolved critical/high-severity functional or security issue.
- Data restore succeeds.
- No production credentials/data are used in preview/test.
- Evidence, test run IDs and known limitations logged.

**Git checkpoint:** `test: verify zasky critical journeys and security boundaries`.  
**Next:** Phase 6 only after the gate passes.

## Phase 6 — Chat UX refinement (adapted from generic UI phase)

**Objective:** Make Discord interactions legible, low-friction and consistent. This is not a frontend phase.

**Tasks:**
1. Refine message structure: short heading, current state, proposal code, action requested, one-line evidence.
2. Keep long plans chunked and ordered; avoid walls of text.
3. Use buttons/components only if the selected Switch/Discord path supports them reliably; textual commands remain the fallback.
4. Confirm commands are discoverable in first-run help and documented.
5. Ensure failure responses state whether any write occurred.
6. Ensure messages do not rely on color/emoji alone.
7. Test mobile Discord rendering with long and short messages.

**No `stageshow` skill:** it is a frontend UI skill and does not apply to a chat-only MVP. Do not install it unless a real UI is added later and this scope is formally changed.

**Acceptance:** owner can distinguish facts, proposals, pending approval, completed actions, risks and errors on phone; no ambiguous approval wording.  
**Git checkpoint:** `feat: refine zasky chat interaction patterns`.  
**Next:** Phase 7.

## Phase 7 — Documentation and operator completeness

**Objective:** Make setup, operations, recovery and product behavior reproducible.

**Tasks:** complete README and `docs/SETUP.md`, `CONFIGURATION.md`, `TESTING.md`, `DEPLOYMENT.md`, `TROUBLESHOOTING.md`, `OPERATOR_GUIDE.md`, `API.md`, `DATA_MODEL.md`, `DESIGN_NOTES.md` (document why no visual reference assets/UI phase applies), `REFERENCE_ASSETS.md`, `OPERATOR_INTAKE.md`, `AI_HANDOFF.md`, `docs/BUILD_LOG.md`.

**Acceptance:** a competent operator can deploy and restore from docs without asking the original implementer; all commands and ports are verified; secrets redacted.  
**Git checkpoint:** `docs: complete zasky setup and operations handbook`.  
**Next:** Phase 8.

## Phase 8 — Demo video (<=180 seconds)

**Objective:** Produce a real, reproducible short demo that proves the Switch-based recovery loop.

**Tasks:** create deterministic demo data; use an isolated Switch/Discord test environment; capture actual chat behavior via Playwright if Discord web can be controlled reliably, otherwise use an equivalent screen capture; script 90–150 seconds; check Google's free AI TTS option and terms; use a genuinely free permitted fallback if unavailable; align narration/captions; redact usernames, IDs, URLs, tokens and personal data; render and review.

**Acceptance:** final file <=180 seconds; audio/video play; narration matches visible actions; no secrets/personal data; script and production notes saved.  
**Git checkpoint:** `docs: add reviewed zasky demo and production notes`.  
**Next:** Phase 9.

## Phase 9 — Final regression, security and authorized release

**Objective:** Run the final full suite and deploy only within recorded authority.

**Tasks:** full unit/integration/E2E/security suite; dependency audit; secret scan; permissions/firewall review; backup and restore; verify Switch connection; verify cost limiter; inspect logs; verify `AI_HANDOFF.md` and build log. If production deployment is authorized, deploy and smoke-test. Otherwise stop at verified staging/test deployment and provide exact release instructions.

**Acceptance:** all release checks pass; no unauthorized production changes; current handoff and evidence accurate.  
**Git checkpoint:** `chore: complete zasky release verification`.  
**Terminal status:** `complete` or `verified-staging-awaiting-authorized-release`.

## Blocker handling

A blocked provider or optional integration must not stop unrelated work. For each blocker, record:
- Exact operation blocked.
- Redacted error/evidence and time.
- Work already completed.
- Work that can continue safely.
- Minimum operator action needed.
- Whether any state was changed.
Do not bypass access controls, invent credentials, accept unapproved charges or perform irreversible production changes.
