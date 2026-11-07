# Zasky — Complete Implementation-Ready Project Blueprint

**Blueprint version:** 1.0  
**Prepared:** 2026-11-05  
**Implementation status:** Not started  
**Purpose:** Source-of-truth package for an AI coding agent that will implement Zasky without redesigning the product.

> **Zasky doesn't give me discipline. It makes coming back cheap.**

This master blueprint follows the requested 30-part output order. The linked source documents in this package contain the full schemas, acceptance criteria, API contracts, security controls and implementation instructions. When there is a conflict, `PROJECT_SPEC.md` defines product behavior, `ARCHITECTURE.md` defines the fixed technical design, and `AGENTS.md` defines coding-agent operating rules.

---

## 1. Product definition

**Product name:** Zasky.

**One-line description:** A personal task-manager agent that lives in the owner's chat, holds a plan from year goals down to today's tasks, and rebuilds a realistic plan when the day goes sideways.

**Problem:** Calls run long, the owner gets distracted, goes out, feels unwell, loses power/internet, has laptop issues or wakes late. The day breaks; the owner loses the thread, panics, abandons the plan and stops trusting deadlines. Reconstructing what matters is too expensive.

**Target user:** One owner/operator in the MVP. The "team" is the owner + Zasky + future-you; the private chat room is the shared workspace.

**Core value:** Make recovery a one-message interaction instead of a fresh planning project.

**Differentiator:** The `reconcile` loop. Zasky reads the approved day/week plan, accepts what happened and the current time, proposes the rest-of-day recovery, and shows whether the week still holds.

**Primary use case:** "Back. A two-hour call ran over; it's 4pm." Zasky proposes what to keep, move or park using only existing approved week tasks and shows the week arithmetic.

**Secondary use cases:** Year/month/week planning, daily plan/backplan, task park/resume/complete, deadline risk, morning/evening prompts and read-only status queries.

**Explicit non-goals:** No website, app, dashboard, calendar replacement, public SaaS, task generation, streaks, guilt-based coaching, arbitrary autonomous computer access, payments, email/calendar integrations or multi-user workflow in MVP.

Full definition and boundaries: `PROJECT_SPEC.md`.

## 2. MVP scope

### MUST HAVE
- Private Discord channel connected through Switch.
- Exact owner/room allow-list and one active agent writer.
- Cloud-hosted Switch + Zasky target so a dead laptop/power cut does not stop the agent.
- SQLite persistence and tested backup/restore.
- Year goals → month commitments → week placements/tasks → day plan.
- Seven domain tools only.
- Week-pool-only day plans; exactly one must when nonempty; maximum three selected tasks.
- 65% weekly capacity default, configurable only 60–70%, with slack visible.
- `reconcile` proposals and `backplan` within `plan_day`.
- Explicit owner approval before record/week/day/reconcile proposals are committed; park/complete are immediate only on explicit owner status requests.
- Park/resume, complete, query, time-zone-aware schedule and fixed-event protection.
- Basic optional idempotent reminders.
- Structured logs, audit record, tests, cost cap and safe deployment.

### SHOULD HAVE
Panic mode (one 10-minute action from existing tasks), timebox overrun prompt, actual-duration capture, deadline ledger, month goal-hours review and bulk reconcile for outages within one week.

### NICE TO HAVE
JSON export/import, second Mattermost bridge, voice transcription only after privacy/cost review.

### FUTURE
Read-only reports, calendar sync, more owners/platforms, multi-tenant hosting and admin console—only after a separate product revision.

### OUT OF SCOPE
Website/frontend/dashboard, payments, external calendar/email/contacts, general web search, shell/browser/file automation, gamification and public API.

## 3. User roles

| Role | Access |
|---|---|
| Owner/operator | The only human with permission to read or change planning data, approve proposals and configure preferences |
| Zasky agent | Reads allowed room context, invokes the seven domain tools on behalf of the verified owner and posts replies |
| Future-you | Same owner in a later session; benefits from shared room history and preserved decisions |
| Other chat participant | No access to Zasky data; request ignored or generic denial without data disclosure |
| VPS operator | Infrastructure access via SSH only; no routine product-admin UI |

