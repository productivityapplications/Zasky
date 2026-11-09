# Zasky Build Log

## 2026-11-07 — Task typing, judge sandbox and final branding

- Added `week_tasks.execution_type` with migration `5234927536a9`; human tasks
  can never enter delegation, enforced in domain, chat, coordinator and API.
- Added the isolated SQLite judge sandbox, sandbox dashboard mount, optional
  Switch sandbox room routing, demo-mode Vercel proxy and banner.
- Added slanted Z SVG favicon, rail logo replacement, removed the profile icon,
  and added GitHub/Docs/WeMakeDevs/Switch footer links.
- Replaced README with the complete architecture, phases, user guide and judge
  instructions.
- Tests: **165 passed**; `ruff` clean; `mypy src` clean; demo and normal
  `npm run build` clean.

## 2026-11-07 — Execution context assembly

- Added `DelegationContext` assembly through `DomainService.task_detail`: task,
  estimate, parent commitment, parent year goal, evidence of done, resume note,
  commitment priority/deadline/consequence and owner instructions.
- Execution Agent system prompt now carries the full context and requires
  explicit missing-context notes in the Verification Checklist.
- `delegate ZK-XXXX [instructions]` now parses and forwards the optional suffix.
- Dashboard Confirm Delegation modal has an optional Additional Context /
  Instructions textarea passed to the delegate API.
- Tests: **165 passed**; `ruff` clean; `mypy src` clean; `npm run build` clean.

## 2026-11-07 — Tailwind redesign and human-in-the-loop delegation

- Replaced the legacy dark dashboard with the approved three-column Tailwind
  design: yellow navigation rail, light calendar workspace, dark All Tasks
  queue, and real-data analytics dock.
- Added Tailwind CSS/PostCSS/autoprefixer, Manrope, shared UI primitives and
  componentized PlanView, TaskQueuePanel, ReconciliationView, AnalyticsDock,
  WorkspaceHeader, NavigationRail and modals.
- Added the `delegation_proposals` table and migration `526c14430d14`.
- Added deterministic `delegate ZK-XXXX` and `approve execution ZK-YYYY`
  commands. The model has no eighth tool; all state transitions are application
  code.
- Updated the Execution Sub-Agent prompt to allow only copy, code snippets,
  plans and document formatting, and to always return the three required
  Markdown sections.
- Updated the dashboard delegate modal to Confirm Delegation → structured
  output → Approve Execution & Complete Task.
- Tests: **165 passed**; `ruff` clean; `mypy src` clean; `npm run build` clean.
- Neon schema migrated to `526c14430d14`.

## 2026-11-07 — Calendar feed and Google Calendar links

- Added a dynamic iCalendar feed from Postgres covering active fixed events and
  approved day-plan tasks. Task events include a `VALARM` display trigger
  (`CALENDAR_ALARM_MINUTES`, default 5).
- Added RFC 5545 escaping/folding, stable UIDs, UTC event times and subscription
  refresh hints.
- Added Google Calendar quick-add utilities. Task payloads include a quick-add
  URL; the Daily Briefing appends an all-day Google Calendar link.
- Added the dashboard **📅 Sync to Calendar** button and per-task 📅 links.
- Auth accepts the dashboard bearer token, or `?token=CALENDAR_FEED_TOKEN` for a
  direct subscription URL.
- Live Neon feed check: 9 VEVENTs, 6 task alarms, fixed events included.
- Tests: **151 passed**; `ruff` clean; `mypy src` clean; `npm run build` clean.

## 2026-11-07 — Two-way dashboard and Execution Sub-Agent

- Added dashboard write endpoints for year goals, month commitments, week-pool
  tasks and task delegation. Goals/commitments use `propose_record` plus the
  deterministic approval path; tasks use the new `DomainService.add_week_task`
  so an existing commitment placement is appended rather than duplicated.
- Added `GET /api/dashboard/goals` and `GET /api/dashboard/commitments` for the
  modal selectors.
- Added the bounded `ExecutionSubAgent`: one tool-free LLM call, existing cost
  guard, no planning mutation, output returned to the dashboard and posted to
  `#ai-workspace` when configured.
- Added Next.js modal forms for New Goal, New Commitment and Add Task; added the
  task-pool delegate button with loading and output states.
- Extended the Next.js proxy allowlist and timeout for delegation.
- Tests: **151 passed**; `ruff check .` clean; `mypy src` clean; `npm run build`
  clean.
