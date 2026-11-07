# Zasky — Architecture and Technical Design

> **Hackathon implementation update — 2026-11-07.** The deployed staging build
> keeps the deterministic core and Switch transport described below, but uses
> **Neon Postgres** for authoritative owner state, a private **Next.js dashboard**
> in `frontend/` on Vercel, and an isolated **SQLite judge sandbox**. Zasky runs
> two Switch connections: one for `#zasky-control` and one for
> `#judges-sandbox`. The original MVP design notes below are retained as design
> history, not as a claim that no dashboard or frontend exists.

> **Implementation adjustment — 2026-11-06.** The operator explicitly selected
> OpenRouter's OpenAI-compatible **Chat Completions** endpoint and
> `openai/gpt-4o-mini` for the hackathon staging build, instead of the OpenAI
> Responses API. The seven-tool contract, deterministic domain authority,
> owner/room gate, cost caps and approval parser are unchanged. The provider
> adapter is isolated in `src/zasky/integrations/openrouter/`; no model gains
> state, approval or arithmetic authority. This is a documented provider
> substitution, not a product-scope change.

**Status:** Proposed fixed implementation architecture  
**Date:** 2026-11-05

## 1. Architecture decision summary

Zasky is a single-owner, chat-native agent. Its actual product interface is a private Discord room connected through Switch. It has no browser frontend, website or custom dashboard in the MVP.

```text
Owner's phone/desktop
        |
        v
Private Discord channel
        |
        v
Switch Discord bridge / Switch workspace
        |
        | Switch agent WebSocket events
        v
Zasky service (one active writer process)
  |-- inbound identity + room gate
  |-- deterministic approval command parser
  |-- conversation/context adapter
  |-- LLM orchestration (strict tool schemas)
  |-- seven domain tools
  |-- deterministic planning engine
  |-- reminder scheduler
  |-- audit + structured logging
        |
        +---- SQLite database on persistent volume
        |
        +---- OpenAI Responses API
        |
        +---- Switch HTTP operations (context/post/connect)

Operator access: SSH -> host / Docker Compose / backups / logs
Health probes: private localhost-only HTTP endpoints
```

Switch must remain central: it supplies the shared chat-room event stream/context and the channel in which the owner works with the agent. Removing Switch means losing the supported room-based interface and shared-room operation; this is not a standalone CLI task manager with an optional chat skin.

### Explicit infrastructure omissions

- **No frontend:** Discord chat is the product interface.
- **No public application API:** only private health/readiness endpoints and the seven internal domain tools.
- **No queue/broker:** one in-process scheduler and one writer are enough at single-owner scale.
- **No webhooks:** Switch WebSocket carries messages; no payment/calendar/provider webhook is required.
- **No search service:** indexed SQLite queries over the owner’s own records are enough; no external search.
- **No cache:** SQLite is the source of truth; avoid stale derived state. Any optional in-process memoization is an implementation detail and cannot govern correctness.
- **No notification vendor:** reminders are posted to the connected private room through Switch.
- **No payment service or wallet:** product has no financial flows.

## 2. Fixed technology stack

| Layer | Decision | Responsibility |
|---|---|---|
| Runtime | Python 3.12+ | One maintained application process |
| API/health | FastAPI + Uvicorn | Private health/readiness and optional internal maintenance only; not a public product API |
| Validation | Pydantic 2 | Tool schemas, settings, event parsing and response validation |
| Persistence | SQLAlchemy 2 + aiosqlite | Typed persistence and async SQLite access |
| Database | SQLite on persistent VPS volume | Single-owner durable state |
| Migrations | Alembic | Versioned schema changes |
| Switch transport | `websockets` + `httpx` | Current WebSocket agent protocol plus documented HTTP operations |
| Model | OpenAI Responses API via official Python SDK | Natural-language understanding, tool selection and response drafting |
| Scheduling | `asyncio` + `zoneinfo` | In-process reminders and local-time planning |
| Tests | pytest, pytest-asyncio, httpx test client | Unit, integration and protocol/E2E tests |
| Packaging | Docker + Docker Compose | Repeatable cloud deployment |
| Host | Linux VPS with persistent disk | Always-on service, separate from owner's laptop |
| CI | GitHub Actions if repository supports it | Lint, type-check, unit/integration suite; no secrets in CI logs |
| Observability | stdlib structured JSON logging + health checks | Operational evidence without storing private conversation bodies |