Switch addressing is not the sole authorization layer. Zasky independently verifies exact opaque participant ID and room ID for every inbound action.

## 4. User flows

Full step-by-step preconditions, inputs, validations, state changes and failures are in `PROJECT_SPEC.md`. MVP journeys:

1. **Activate:** one-time Switch registration → connect private room → echo test → owner-only round trip.
2. **Year:** owner names a goal and evidence of done → Zasky validates → save.
3. **Month:** owner names concrete commitments and estimates → Zasky pressure-tests monthly capacity → owner confirms.
4. **Week:** owner names concrete work items and estimates → Zasky proposes placements and 65% budget arithmetic → owner approves.
5. **Day:** owner provides battery → Zasky selects only tasks in approved week pool → exactly one must / max three → backplan wake time → owner approves.
6. **Reconcile:** owner reports disruption/current time → Zasky proposes a revised rest-of-day/week plan → shows holds/at-risk/insufficient-data → owner approves/rejects.
7. **Park/resume:** parking requires a resume note; parked tasks are excluded until resumed.
8. **Complete:** owner identifies one task; completion is idempotent.
9. **Query:** read-only today/week/month/goals/deadlines/status.
10. **Reminders:** morning/evening message at configured local time, once per type/day, skip if outside restart grace window.

## 5. Functional requirements

The authoritative acceptance criteria are FR-01 through FR-20 in `PROJECT_SPEC.md`. Core requirements:
- Switch room round trip works; unauthorized room/sender is blocked before model invocation.
- Year goal requires testable evidence; maximum five active per year.
- Month commitments are owner-authored and optionally linked to a goal.
- Week tasks must originate from owner-provided titles; application validates title provenance and commitment link.
- Weekly capacity is calculated from owner availability, fixed events, transition buffers and configured capacity.
- Day plan can only reference active tasks in approved week pool.
- Nonempty day plan has exactly one must and no more than three selected tasks.
- Low battery yields one must + at most one short/admin task from pool.
- Backplan values use deterministic formulas and owner-provided prep/commute buffers.
- Reconcile never creates a task or moves a fixed event; a proposal is shown before mutation.
- Exact owner approval is required; fuzzy chat agreement is not approval.
- Completion, event handling and proposal approval are idempotent.
- Monthly model spend ceiling and daily request limit are enforced.

## 6. Business logic / state machines

### Planning cascade
`year_goal → month_commitment → week_placement → week_task → day_plan_item`

Goals do not generate tasks. Each step requires owner-authored information or owner approval.

### Capacity
- Calculate work availability from owner-supplied weekly availability windows.
- Subtract fixed-event overlap and transition buffers.
- `planning_budget_min = floor(available_work_min × capacity_pct / 100)`.
- Default `capacity_pct = 65`; allowed range 60–70.
- `slack_min = available_work_min - planning_budget_min`.
- Monthly budget sums availability for dates in that calendar month, subtracts fixed-event overlap/buffers, then applies the same percentage.
- If schedule data is missing, do not make a "week holds" claim.

### Task scheduling / rank
- Preserve owner-specified date and approved placements.
- If no week date is supplied, deterministic planner allocates whole tasks to the least-loaded eligible available date in the week, respecting daily planning capacity and fixed events; never split a task automatically.
- Sort candidates by commitment priority (`high`, `normal`, `low`), nearest deadline, then owner-approved placement/creation order.
- The LLM does not invent rankings or task titles. A normal daily plan selects only tasks scheduled for that date; overdue work enters through reconcile.
- In the day plan, one selected task is must and remaining selected tasks are should; at most three selected.
- `drop`/omitted tasks stay in week pool; drop is a proposal disposition, not deletion/cancellation.

### State machines
- Proposal: `draft → pending → approved | rejected | expired | stale`.
- Task: `active ↔ parked → completed`; `active|parked → cancelled` only when an approved parent commitment is cancelled; completed/cancelled tasks remain historical.
- Goal: `active | achieved | retired`.
- Commitment: `active | completed | renegotiated | cancelled`.