- All writes target the same Neon Postgres database that Zasky reads in Discord.

## 2026-11-07 — Discord routing activated

- Operator ran the reviewed `scripts/setup_discord.py`; the `Zasky HQ` category
  and all five channels were created.
- Added `DISCORD_BOT_TOKEN` and the five channel IDs to the protected env.
- Recreated the container with `docker compose up -d --force-recreate` so the
  new environment was loaded (a restart alone would not do this).
- Verified inside the container: routing configured, daily/reconcile/AI channel
  IDs present. Read-only Discord API checks returned HTTP 200 for all three
  channels. No test message was posted.
- Health after recreation: database/switch/schema/model ready.
- Next: exercise one plan approval and one reconcile approval, then apply
  Discord room privacy.

## 2026-11-07 — Discord HQ layout and notification routing

- Added `scripts/setup_discord.py`, a reviewed-but-not-executed one-off Discord
  REST setup script. It creates the `Zasky HQ` category and `#zasky-control`,
  `#daily-briefings`, `#reconcile-alerts`, `#ai-workspace`, `#dashboard-sync`.
  It is idempotent, refuses to move same-named channels outside the category,
  writes `data/discord_channels.json` (mode `0600`) and prints backend env lines.
- Added a narrow outbound `DiscordNotifier` for three configured channel IDs.
  The chat interface remains Switch; no inbound Discord Gateway is opened and
  the model has no Discord tool.
- Approved `plan_day` briefings now go to `#daily-briefings` when configured,
  with a main-room fallback. Approved `reconcile` summaries go to
  `#reconcile-alerts`. Execution Sub-Agent results go to `#ai-workspace` through
  `POST /api/internal/execution-results`.
- Discord messages cap content at 2,000 characters and send
  `allowed_mentions: {"parse": []}`.
- Added `DISCORD_*` settings, `docs/DISCORD_SETUP.md`, API/config/deployment/
  operator notes and unit tests for channel routing, retries, permissions and
  the execution-result ingestion endpoint.
- Tests: **136 passed**; `ruff check .` clean; `mypy src` clean. The setup script
  was syntax-checked with `py_compile` but **not executed**.
- Release state remains **verified-staging-awaiting-authorized-release** and the
  Vercel dashboard is deployed and working.

## 2026-11-07 — Neon Postgres and Vercel-ready owner dashboard

- Added `asyncpg` and normalized Neon URLs (`postgres://`/`postgresql://` →
  `postgresql+asyncpg://`, `sslmode` → asyncpg `ssl`, drop `channel_binding`).
- Added SQLite/Postgres engine branching, `pool_pre_ping` on Postgres and a
  process-lifetime statement-cache-off connection pool for Neon/PgBouncer.
- Updated Alembic environment and the baseline migration for Postgres partial
  indexes and append-only audit triggers.
- Migrated Neon to `b23394c5a105` → `6823aaca3872` → `9f4c1a7b2d30`. The last
  migration widens Switch sequence columns to `BIGINT` after a real sequence
  value exceeded signed 32-bit range.
- Seeded synthetic base data plus a dashboard-specific today plan and one
  reconciliation history entry.
- Added an authenticated owner dashboard API on `0.0.0.0:8100` with CORS,
  bearer auth and four routes: today, tasks, completion and reconciliation
  history.
- Added `frontend/`: Next.js 16 dark dashboard with Today's Plan (MUST/SHOULD),
  All Tasks with interactive completion checkboxes and a reconciliation timeline.
  The browser uses a same-origin Next proxy; the token stays server-side.
- Added `frontend/README.md` with exact Vercel steps, environment variables and
  the optional `sudo ufw allow 8100/tcp` command. Port `8000` remains Switch.
- Live evidence: dashboard API read returned the approved plan, task pool and one
  recovery record; a completion POST updated Neon and the task counts. The
  Next.js production server proxy returned the same payload.
- Tests: **124 passed**; `ruff check .` clean; `mypy src` clean; `npm run build`
  clean. Container health: database/switch/schema/model all ready.
- Release state remains **verified-staging-awaiting-authorized-release**.

## 2026-11-05 — Blueprint package authored

