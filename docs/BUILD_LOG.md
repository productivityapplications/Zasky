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