### Approval
`add_commitment`, `place_week`, `plan_day` and `reconcile` return pending proposals; `park_task`/`complete_task` are immediate only on explicit owner requests. A deterministic parser intercepts exact `approve ZK-XXXX` / `reject ZK-XXXX` messages before LLM use. Plain `approve`/`reject` is accepted only if exactly one pending proposal exists. Check owner, room, code, TTL and revision. Approval is transactional and idempotent. This parser is not an eighth model tool.

Detailed business rules: `PROJECT_SPEC.md`.

## 7. Data model

Detailed fields, types, defaults, constraints and indexes are in `docs/DATA_MODEL.md`.

Core entities:
- `owner_config`
- `year_goals`
- `month_commitments`
- `fixed_events`
- `week_placements`
- `week_tasks`
- `day_plans`
- `day_plan_items`
- `pending_proposals`
- `planning_scope_revisions`
- `processed_switch_events`
- `switch_connection_state`
- `reminder_dispatches`
- `audit_events`
- `model_usage_records`
- `timebox_checkins` (SHOULD HAVE)

**Important relationship refinement:** a `week_placement` links one commitment to a particular week. Each concrete `week_task` has its own `scheduled_date` within that week, so reconcile can move one task without moving every task for the commitment.

All domain data is private to the owner. Credentials are not stored in SQLite. No public data exists.

## 8. System architecture

```text
Owner phone/desktop
      ↓
Private Discord channel
      ↓
Switch Discord bridge / workspace
      ↓ WebSocket room events + HTTP operations
Single Zasky service
  ├── access gate + event dedupe + rate limit
  ├── deterministic approval parser
  ├── LLM orchestration (seven strict tools)
  ├── domain services
  ├── deterministic planner/backplan/reconcile
  ├── optional reminder scheduler
  └── structured logs/audit
      ↓                         ↓
SQLite on persistent disk    OpenAI Responses API
```

Switch is central. No direct Discord bot API inside Zasky. Switch connects the agent to the shared chat context and delivers the room events. One writer process and one room claim.

Detailed architecture, failure behavior and deployment topology: `ARCHITECTURE.md`.

## 9. Technology stack

| Layer | Fixed choice |
|---|---|
| Runtime | Python 3.12+ |
| Private health service | FastAPI + Uvicorn |
| Schemas | Pydantic 2 |
| ORM / persistence | SQLAlchemy 2 + aiosqlite |
| Database | SQLite on persistent VPS volume |
| Migrations | Alembic |
| Switch | `websockets` + `httpx` |
| AI | OpenAI Responses API + official Python SDK |
| Scheduler | `asyncio` + `zoneinfo` |
| Tests | pytest + pytest-asyncio + HTTPX |
| Packaging | Docker + Docker Compose |
| Host | One Linux VPS; one Zasky writer |
| CI | GitHub Actions if repo supports it |
| Logs | Structured JSON with redaction |

No PostgreSQL, Redis/Celery, Kubernetes, Next.js, custom frontend or direct Discord bot for MVP. Pin exact versions after repository/provider inspection. The model name is selected at intake after verifying function calling and pricing.

## 10. API specification

There is no public product API. Internal model-facing domain tools are exactly:
1. `add_commitment`
2. `place_week`
3. `plan_day`
4. `reconcile`
5. `park_task`
6. `complete_task`
7. `query`

Inputs, request examples, validation, outputs and errors: `docs/API.md`. Switch transport endpoint methods/paths and registration details are included in that document.

Private operational endpoints only:
- `GET /health/live`
- `GET /health/ready`

The seven tool schemas are strict, owner context is injected by trusted code, and domain services revalidate every mutation.

## 11. Database behavior

- SQLite WAL mode, `foreign_keys=ON`, configured busy timeout.
- One active writer process; no horizontal app scaling in MVP.
- `BEGIN IMMEDIATE` for approval/critical writes where needed.
- Proposal approval: verify owner/room/code/status/expiry/revision → validate payload/current state → apply all changes → resolve proposal → audit → commit.
- Roll back the full transaction on failure.
- Unique inbound Switch event IDs prevent replay.
- Unique `(local_date, reminder_type)` prevents duplicate reminders.
- Unique `(day_plan_id, task_id)` prevents duplicate daily task assignment.
- Use online SQLite backup or safe checkpoint-and-copy; never copy only the main `.db` while WAL is active.
- Daily encrypted backup; retain seven daily and four weekly; restore test before release and monthly.