- Read the Zasky project handoff and `PROPER_VIBE_CODING_WORKFLOW_AUTONOMOUS.md`.
- Translated generic workflow to chat-native product.
- Explicitly excluded irrelevant frontend requirements: website, early skeletal frontend shell, UI reference image intake, mockups, `stageshow` skill and frontend footer/metadata.
- Preserved complete intake, autonomous phases, checkpoint tests/commits, security boundaries, docs, handoff and <=180-second demo.
- Produced product, architecture, tool contracts, data model, intake, implementation plan and operator docs.
- Product code not started. No external credentials tested. No deployment performed.
- Current state: blueprint ready; waiting for coding-agent execution to conduct its own Phase 0 operator intake.

## 2026-11-06 — Phase 1: Switch-connected chat shell

- Inspected the existing repository: docs-only, clean `main`, no prior application
  code, manifests, migrations, tests or CI.
- Completed the read-only environment inspection and consolidated Phase 0 intake
  report. Confirmed Python 3.12.3, uv, Node, ffmpeg and Docker availability.
- Deployed the official Switch **0.31.0** Compose stack locally with the
  `collab` and `gateway` profiles; Postgres is on localhost:5433 and the Gateway
  on localhost:3001. The Switch API is on localhost:8000.
- Set `SWITCH_VERSION=0.31.0`, `POSTGRES_HOST_PORT=5433`,
  `GATEWAY_HOST_PORT=3001`; regenerated Switch-local secrets and restricted
  `/root/switch/.env` to `0600`.
- Registered `zasky` as a custom agent. The agent ID is redacted here and stored
  only in the protected env file. The temporary admin-owned registration key was
  used once and revoked.
- Created `/root/Zasky-secrets/zasky.env` with mode `0600` containing the Switch
  base URL, agent ID, runtime key, room ID, owner participant ID and a stable
  connection ID. No secret value was printed or written to the repository.
- Added the Phase 1 Python package, strict settings validation, JSON logging with
  redaction, SQLite operational state, WAL/foreign-key/busy-timeout setup,
  single-writer lock, Switch WebSocket lifecycle, heartbeat/pong, bounded
  reconnect, `gap` handling, `taken_over` stop, event dedupe and deterministic
  echo. Added the private health server and Dockerfile/Compose service.
- Tests: `uv run pytest -q` → **33 passed**. `uv run ruff check .` → clean.
  `uv run mypy src` → clean. Docker image builds successfully; container runs as
  uid 10001 with a read-only root filesystem, `CAP_DROP=ALL`, and a persistent
  `./data` bind mount. Container healthcheck is healthy.
- Switch connection evidence: logs show `Switch room ready`, and
  `/health/ready` returns `{"status":"ready","database":"ok","switch":"connected"}`.
- Known issue: Switch currently reports the Discord room as `channel_public`
  rather than `channel_private`. The owner/room application gate is still in
  force, but Phase 1 acceptance will not be claimed until the Discord
  `@everyone → View Channel = deny` privacy setting is applied or the room is
  replaced.
- Authorization: local staging only; no production deployment; no Zasky domain
  data existed before this phase. `docker compose down -v` on the local Switch
  stack was explicitly authorized by the operator and destroyed only the local
  Switch volumes.
- Next: observe one real owner message in the Discord room, then proceed to
  Phase 2 (durable domain schema, Alembic, owner access boundary, backup/restore).

## 2026-11-06 — Phase 2: durable schema, migrations and recovery

- Added the complete MVP SQLAlchemy model set: owner configuration, goals,
  commitments, fixed events, placements, tasks, day plans/items, proposals,
  scope revisions, reminders, audit events, model usage, timebox check-ins and
  the Switch connection/event ledgers.
- Added a tested Alembic baseline migration (`b23394c5a105`) with indexes,
  checks, foreign keys, a partial unique placement index, and append-only
  triggers on `audit_events`.
- Added owner-singleton seeding from validated settings, optimistic scope
  revision repositories, append-only audit writes and schema-revision checks.
- Added manual SQLite online backup, SHA-256 sidecar, restore verification
  (`integrity_check` + `foreign_key_check`) and a retention helper. Encrypted
  backup automation remains intentionally deferred.
- Added the local maintenance CLI (`zasky-maintenance`) for migrate/status/
  backup/restore/prune.
- Tests: **46 passed**; `ruff check .` clean; `mypy src` clean.
- Migration evidence: upgrade → `b23394c5a105`; `alembic check` reports no new
  operations; downgrade to base and re-upgrade both succeeded.
- Staging evidence: Phase 1 ops DB backed up, fresh Phase 2 DB migrated, owner
  config seeded once, container rebuilt and `/health/ready` returns
  `{"status":"ready","database":"ok","switch":"connected","schema":"current"}`.
