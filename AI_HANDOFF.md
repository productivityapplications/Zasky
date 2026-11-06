# AI_HANDOFF.md — Zasky Implementation State

**Last updated:** 2026-11-06  
**Project status:** Phases 1–2 implemented; live owner round-trip pending  
**Current phase:** Phase 2 complete — durable schema and recovery foundation  
**Next task:** Live Discord round-trip evidence, then Phase 3 domain services and planner.

## Current state

- Product definition: fixed in `PROJECT_SPEC.md`.
- MVP scope: fixed; single-owner, chat-native agent.
- Architecture: fixed in `ARCHITECTURE.md`.
- Implementation sequence: fixed in `IMPLEMENTATION_PLAN.md`.
- Persistent agent instructions: `AGENTS.md`.
- Operator intake: partially complete. Switch/Discord access, agent registration,
  owner identity, local host and cost caps are verified. OpenAI access, planning
  inputs, demo data and the room privacy setting remain open.
- Product code: Phase 1 transport/echo and Phase 2 durable schema/migrations/
  recovery foundation. No domain tools or planner yet.
- Database schema revision: `b23394c5a105`.
- Reference assets: UI reference image not applicable; no frontend in MVP.
- Demo video: not produced.

## Current phase record

| Field | Status |
|---|---|
| Operator intake | Partial — see `OPERATOR_INTAKE.md` |
| Existing repository inspected | Yes — docs-only, clean `main` |
| Switch deployment/version verified | Yes — local Switch **0.31.0** |
| Switch agent registration status verified | Yes — `zasky` registered |
| Discord private room / bridge verified | Bridge/room yes; room privacy **blocked** (`channel_public`) |
| Owner participant ID and room ID verified | Yes — exact values in protected env only |
| OpenAI model/tool capability and spend cap verified | Spend cap recorded; key/model capability pending |
| VPS, persistent disk, SSH, firewall verified | Deferred by hackathon scope; local staging only |
| Owner timezone and availability supplied | Pending; provisional `Africa/Lagos` seeded |
| Seed goals/commitments/week tasks supplied | Pending (demo content) |
| Backup destination/restore procedure validated | Yes — manual online backup + restore drill |
| Preview/staging authority | Local staging only |
| Production authority | Not granted |
| Current preview URL | None — local container only |
| Deployed commit | Phase 2 checkpoint pending |
| Current Git commit | Phase 2 checkpoint pending |
| UI reference asset | Not applicable |
| `stageshow` skill | Not applicable; no frontend |
| Unit/integration/E2E evidence | 46 tests pass; live owner round-trip pending |
| Demo video | Not produced |

## Phase 1 evidence

- Local Switch 0.31.0 Compose stack runs with the `collab` and `gateway`
  profiles. Postgres and Gateway are bound to localhost only.
- Zasky is a registered custom agent in the configured room, owned by the linked
  Discord owner account. Exact IDs are redacted here and held only in
  `/root/Zasky-secrets/zasky.env` (mode `0600`).
- The temporary registration key was used once and revoked.
- `/health/live` returns `200`; the current `/health/ready` returns
  `{"status":"ready","database":"ok","switch":"connected","schema":"current"}`.
- Docker image builds. Container runs as uid `10001`, with a read-only root
  filesystem, `CAP_DROP=ALL`, `no-new-privileges`, and a persistent `./data`
  bind mount.
- Tests: 46 passed; `ruff` clean; `mypy src` clean.
- The client accepts the deployed Switch envelope (`event`/`data`), answers
  pings, resumes with cursor/generation, rereads context after `gap`, stops on
  `taken_over`, deduplicates event sequences and posts one deterministic echo.
- **Pending acceptance evidence:** an actual owner message in the Discord room
  and Zasky's reply in the same room.

## Phase 2 evidence

- 16 domain/operational tables plus `alembic_version` created by migration
  `b23394c5a105`.
- Alembic upgrade, `alembic check`, downgrade-to-base and re-upgrade all passed.
- `audit_events` has database triggers that reject update and delete.
- `owner_config` is seeded once from validated settings; singleton and capacity/
  daily-limit checks are enforced.
- Manual online backup produced `zasky-20261106T100821Z.db` with SHA-256 sidecar.
- Restore to `/tmp/zasky-restore-test.db` passed `PRAGMA integrity_check`
  (`ok`), `PRAGMA foreign_key_check` (0 violations), 17 tables and a present
  owner config.
- `zasky-maintenance` supports migrate/status/backup/restore/prune locally.
- Encrypted backup automation is intentionally deferred; the manual restore
  proof is the Phase 2 acceptance evidence.

## Known issues and blockers

1. **Room privacy:** Switch reports the room as `channel_public`. The application
   still enforces exact owner and room checks, but Discord channel visibility must
   be restricted before Phase 1 acceptance and any demo. Apply
   `@everyone → View Channel = deny` or replace the room with a private one.
2. **OpenAI:** key, verified Responses model/tool capability and provider data
   acceptance are still pending. Phases 1–3 do not need them.
3. **Planning inputs:** timezone confirmation, availability, fixed events,
   prep/commute/transition buffers and week-start confirmation are pending.
   Synthetic demo inputs are acceptable if explicitly approved.
4. **Demo:** synthetic seed content, pronunciation, output permission and a
   Discord capture path are pending.
5. **Live round-trip:** the transport is ready and the agent is in the room, but
   no owner message has been observed by this running container.
6. **Phase 1 DB reset:** the Phase 1 operations-only DB was backed up and then
   replaced by a fresh migrated Phase 2 DB. No domain data existed. The Switch
   cursor will resume from the server's current position.

## Intentional hackathon deferrals

These are recorded before further code and must not be silently changed:

1. **VPS deployment deferred.** Local staging only. Cloud architecture is
   documented in the writeup, not demonstrated.
2. **Encrypted backup automation deferred.** Manual SQLite online backup and
   restore are enough for the demo; encrypted backup is documented as
   production-only.
3. **Full micro-USD cost ledger simplified.** Hard monthly spend cap enforced
   (default **$20**), daily request cap enforced (default **100**), no reservation
   ledger in Phase 1.
4. **Production deployment authority not granted.** Final state is
   `verified-staging-awaiting-authorized-release`.

## Locked boundaries

- One owner and one private room.
- Switch + Discord is the intended MVP integration.
- Use current Switch WebSocket protocol and documented HTTP operations; deployed
  protocol verified against Switch 0.31.0.
- Exactly seven domain tools in later phases.
- SQLite, one active writer, no public product API.
- No frontend, website, dashboard, payments or external calendar/email.
- No generated tasks from goals.
- Owner approval required before plan mutation.
- No production deployment without explicit authority.
- No costs incurred outside the recorded ceiling.

## Checkpoint template

```text
Current phase:
Completed:
Tests and evidence:
Switch connection status:
Protected test/staging URL (if any):
Deployed commit / image digest:
Git commit:
Operator intake status:
Reference asset status (N/A for MVP):
UI skill status (N/A for MVP):
Documentation status:
Backup and restore status:
Demo video status:
Known issues:
Spend to date / approved ceiling:
Authorization boundaries:
Next task:
Blocked by:
```

## Resume instruction

If a coding-agent session ends, read `AGENTS.md`, this file and
`docs/BUILD_LOG.md`; inspect Git status and the last verified commit; continue
from the next incomplete task in `IMPLEMENTATION_PLAN.md`. Do not redo completed
work without evidence it is invalid. Do not claim Phase 1 acceptance without a
real owner message and a private room.