## 12. Authentication and authorization

- Switch runtime agent API key authenticates the connection/HTTP operations; separate registration key is used once.
- Exact owner Switch participant ID and allowed room ID are checked before reading room context, calling model or touching planning data.
- Require addressed event (`payload.addressed` true).
- IDs are opaque; never authorize by display name/nickname.
- No public product login or account creation.
- Operator shell access through key-based SSH; private health port only.
- Agent cannot change owner identity/room ID from chat.
- Rotating credentials requires controlled replacement, verification and revocation of old credential.

## 13. Security architecture

Threat controls are detailed in `ARCHITECTURE.md` and `docs/EDGE_CASES.md`.

Key controls:
- Owner + room allow-list; no IDOR; no public data endpoints.
- Prompt injection defense: treat room text as untrusted; no arbitrary tools.
- Strict Pydantic tool inputs and domain checks.
- No model approval tool; exact deterministic approval parser.
- Parameterized database operations; no model SQL.
- No arbitrary URL fetching/SSRF path.
- Rate limits, message size cap, model loop cap, daily and monthly budget hard stops.
- Server-only secrets, redacted logs, encrypted backups and restrictive permissions.
- Transaction safety, event dedup, stale revision detection.
- Security gate before release; no destructive/financial/production action without exact authority.

## 14. UI/UX architecture

Zasky has **no browser UI**. The product UI is chat in the private Discord room via Switch.

UX requirements:
- Message formats optimized for mobile readability.
- Clearly label stored facts, calculated outputs, proposals, approvals, errors and risks.
- Every proposed mutation has one proposal code and one exact approval command.
- State explicitly "nothing changed yet" until approval.
- Avoid wall-of-text summaries; split long plans with stable ordering.
- No reliance on color or emoji alone.
- No guilt, streaks or unsupported motivational language.

Chat examples and content rules: `docs/DESIGN_NOTES.md`; full operator behavior: `docs/OPERATOR_GUIDE.md`.

## 15. Reference-image-led UI and skill requirements

**Not applicable to this MVP.** No frontend, website, mockup, prototype or image asset is required. No reference image has been supplied; do not pretend otherwise. Do not ask for mockups or install `npx skills add benjitaylor/skills --skill stageshow`, because it is a frontend UI skill and there is no frontend task. Instead, refine the real chat UX in Phase 6 after end-to-end functionality passes. If a frontend is later added, revise the scope/architecture first and then re-evaluate reference imagery and UI skills.

## 16. Third-party integrations

| Service | Status | Purpose |
|---|---|---|
| Switch | Required | Agent connection, room event stream/context, post messages |
| Discord bridge inside Switch | Required for preferred UX | Phone/desktop chat; Zasky does not directly integrate with Discord API |
| OpenAI Responses API | Required for natural language | Intent interpretation, seven-tool calls, conversational output |
| VPS provider | Required for resilient target deployment | Host Switch and one Zasky instance with persistent disk |
| Google AI TTS | Optional, demo only | Narration if current free access/terms/quotas are verified |

No payment provider, calendar, email, web search, separate notification service or direct Discord bot.

## 17. AI architecture

- Model handles intent and conversation; Python handles identity, permissions, time math, capacity, state, validation, approval and persistence.
- Use Responses API; Assistants API was sunset August 26, 2026. Model and function-call availability must be verified at intake. Official references: `docs/REFERENCE_SOURCES.md`.
- Provide exactly seven strict function schemas; no shell/browser/URL/SQL/file/email/payment tools.
- Context includes only relevant current plan data and bounded room history.
- Max 5 tool cycles and 2 proposal-producing writes per message.
- One retry for transient provider failures; malformed output twice → ask owner to rephrase, no write.
- Monthly spend ceiling mandatory; reserve worst-case request cost before the model call and settle on verified usage; retain unknown reservations; warning at 80%, hard stop at 100%; daily request cap also required.
- Verify provider retention/privacy and use `store=false` when supported and appropriate; never promise retention guarantees without checking current terms.
- Never allow the model to approve its own proposal or invent tasks.