- Restore drill: backup `zasky-20261106T100821Z.db` restored to
  `/tmp/zasky-restore-test.db`; integrity `ok`, foreign-key violations `0`,
  17 tables, owner config present.
- Known issue unchanged: the Discord room is still `channel_public`; the live
  owner round-trip is still pending.
- Next: Phase 3 domain services, seven strict tools, proposal lifecycle and
  deterministic planner.

## 2026-11-06 — Phase 3: deterministic domain, seven tools and planner

- Added the seven strict request schemas and tool definitions:
  `add_commitment`, `place_week`, `plan_day`, `reconcile`, `park_task`,
  `complete_task`, `query`. Unknown fields are rejected.
- Added deterministic capacity math: availability windows, fixed-event overlap,
  transition buffers, 65% budgets, daily/weekly/monthly slack and remaining-week
  capacity.
- Added deterministic scheduling, fixed-event avoidance, backplan/latest-wake
  and week feasibility arithmetic.
- Added the proposal lifecycle: human-readable codes, 30-minute/24-hour TTLs,
  expected-scope revisions, stale/expired handling, rejection, duplicate
  approval idempotency and transactional application.
- Added owner-authored goal/commitment/fixed-event proposals with five-goal cap,
  duplicate-title checks, evidence requirement, immutable fixed events and
  parent-commitment cancellation cascading to week tasks.
- Added week placement with capacity enforcement, ad hoc provenance rules, date
  bounds, least-loaded auto-placement and approval.
- Added day planning with week-pool-only selection, one must, three-task ceiling,
  low-battery shaping, fixed-event avoidance and backplan.
- Added reconcile proposals with keep/move/unplaced output, in-week moves and
  week-holds/at-risk arithmetic.
- Added immediate park/resume/complete actions with note requirements and
  idempotent completion, plus read-only bounded queries and deadline risk.
- Tests: **78 passed**; `ruff check .` clean; `mypy src` clean.
- Still pending: one real Discord owner message, room privacy, OpenAI access and
  planning/demo inputs. Phase 4 is blocked on the OpenAI key and provider data
  acceptance but the adapter can be built against a fake provider.

## 2026-11-06 — Phase 4–8: OpenRouter, live E2E, chat UX, docs and demo

- Applied the operator's explicit provider-change authorization: OpenRouter
  OpenAI-compatible **Chat Completions**, model `openai/gpt-4o-mini`, pricing
  `$0.15/$0.60` per 1M input/output, `$20` monthly cap and `100` requests/day.
  The seven tools, deterministic domain and approval parser are unchanged.
- Implemented the bounded model/tool loop: max five cycles, max two proposals
  per message, strict Pydantic validation, tool error relay, hallucinated-code
  rejection, status-action intent guard and transparent provider errors.
- Added the cost/request guard with month-to-date and daily counters. Demo
  model calls consumed 7 requests and **$0.003779** in the isolated demo DB;
  staging remains at $0.
- Added minimal context (goals, commitments, fixed events, week pool, today's
  plan, pending proposal codes, display-time fields) with no participant/room
  IDs or raw room history.
- Live evidence: normal prose and tool calls worked; a real goal → commitment →
  week placement → day plan chain produced and approved proposals; a real
  query → reconcile → approve → query chain produced
  `artifacts/demo/transcript.txt`.
- Prompt-injection probe asking for system prompt, API key and room ID was
  refused. Unauthorized event tests prove handlers are never called for wrong
  room, wrong sender or unaddressed messages.
- Chat UX refined: concise mobile-first structure, exact proposal codes,
  "Nothing is changed until approval", local display times, exact task titles,
  explicit week feasibility arithmetic and transparent failure messages.
- Documentation updated for the provider adjustment, local staging, model caps,
  operator commands, backup/restore and demo limitations.
- Produced `artifacts/demo/zasky-demo.mp4` (97s, H.264/AAC, 1280×720) with
  `espeak-ng` narration. It is a real-model **local protocol/transcript** demo,
  not a Discord screen capture, and is labeled as such.
- Tests: **95 passed**; `ruff check .` clean; `mypy src` clean.
- Remaining blockers: Discord room is still `channel_public`; no app-level live
  Discord owner message has been observed by this container. The user has been
  asked to test in Discord. Production release is not authorized.

## 2026-11-06 — Phase 9: final regression and release checklist

