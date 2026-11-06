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