## 18. Payments / financial logic

**Not applicable.** Zasky MVP does not receive, hold, transfer, refund or pay money; no billing/subscriptions/escrow/wallet. No payment provider or payment-related environment variables. Model and VPS spending is an operator infrastructure budget governed by explicit hard limits, not a product payment flow.

## 19. Admin / operations

No admin dashboard or admin user role in MVP. Operator runs the service via SSH, Docker Compose, protected config, backup/restore utilities and logs. Operational endpoints are private health probes only. Required operator actions: rotate credentials, inspect Switch connection, restore backups, configure owner/timezone/availability, review cost and authorize release. See `docs/OPERATOR_GUIDE.md`, `docs/SETUP.md`, `docs/DEPLOYMENT.md`.

## 20. Error and edge-case matrix

Full testable matrix: `docs/EDGE_CASES.md`.

Priority cases: non-owner sender, wrong room, unaddressed message, duplicate/replayed event, Switch gap/taken-over, invalid model tool payload, task invention attempt, missing availability, fixed event overlap, capacity overrun, low battery, expired/stale proposal, ambiguous approval, duplicate completion, database lock/disk full, provider outage, spend limit, duplicate reminder, backup failure, missing production authority and demo data leakage.

## 21. Test strategy

Full suites and acceptance gate: `docs/TESTING.md`.

- **Unit:** capacity, scheduling, backplan, deadline risk, states, proposal logic, week-pool-only and one-must/three-max invariants.
- **Integration:** SQLite constraints/transactions, Switch WebSocket/HTTP operations, OpenAI Responses tool call, cost ledger, reminder dedupe, backup/restore.
- **E2E:** full goal→month→week→day→reconcile→approval→park/resume/complete/query journey in isolated test Discord/Switch room.
- **Security:** non-owner, wrong-room, replay, prompt injection, forged IDs, approval bypass, race, secrets, port exposure and spend cap.
- **Acceptance:** no unresolved critical/high security or functional issue; restore proven; real private-room round trip verified.

## 22. Repository structure

Target tree is fully specified in `docs/REPOSITORY_STRUCTURE.md`. Key layers:
- `src/zasky/switch/`
- `src/zasky/access/`
- `src/zasky/agent/`
- `src/zasky/domain/`
- `src/zasky/planner/`
- `src/zasky/storage/`
- `src/zasky/integrations/openai/`
- `src/zasky/scheduler/`
- `src/zasky/ops/`
- `migrations/`, `tests/`, `docs/`, `artifacts/demo/`.

There is no frontend directory.

## 23. Environment variables

Full variable purpose, required status and secret/client visibility: `docs/CONFIGURATION.md`.