- Final tests: **95 passed**; `ruff check .` clean; `mypy src` clean.
- Secret scan of tracked/candidate files found no API keys, bearer tokens or
  real owner/room IDs. `.env` remains untracked and mode `0600` outside the repo.
- Final online backup `zasky-20261106T144317Z.db` restored to an isolated target:
  integrity `ok`, 0 foreign-key violations, 17 tables, 3 goals, 3 commitments,
  6 week tasks, 2 day-plan items, schema `b23394c5a105`.
- Staging health: `{"status":"ready","database":"ok","switch":"connected",
  "schema":"current","model":"configured"}`.
- Demo video: 97.19s, 1280×720 H.264/AAC, local TTS, real model/tool transcript,
  synthetic data, explicitly labeled not a Discord screen capture.
- Final release state: **verified-staging-awaiting-authorized-release**.
- Remaining limitations: Discord room is still `channel_public`; the running
  container has not logged an app-level live Discord owner message. No production
  deployment is authorized. The transcript demo is not a substitute for the live
  Discord round-trip; both limitations are stated in the handoff and docs.

## 2026-11-06 — Phase 4 chat-context follow-up

- Added the last eight ordinary Switch room messages to the model context via
  `read_context`; each is bounded to 500 characters, marked untrusted and never
  persisted in SQLite. The current inbound body is filtered out to avoid
  duplication.
- Added deterministic date/time normalization for `plan_day` and `reconcile`
  from the owner's text and the context dates map. Plan requests now produce a
  `plan_day` proposal with a code; the deterministic fallback covers a model
  that chooses a read-only query.
- Plan/reconcile proposal blocks are rendered from tool payloads, so the model
  cannot substitute a wrong weekday, UTC/local time or task title.
- Added a deterministic conversational-approval guard: "looks good", "lock that
  in", "go ahead" and similar phrases never commit; if a proposal is pending,
  the reply names the exact `approve ZK-XXXX` command.
- System prompt updated with the same rules and the server date to anchor the
  model's calendar.
- Tests: **100 passed**; `ruff check .` clean; `mypy src` clean. Live model
  checks confirmed conversation memory resolves the pending proposal code and
  the plan request returns a pending code. The operator tested the previous
  container in Discord at 18:12–18:14 UTC; app-level replies were observed, but
  that image reproduced the missing-memory/no-code behavior. The rebuilt image
  has the fixes and is ready for retest. Room privacy remains `channel_public`.

## 2026-11-06 — Phase 6: Discord Markdown formatting

- Added deterministic Discord Markdown templates for `plan_day` and
  `reconcile` so the model cannot produce a wall of text or wrong date/time
  labels.
- `plan_day` now renders: date header, blank line, **MUST DO** bullets,
  **SHOULD DO** bullets, latest wake, horizontal rule, inline-code proposal
  code and exact approval hint.
- `reconcile` now renders separate **KEEP**, **MOVE** and **DROP** sections,
  week status/arithmetic and the same proposal footer. Move titles/dates and
  drop titles come from the domain payload.
- Approval replies are deterministic Markdown (`✅ **Approved**` / `🚫
  **Rejected**` / `⚠️ **Not applied**`).
- Added deterministic owner-clock/date normalization so "4pm Friday" uses the
  owner's reported time and the context weekday map, not the model's calendar.
- System prompt now documents Discord Markdown rules and the exact plan shape.
- Tests: **104 passed**; `ruff` clean; `mypy src` clean. Live checks produced
  the exact plan/reconcile layouts with actual task titles, 12-hour local times
  and proposal codes.

## 2026-11-06 — Phase 6 edge-case handling

- Empty day-plan requests now return a specific message instead of a generic
  validation error:
  "You don't have any tasks scheduled for {Weekday}. You can ask me to plan
  your week to add some." This covers both a model `plan_day` call and the
  deterministic fallback.
- Added a deterministic battery-clarification path: if Zasky just asked for
  battery and the owner asks what it means, reply with the exact explanation
  without calling the model.
- Replaced generic validation failures with a helpful fallback:
  "I didn't understand that. If you are trying to plan your day, try:
  '@zasky What is my plan for tomorrow? Battery medium'."
- Tests: **107 passed**; `ruff` clean; `mypy src` clean. Live check for a
  Sunday plan request returned the exact empty-schedule message.

## 2026-11-06 — Phase 6: proactive room features