**Why this stack:** the MVP has one owner, one writer, modest event volume and no need for distributed queues or a frontend. Python provides clear deterministic time/capacity logic and a direct path to tool-calling. SQLite is sufficient for the scale and simplest to back up. Docker Compose makes the service reproducible while keeping the deployment small.

**Rejected for MVP:** PostgreSQL (unnecessary operational cost for a single-writer personal agent); Redis/Celery (no independent queue workload); Kubernetes (excessive operations); Next.js/Tailwind (no web UI); a dedicated Discord bot (duplicates Switch's bridge and weakens Switch centrality); multiple microservices (unnecessary network and state complexity).

### Version policy

- Pin exact tested versions in `pyproject.toml`/lockfile; do not use wildcard ranges for production dependencies.
- Confirm Python 3.12 support across current pinned packages at intake.
- Confirm current Switch server/protocol version and WebSocket contract before implementation.
- Confirm the selected OpenAI model supports Responses API tool/function calling and configured structured output before enabling it.
- Do not use the retired/deprecated Assistants API. Model identifiers are configuration and must be verified at intake, not assumed from this document.
- Dependabot/renovation is optional; no blind major upgrades during a build checkpoint.

## 3. Switch protocol implementation

### 3.1 Registration and credentials

1. Perform one-time agent registration with the registration credential using the currently documented Switch agent registration endpoint.
2. Capture the returned `agent_id` and agent API key.
3. Store the agent key server-side with file mode `0600` or a secrets manager. Never print it.
4. Do not re-register on every process boot and do not overwrite an existing agent identity.
5. Keep the registration credential separate from the runtime agent API key.
6. Configure addressing as owner-only where supported. Application-level owner and room checks remain mandatory.

### 3.2 Connection and event loop

Use the current Switch WebSocket agent connection protocol, not legacy SSE.

- Connect to the documented WebSocket endpoint for the registered agent, with a stable `connection_id`, the configured room, and a bearer agent API key.
- Read the first `connection_state` frame and use its authoritative room set, cursor, generation, protocol revision and `heartbeat_interval_seconds`; do not assume the requested room/cursor was accepted.
- Persist the highest processed sequence/cursor and generation safely.
- The current documented heartbeat interval is 2 seconds. Respond immediately to each `ping` with a pong containing the highest processed cursor; do not queue pongs behind slow LLM work. Treat heartbeat lapse as recoverable.
- Resume with the same `connection_id`, `start_from` set to the highest processed sequence and `expected_generation` from the last connection state. Verify exact query parameter names/types against the server version during intake.
- A `gap` control frame means continuity cannot be assumed: take the server-provided resume position, attach the gap marker to the next surfaced event, and reread room history before responding. Do not process historical context as a fresh command.
- A Switch `evicted` control frame with code `taken_over` is terminal for that connection: stop reconnecting from the displaced instance. Other close/eviction codes require their documented, bounded recovery behavior.
- Enforce one active Zasky writer for the room. Use a host-level singleton/lock plus database lease/instance guard; never allow two app instances to process writes simultaneously. Deployment must stop the old writer before the new one opens a room-claiming connection, because opening another connection can take over the existing room claim.
- Process only `message` events directed/addressed to this agent and allowed room (`payload.addressed=true`); treat slash/room `command` events as unsupported in MVP. The approval text is an ordinary owner message addressed to Zasky, not a Switch slash command.
- Prefer the `addressed` event filter if compatible with the deployed protocol; remember it intentionally excludes `command` events, which MVP does not use. Confirm event envelope/field paths at intake.
- Treat sender IDs as opaque identifiers. Compare exact strings; do not parse or derive identity from them.

### 3.3 Switch operations

The application adapter needs only:
- Connect/claim the configured room as the agent.
- Read room context after a `gap` and when the LLM requires a bounded recent context window.
- Post replies and proposal summaries into the same room.

Use only documented operation schemas. Validate every response. Retry only transient failures with bounded exponential backoff and jitter. Never retry a non-idempotent operation without a stable idempotency/event key.

### 3.4 Discord boundary

No Discord token or direct Discord gateway code belongs in Zasky. Discord is reached through Switch's configured bridge. Discord bridge credentials and permissions live in the Switch deployment's secret configuration. Use a private channel and restrict membership; also keep owner verification in Zasky. Mattermost is a local fallback for setup/demo if Discord bridge is not ready, not a second concurrent MVP integration.

## 4. Application components

### 4.1 `switch_client`

- WebSocket lifecycle, heartbeat, cursor/generation persistence, bounded reconnect.
- HTTP operation client for context and message posting.
- Switch event parsing into internal typed events.
- Does not contain product decisions or task logic.

### 4.2 `access`

- Exact allowed room ID check.
- Exact owner participant ID check.
- Addressed-event check.
- Rate limit and event dedupe.
- Approval command parser. Approval is processed before any LLM call.
- Fail closed: missing identity or malformed room data means no domain access.

### 4.3 `agent`

- Build minimal system/developer context from stored state and bounded room history.
- Call OpenAI Responses API with only the seven registered tool schemas.
- Validate tool calls with Pydantic before domain execution.
- Limit tool loops to five rounds per inbound message; maximum two state-changing tool proposals per event before returning control to owner.
- No direct SQL or unrestricted network/shell tools.
- Format concise messages, with proposal code and exact approval command.

### 4.4 `domain`

Pure functions and services for goals, commitments, placements, day plans, reconciliation, task state, queries and proposal lifecycle. This layer contains the invariants in `PROJECT_SPEC.md`.

### 4.5 `planner`

Deterministic time calculations:
- Daily, weekly and monthly capacity and slack.
- Fixed-event overlap and transition buffers.
- Remaining-week feasibility from future available windows compared with all incomplete non-cancelled task estimates; parked tasks remain in the workload estimate.
- Task schedule placement and per-task date movement within a week.
- Backplan/latest wake.
- Reconcile feasibility and risk.
- Deadline ledger.
The LLM can explain and select intent; it does not calculate authoritative values.

### 4.6 `storage`

SQLAlchemy models, repository methods, transactions, revision checks, audit writing and database initialization. All business mutations pass through domain services.

### 4.7 `scheduler`

One in-process scheduler for morning/evening reminders and proposal expiry housekeeping. Database uniqueness provides dedupe across restarts. No Redis or external job queue in MVP.

### 4.8 `ops`

Private liveness/readiness endpoints, backup/restore commands, migration status and safe diagnostics. Do not expose operational endpoints publicly.

## 5. Persistence design

### 5.1 Core entities

| Entity | Purpose | Main fields |
|---|---|---|
| `owner_config` | Single-owner configuration | owner participant ID, room ID, timezone, capacity, availability, buffers, reminder settings |
| `year_goals` | Testable long-range goals | year, title, evidence, status |
| `month_commitments` | Owner-chosen concrete monthly outcomes | goal ID, year/month, title, estimate, deadline, consequence, priority, status |
| `fixed_events` | Immutable time anchors | title, starts/ends UTC, local timezone/date, source |
| `week_placements` | Link a commitment to a specific week | commitment ID, week start, status |
| `week_tasks` | Concrete owner-named work items in the approved week pool | placement ID, title, estimate, scheduled date, status, resume note, actual time |
| `day_plans` | Approved plan for one local date | date, revision, battery, status, plan source, wake/start calculations |
| `day_plan_items` | Selected subset and dispositions for a day | plan ID, task ID, order, must/should/drop, planned interval |
| `pending_proposals` | Approval-gated record/week/day/reconcile changes | code, type, status, payload, expected base revisions, expiry |
| `planning_scope_revisions` | Optimistic concurrency for proposal freshness | canonical scope key, monotonic revision, update time |
| `switch_connection_state` | Durable Switch resume state | agent ID, connection ID, generation, highest processed sequence, protocol revision, last connected |
| `processed_switch_events` | Idempotent inbound event ledger | numeric event sequence, room, message ID, sender, outcome, processed time |
| `reminder_dispatches` | Reminder dedupe and delivery state | local date, type, status, sent time |
| `audit_events` | Append-only domain decision evidence | actor, action, entity, redacted summary, timestamp |
| `model_usage_records` | Request/token/cost ledger for hard spend controls | provider request ID, model, token counts, pricing version, reserved and actual micro-USD, status |
| `timebox_checkins` | Optional task-overrun / panic 10-minute check-ins | task/day item, due time, status, idempotency key |

### 5.2 Relationships

```text
year_goals (0..5 active per year)
    1
    |
    +----< month_commitments (0..many)
                 |
                 +----< week_placements (0..many across weeks)
                              |
                              +----< week_tasks (1..many)
                                           |
                                           +----< day_plan_items >---- day_plans

pending_proposals: polymorphic proposal payload referencing affected records
fixed_events: independent time anchors read by planner
processed_switch_events / reminder_dispatches / audit_events: operational ledgers
```

### 5.3 Key schema constraints

- Use UUID primary keys generated by the application.
- Store event instants as UTC; store planning dates as `DATE` in the owner's IANA timezone.
- `owner_config` is a singleton row.
- `year_goals`: unique `(year, normalized_title)`; enforce max five active goals per year in domain transaction.
- `month_commitments`: FK to goal nullable; index `(year, month, status)` and `deadline_local_date`.
- `week_placements`: index `(week_start,status)`; FK to commitment.
- `week_tasks`: FK to placement; store `scheduled_date` on each task; index `(scheduled_date,status)` and `(placement_id,status)`; validate that scheduled date falls inside parent week; estimate > 0.
- `day_plans`: unique `(local_date, revision)` and unique active/approved plan per local date enforced transactionally.
- `day_plan_items`: unique `(day_plan_id, task_id)`; unique `(day_plan_id, position)`; exactly-one-must enforced by domain service.
- `pending_proposals`: unique `code`; index `(status, expires_at)`; JSON payload schema version and every expected scope/revision pair included.
- `planning_scope_revisions`: canonical scope keys for goal/year, month, week, day, affected commitment and owner config. Increment all affected revisions in the same transaction as each committed mutation; proposal approval compares all expected revisions before applying changes.
- `switch_connection_state`: one row per registered agent; persist stable connection ID, current generation, highest processed numeric event sequence and protocol revision.
- `processed_switch_events`: use numeric Switch event `sequence` (the WebSocket frame `id` is the same sequence) as the idempotency key scoped to the registered agent; store message ID and outcome but not body.
- `reminder_dispatches`: unique `(local_date, reminder_type)`.
- `audit_events`: append-only; do not allow application update/delete.
- Foreign keys ON; WAL mode; busy timeout configured.

### 5.4 Privacy and ownership

The database is private to the owner. The owner’s titles, goals, schedules, deadlines, consequences, availability, resume notes and battery values are not exposed to other participants. No public list/query endpoint exists. Credentials are never stored in domain tables.

## 6. Transaction and concurrency design

- Single active application writer. Enforce singleton with process lock and persistent instance lease.
- Use SQLite WAL, `foreign_keys=ON`, a documented `busy_timeout`, and parameterized queries through SQLAlchemy.
- Write transactions use `BEGIN IMMEDIATE` where appropriate to serialize proposal approval and revision checks.
- Proposal approval transaction:
  1. verify owner/room in application layer;
  2. load proposal and verify pending/unexpired;
  3. compare current affected-scope revision with `base_revision`;
  4. validate payload against current task and fixed-event state;
  5. apply all day/week/task changes;
  6. update proposal status to approved;
  7. append audit event;
  8. commit.
- If any step fails, rollback fully and leave proposal pending/stale as appropriate.
- Never split placement changes across separate transactions.
- Inbound event is marked processed in the same transaction as any domain write where possible. If message posting fails after write, the event outcome is still queryable and retry must not repeat the write; post result can be retried by a safe outbox pattern or idempotent send key if Switch supports it.
- Keep an outbound message record/outbox only if the chosen Switch API lacks reliable idempotent message post. Avoid adding queue infrastructure.

## 7. Authentication and authorization

### Inbound message authorization

For every event, all must pass:
1. valid Switch authenticated connection/event;
2. exact configured room ID;
3. exact configured owner participant ID as sender;
4. addressed to this agent under current protocol (`payload.addressed=true`); approval messages must also be addressed to Zasky, even though they bypass the LLM;
5. event has not already been processed;
6. sender/event is not over per-owner rate limit.

No model call before these checks. Do not rely exclusively on Discord role names, nicknames, display names or Switch room addressing. Use opaque Switch participant ID as exact identity.

### Operator and host access

- SSH key authentication only; disable password SSH and root login where provider permits.
- Restrict security group/firewall to SSH from operator's known access range where practical; do not expose database or Docker socket.
- Switch ports are the only required external application ports; health endpoints bind localhost/private interface.
- Docker secrets or protected env file owned by service account, mode `0600`.
- No web admin UI. Admin actions via SSH CLI and Switch server's own controls.

### Account lifecycle

Single-owner configuration is created during first setup. If owner participant ID or room changes, require operator shell-level reconfiguration and a verification message; do not accept identity changes from chat. Rotate API keys by replacing secret, restarting, verifying connection, then revoking old key. Backup before migration/identity changes.

## 8. Security architecture and threat model

| Threat | Mitigation |
|---|---|
| Non-owner tries to read plan | Exact sender ID allow-list before context or model call; owner-only Switch addressing; generic denial/no data |
| Wrong room / public room | Exact room ID allow-list; private room membership; ignore all other rooms |
| IDOR / guessed task ID | Domain queries always scope to owner singleton; opaque UUIDs; no caller-supplied owner ID; not-found for foreign IDs |
| Prompt injection in room history | Treat all message bodies/context as untrusted data; instructions only from system/developer prompt; quote/sanitize context; no arbitrary tools |
| LLM proposes invented task | Validate every task ID against week pool; task titles accepted only from owner input; schema rejects unknown IDs |
| LLM attempts approval | Approval parser is deterministic outside model; model has no proposal-approval tool; require exact owner command |
| Tool schema abuse | Pydantic validation; enums, length limits, max array sizes, positive integers; reject extra fields |
| SQL injection | SQLAlchemy parameterized statements; no dynamic SQL from model/user text |
| XSS | No custom browser UI; chat text encoded/posted as ordinary message; do not render untrusted HTML or embeds |
| CSRF | No browser session or state-changing HTTP endpoint; internal health endpoint read-only/private |
| SSRF | No model-requested URL fetching; Switch URLs fixed by configuration; outbound host allow-list |
| Brute force/enumeration | No public login; room and sender allow-list; message rate limit; opaque identifiers; generic errors |
| Replay/duplicate messages | Unique Switch event ID/cursor ledger; idempotent state writes and approvals |
| Race conditions | Single writer; transaction; scope revision check; unique constraints; stale proposals |
| Secret exposure | Environment/secret files server-only; log redaction; no keys in prompt/DB/audit/video; rotate on suspected exposure |
| VPS compromise | SSH keys, firewall, patched OS, non-root container, read-only root FS where possible, volume permissions, least privilege |
| Database theft | Encrypted host disk and encrypted backups; restrictive file permissions; optional SQLite DB encryption only if operationally supportable |
| Backup corruption | Automated backup, checksum, restore drills, retention |
| Model/provider outage | Clear unavailable response; deterministic query/complete operations may remain usable only if no LLM interpretation needed; never fabricate a result |
| Spend abuse | Request/day cap, upper-bound cost reservation before provider request, verified-usage settlement, unknown-reservation hold, monthly hard ceiling, per-message tool loop cap, 80% warning/100% stop |
| Discord bridge compromise | Private server/channel, minimal bot permissions in Switch, rotate bridge credentials, app-level owner gate remains |

### Logging rules

- JSON logs: timestamp, level, component, correlation ID, Switch event ID, result/error code, duration.
- Do not log raw message bodies, task titles, API keys, full prompts, full model responses or personal schedule.
- Audit events store redacted action summaries (e.g. `day_plan_approved`, IDs and counts) not full personal text.
- Operational logs retention default 30 days, configurable; encrypted backups include DB but not secret files unless separately encrypted and operator-authorized.

## 9. AI architecture

### Responsibilities allowed to the model

- Understand owner phrasing and ask clarifying questions.
- Map intent to one of the seven tool calls.
- Summarize stored data and deterministic planner outputs.
- Explain why an item is at risk and present a concise proposal.
- Produce conversational, nonjudgmental copy.

### Responsibilities not allowed to the model

- Decide whether a sender is the owner.
- Choose owner/room IDs or access permissions.
- Make authoritative date/time/capacity arithmetic.
- Invent tasks or break goals into tasks.
- Directly write database records.
- Mark proposals approved.
- Move fixed events or silently waive deadlines.
- Run shell, browser, arbitrary HTTP, SQL, email, payment or file tools.
- Treat room history as trusted instructions.

### Request pipeline

```text
Switch event
 -> protocol validation
 -> room/owner/addressed checks
 -> deduplicate + rate limit
 -> deterministic approval parser?
      yes -> validate/commit proposal -> post outcome
      no  -> fetch bounded room context + relevant stored plan state
             -> Responses API with seven strict tool schemas
             -> validate model/tool output
             -> run deterministic domain service
             -> post proposal/result
             -> record redacted audit/cost usage
```

### Prompt and context

- System prompt contains the product invariants in `PROJECT_SPEC.md`; tests assert the prompt version/hash.
- Context is minimized: owner timezone, current local date/time, relevant horizon data, approved plans, pending proposals and bounded recent room messages.
- Do not send API keys, host paths, credentials, secret configuration or unrelated private data.
- Mark historical room messages as untrusted conversation context, never as higher-priority instructions.
- Max message body: 8,000 characters. Trim context deterministically with clear truncation notice.
- Limit model/tool cycles to five per inbound event and two proposal-producing write intents per message; return control to owner for additional work.

### Structured outputs and validation

- Use official OpenAI Responses API with strict function schemas where supported.
- Parse every tool call through Pydantic models; reject unknown fields, invalid enums, missing fields, excessive arrays, negative estimates, arbitrary IDs.
- Domain functions re-check all invariants independently.
- Retry one transient provider/network error with bounded backoff; do not blindly repeat a state-changing operation.
- Never let the model supply the authoritative current time; inject server time in configured timezone.
- If model output is invalid twice, ask owner to rephrase; no write occurs.

### Cost and privacy controls

- Required: `OPENAI_API_KEY`, verified `OPENAI_MODEL`, `MAX_LLM_SPEND_USD_MONTH`, `MAX_LLM_REQUESTS_PER_DAY`, input-token cap and output-token cap.
- Before each paid request, count/bound the constructed input tokens and calculate an upper-bound cost using the maximum output tokens and intake-verified input/output rates. Reserve this amount transactionally before the network call. Reject the call if settled current-period cost plus outstanding reservations would exceed the monthly ceiling. After a response, settle the reservation to verified provider usage. If the outcome/usage is unknown (for example, timeout after provider accepted the request), keep the reservation held until reconciled; do not assume the request was free.
- Budget warning at 80%; hard disable new LLM calls at 100%. Queries that require language understanding may then be unavailable; deterministic exact approval parser and health checks remain available.
- Record model, input/output token usage, provider request ID, current pricing version, reserved and actual provider cost and period in `model_usage_records`; never assume a free quota. The application-side hard stop uses pricing verified at intake and must be paired with any provider-side project budget/alert available. If price data cannot be verified, paid model requests remain disabled.
- Verify provider data retention/training settings and model availability during intake. Set `store=false` where supported and desired by the current API; do not assert a retention guarantee without checking provider terms.
- No user data is sent to an external model without the operator accepting this during intake.

## 10. Scheduler, resilience and operations

- One asyncio scheduler in the main service process.
- Run morning/evening reminders at configured local times (defaults are proposed in intake, not silently assumed).
- Enforce one message per `(local_date, type)` in DB.
- Proposal expiry can be lazy (on next read/approval) plus hourly cleanup; no task queue needed.
- Health: `/health/live` = process loop alive; `/health/ready` = DB reachable, migrations current, Switch session status and model configuration (without exposing secrets).
- Use Docker restart policy with bounded backoff; one app replica only.
- SQLite file on persistent VPS volume; no network filesystem.
- Daily encrypted DB backups; retention 7 daily + 4 weekly; verify checksums; restore test before a release and at least monthly.
- For WAL databases use SQLite online backup API or a proper checkpoint-and-copy procedure; never blindly copy only the main `.db` file while WAL is active.
- Cloud target: Linux VPS with sufficient persistent disk, fixed public endpoint if required by Switch, automated OS security updates under controlled maintenance, and SSH access.
- If VPS setup is disproportionately blocking, local demo may be used as explicitly labeled fallback; it does not demonstrate resilience to owner's laptop/power failure.

## 11. Third-party integrations

| Integration | Required? | Use | Failure behavior |
|---|---|---|---|
| Switch | Yes | Agent connection, room event stream, context and posting | Reconnect; on auth/room failure pause processing and report |
| Discord bridge in Switch | Yes for target experience | Mobile/desktop private chat | If unavailable, local Mattermost can be temporary demo fallback |
| OpenAI Responses API | Yes for natural-language interaction | Understand intents, tool calling and response drafting | Bounded retry, then transparent unavailable response |
| VPS provider | Yes for resilient target deployment | Runs Switch and Zasky persistently | Local demo only as documented fallback |
| Google AI TTS | Optional, demo only | Voiceover for demo | Use genuinely free permitted fallback or no narration if unavailable |

No payment, calendar, email, notification vendor or separate Discord API integration in MVP.

## 12. Deployment topology

Recommended production topology on one Linux VPS:

```text
Host firewall
  - SSH from operator
  - Switch-documented inbound/outbound ports only
  - No public Zasky health/API port
  |
Docker Compose project
  |-- switch service(s) + Discord bridge (official Switch deployment)
  |-- zasky service (single replica, non-root)
  |-- persistent volumes:
        switch data/config
        zasky SQLite + backups
```

Prefer separate Compose projects/networks if required by official Switch deployment. Do not rewrite or fork Switch deployment files unnecessarily. Pin image versions/digests where supported. Zasky reaches Switch over an internal Docker network or documented secure URL. The external port mapping is decided from the official deployment's current requirements during intake.

No frontend preview deployment is applicable. The equivalent Phase 1 proof is a **live private Discord room round-trip** through Switch, with a protected test environment and an exact deployed commit/version recorded.

## 13. Backup, recovery and disaster behavior

- Daily automated encrypted backups, 7 daily + 4 weekly retention.
- Backup DB and required migration metadata; backup secrets only separately under explicit encryption/permissions.
- Test restore into a temporary isolated DB; run integrity check and foreign-key check.
- On data restore, reconcile event cursor cautiously: do not replay old state-changing messages. Require operator to reset/resume cursor according to verified Switch protocol.
- After multi-day service outage, owner uses `reconcile` in bulk mode; Zasky summarizes missed dates and proposes only in-week recovery. It does not pretend the plan stayed current while offline.
- When Switch loses event continuity (`gap`), reread room context but never replay old command messages as new instructions unless protocol event identity and dedupe establish they are new.

## 14. Implementation details the coding agent may decide

- Exact Python module/file names inside the repository structure.
- SQLAlchemy relationship-loading style and repository class boundaries.
- Internal class naming and log formatter implementation.
- Choice of a maintained cron helper versus a small asyncio scheduler loop, provided one-process semantics and idempotency remain.
- Exact retry backoff constants within documented maximums.
- Internal message formatting/emoji choices, provided no critical information relies only on emoji.

These are implementation details only. The agent may not change the fixed architecture, seven tools, state invariants, storage choice, Switch transport, authorization rules or scope without documenting a genuine incompatibility and stopping only the affected work.
