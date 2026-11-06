# Zasky Build Log

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