Core values:
`APP_ENV`, `LOG_LEVEL`, `DATABASE_URL`, `SWITCH_BASE_URL`, `SWITCH_AGENT_ID`, `SWITCH_AGENT_API_KEY`, `SWITCH_REGISTRATION_KEY` (one-time only), `SWITCH_CONNECTION_ID`, `SWITCH_ROOM_ID`, `OWNER_SWITCH_PARTICIPANT_ID`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MAX_INPUT_TOKENS`, `OPENAI_MAX_OUTPUT_TOKENS`, `OPENAI_STORE`, `MAX_LLM_REQUESTS_PER_DAY`, `MAX_LLM_SPEND_USD_MONTH`, `TIMEZONE`, `CAPACITY_PCT`, `DAILY_TASK_LIMIT`, `TRANSITION_BUFFER_MIN`, `MORNING_PREP_MIN`, `COMMUTE_BUFFER_MIN`, `MORNING_PROMPT_TIME`, `EVENING_PROMPT_TIME`, `REMINDERS_ENABLED`, `WEEKLY_AVAILABILITY_JSON`, `WEEK_START_DAY`, `OPENAI_INPUT_USD_PER_1M`, `OPENAI_OUTPUT_USD_PER_1M`, `OPENAI_PRICE_EFFECTIVE_DATE`, `HEALTH_BIND_HOST`, `HEALTH_BIND_PORT`, `BACKUP_DIR`, `MAX_MESSAGE_CHARS`.

Secrets are server-only, never client-exposed or committed. No cost cap means no paid model service can be enabled.

## 24. Autonomous implementation plan

Exact phases, files, tests, criteria and commit checkpoints: `IMPLEMENTATION_PLAN.md`.

0. One consolidated operator intake and repository readiness.
1. Repository foundation, Switch-connected chat shell, protected test deployment and echo round trip.
2. Backend/data/migrations/owner authorization/backup.
3. Core domain tools, planner, proposals, approval, backplan and reconcile.
4. OpenAI Responses orchestration and live chat integration.
5. E2E/security functionality gate.
6. Chat UX refinement (not visual frontend work).
7. Documentation and operator completeness.
8. Demo video <=180 seconds.
9. Final regression/security and authorized release only.

At each internal checkpoint: test → inspect → fix → commit → update `AI_HANDOFF.md` and `docs/BUILD_LOG.md` → continue autonomously.

## 25. `PROJECT_SPEC.md`

The full standalone product specification is supplied as `PROJECT_SPEC.md`. It is the authority for product definition, scope, flows, functional requirements, business logic, tool contracts, error envelope and privacy classification.

## 26. `ARCHITECTURE.md`

The full standalone technical architecture is supplied as `ARCHITECTURE.md`. It defines Switch protocol integration, the fixed Python/SQLite stack, components, transactions, authorization, security, AI, deployment, backup and implementation details the agent may decide.

## 27. `IMPLEMENTATION_PLAN.md`

The complete nine-phase build plan is supplied as `IMPLEMENTATION_PLAN.md`. It preserves the required overall sequence and adapts frontend-specific workflow stages to a chat-native product.

## 28. `AGENTS.md`

Persistent coding-agent instructions are supplied as `AGENTS.md`. It defines source-of-truth precedence, fixed decisions, one-time intake, autonomous checkpoints, allowed implementation details, authorization limits, tests and completion criteria.

## 29. `AI_HANDOFF.md`

Current state template is supplied as `AI_HANDOFF.md`. It truthfully records that only the blueprint exists, no implementation/deployment has occurred, intake is pending, and production authorization is not granted by default.

## 30. Final pre-implementation audit

The audit is supplied as `FINAL_PRE_IMPLEMENTATION_AUDIT.md`. Blueprint-level design is complete; Phase 0 remains pending external facts and access such as repository, Switch/Discord IDs/credentials, VPS, OpenAI model/key/cost cap, owner availability, fixed events, seed commitments/tasks, backup destination, demo redaction and release authority.

---

# CODING AGENT START POINT

**Exact first task:**

Read `AGENTS.md`, `AI_HANDOFF.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `OPERATOR_INTAKE.md`, `REFERENCE_ASSETS.md` and the relevant `docs/` files. Inspect the existing repository and environment without changing anything. Then complete one consolidated **Operator Intake / Readiness Check**: verify repository/Git access, Switch host/version/agent registration, Discord bridge/private room, exact owner and room IDs, runtime credentials, OpenAI Responses model/tool capability, account quota and hard cost ceilings, VPS/SSH/persistent storage/firewall, owner timezone/weekly availability/fixed events/buffers, seed goals/commitments/week tasks, backup destination, privacy constraints, demo output/redactions and production authorization. Record answers and evidence in `OPERATOR_INTAKE.md` without printing secrets. Do not request UI reference images or install a frontend UI skill because there is no frontend. Do not begin Phase 1 while a critical input or permission is missing. Once intake passes, execute Phase 1 onward autonomously in the specified order, testing, inspecting, fixing, committing and updating `AI_HANDOFF.md` plus `docs/BUILD_LOG.md` at every internal checkpoint. Stop only for a genuine blocker or an action outside the operator's explicit authority.