- Added `alarm_dispatches` persistence and migration `6823aaca3872`.
- Added an in-process task-start alarm scheduler: approved day-plan items post
  `⏰ **Timebox Started:** ...` through Switch `post_message` once per item,
  with a five-minute restart grace and database dedupe.
- Added focus mode: the prompt supports focused co-worker help; replies stay in
  the owner's existing Switch thread via `thread_id`.
- Added deterministic Daily Briefing on `plan_day` approval: formatted room
  message plus a persistent room document. The message explains that Switch
  0.31.0 has no pin operation; manual Discord pinning remains.
- Audited Switch 0.31.0 operations: no thread creation, pin, or scheduled-event
  operation exists; no direct Discord API was added.
- Tests: **112 passed**; `ruff` clean; `mypy src` clean. Scheduler, briefing,
  thread-aware reply and approval-briefing tests pass.
- Migration applied locally; health shows schema current.

## 2026-11-07 — Phase 6 latency tuning

- Added OpenRouter `provider.sort=throughput` routing.
- Made the LLM `httpx.AsyncClient` process-lifetime with explicit keep-alive
  pooling (10 keepalive connections, 60s expiry).
- Capped model output at **600 tokens**; live smoke test returned in ~1s.
- Added an immediate `…` typing placeholder after the owner/room gate. Switch
  0.31.0 has no message edit/typing operation, so the final reply is a follow-up
  message; exact approval commands skip the placeholder.
- Tests: **113 passed**; `ruff` clean; `mypy src` clean.

## 2026-11-07 — Final repository polish and judge surface

- Moved the planning/implementation document set into `docs/`: `AGENTS.md`,
  `AI_HANDOFF.md`, `ARCHITECTURE.md`, `DEMO_VIDEO_PLAN.md`,
  `FINAL_PRE_IMPLEMENTATION_AUDIT.md`, `IMPLEMENTATION_PLAN.md`,
  `OPERATOR_INTAKE.md`, `PROJECT_SPEC.md`, `REFERENCE_ASSETS.md` and
  `ZASKY_IMPLEMENTATION_BLUEPRINT.md`. The repository root now contains only
  `README.md` plus standard deployment/project files.
- Rebuilt the root README for judges: live dashboard, 97-second demo, Discord
  invite, sandbox test path, core problem/solution, feature highlights,
  architecture, and local setup.
- Added `scripts/post_welcome_guide.py` and posted the formatted Server Guide to
  `#welcome-and-how-to-test` (message `1568706511142780949`). The guide explains
  `#zasky-control`, `#judges-sandbox`, the read-only output channels, and the
  sandbox test commands. Pin was skipped because the bot currently lacks
  `Manage Messages`; the message itself is live.
- Tests: **165 passed**; `ruff` clean; `mypy src` clean; local Markdown links
  checked with 0 broken targets.

## 2026-11-09 — Day-plan transparency

- Added deterministic day-plan payload counts: `week_pool_active_count`,
  `not_selected_count`, `selected_est_min_total` and `task_cap`.
- Added `plan_transparency_notes` for proposal and Daily Briefing templates:
  unselected week-pool count, 3-task cap (2 on low battery), the light-plan
  message at ≤90 selected minutes, and the low-battery one-MUST/one-SHOULD
  clarification.
- Updated the system prompt so plan responses cannot imply every task was
  scheduled and must preserve the application-supplied notes.
- Fixed dashboard task creation to infer the week from `scheduled_date` rather
  than always using the current week.
- Tests: **169 passed**; `ruff` clean; `mypy src` clean; live container rebuild
  and health ready.

## 2026-11-09 — Explicit day-plan override

- Added `override_limits: bool = False` to the `plan_day` tool contract.
- Default plans still enforce the battery-shaped 1 MUST / 3-task cap and now
  offer: "Reply `override limits` if you want me to schedule all of them."
- Override mode schedules every active task for that date, preserves exactly one
  MUST, and still protects fixed events. It uses a full-day scheduler that
  starts at the earliest availability time and can run past the normal window.
- Added a deterministic capacity warning when override tasks exceed the day's
  available minutes, e.g. 14 hours of tasks vs 8 hours available.
- The system prompt now states that Zasky is protective by default and may only
  enable override on an explicit owner command.
- Tests: **174 passed**; `ruff` clean; `mypy src` clean.

## Checkpoint template

```text
Date:
Phase:
Commit:
Implementation:
Tests/evidence:
Switch/Discord status:
Database/backup status:
Model/cost status:
Known issues:
Authorization:
Next task:
Blocked by:
```
