# AI_HANDOFF.md — Zasky Implementation State

**Last updated:** 2026-11-06  
**Project status:** Phases 1–9 complete; verified staging awaiting release; live Discord app-level round-trip pending  
**Current phase:** Phase 9 complete — final regression and release checklist  
**Next task:** Operator fixes room privacy and sends one live Discord test message; production release remains unauthorized and steps are documented.

## Current state

- Product definition: fixed in `PROJECT_SPEC.md`.
- MVP scope: fixed; single-owner, chat-native agent.
- Architecture: fixed in `ARCHITECTURE.md`.
- Implementation sequence: fixed in `IMPLEMENTATION_PLAN.md`.
- Persistent agent instructions: `AGENTS.md`.
- Operator intake: partially complete. Switch/Discord access, agent registration,
  owner identity, local host and cost caps are verified. OpenAI access, planning
  inputs, demo data and the room privacy setting remain open.
- Product code: Phase 1 transport/echo, Phase 2 durable schema/migrations/
  recovery, Phase 3 deterministic domain/planner/tool schemas, and Phase 4
  OpenRouter Chat Completions orchestration. Live model calls are enabled with
  hard caps.
- Database schema revision: `b23394c5a105`.
- Domain tools: exactly seven strict schemas; proposal approval is deterministic.
- Staging model: `openai/gpt-4o-mini` via OpenRouter Chat Completions; pricing
  `$0.15/$0.60` per 1M; `$20`/month and `100` requests/day caps.
- Reference assets: UI reference image not applicable; no frontend in MVP.
- Demo video: produced — `artifacts/demo/zasky-demo.mp4` (97s, local transcript, honestly labeled).

## Current phase record

| Field | Status |
|---|---|
| Operator intake | Partial — see `OPERATOR_INTAKE.md` |
| Existing repository inspected | Yes — docs-only, clean `main` |
| Switch deployment/version verified | Yes — local Switch **0.31.0** |
| Switch agent registration status verified | Yes — `zasky` registered |
| Discord private room / bridge verified | Bridge/room yes; room privacy **blocked** (`channel_public`) |
| Owner participant ID and room ID verified | Yes — exact values in protected env only |
| OpenAI/OpenRouter model/tool capability and spend cap verified | Yes — live prose + tool calls; $20/$100 caps |
| VPS, persistent disk, SSH, firewall verified | Deferred by hackathon scope; local staging only |
| Owner timezone and availability supplied | Yes — Africa/Lagos; daily 09:00–21:00 |
| Seed goals/commitments/week tasks supplied | Yes — synthetic demo plan seeded |
| Backup destination/restore procedure validated | Yes — manual online backup + restore drill |
| Preview/staging authority | Local staging only; verified |
| Production authority | Not granted |
| Current preview URL | None — local container only |
| Deployed commit | `d41a6c2` (Phase 4–9 code/demo checkpoint) |
| Current Git commit | `d41a6c2` plus docs checkpoint |
| UI reference asset | Not applicable |
| `stageshow` skill | Not applicable; no frontend |
| Unit/integration/E2E evidence | 95 tests pass; live model/tool E2E; app-level Discord message pending |
| Demo video | Produced — `artifacts/demo/zasky-demo.mp4` (97s, local transcript) |

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
- Tests: 78 passed; `ruff` clean; `mypy src` clean.
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

## Phase 3 evidence

- Seven strict tool schemas are defined and tested: `add_commitment`,
  `place_week`, `plan_day`, `reconcile`, `park_task`, `complete_task`, `query`.
  Unknown fields are rejected.
- Deterministic capacity/scheduling/backplan/feasibility code is in
  `src/zasky/planner/core.py`; no model performs arithmetic.
- Proposal lifecycle supports record/week/day/reconcile proposals, TTLs, codes,
  expected-scope revisions, stale/expired/rejected handling and idempotent
  duplicate approval.
- Owner-authored goals/commitments/fixed events, five-goal cap, duplicate-title
  checks, immutable fixed events and commitment-cancellation cascades are
  enforced.
- Week placement enforces capacity, ad hoc provenance and in-week dates.
- Day plans use only active week-pool tasks for the requested date, have exactly
  one must and at most three items, shape low battery, avoid fixed events and
  calculate latest wake.
- Reconcile keeps/moves existing work within the week and reports week holds or
  at risk with arithmetic.
- Park/resume/complete, bounded queries and deadline risk are implemented.
- Tests: **78 passed**; `ruff` clean; `mypy src` clean.

## Phase 4–8 evidence

- OpenRouter Chat Completions is live with `openai/gpt-4o-mini`; live prose and
  tool-call smoke tests passed. A live goal → commitment → week placement → day
  plan chain produced real proposals and approvals.
- The model is bounded to five tool cycles and two proposal-producing calls per
  message. Unknown fields, invalid JSON, hallucinated proposal codes and
  non-explicit status actions are rejected.
- Cost guard: 7 live demo requests cost **$0.003779** in the isolated demo DB;
  staging has $0 model spend. Hard caps remain $20/month and 100 requests/day.
- Prompt-injection probe asking for system prompt/API key/room ID was refused.
- Demo transcript (`artifacts/demo/transcript.txt`) is real model/tool output:
  Friday plan → disruption → reconcile proposal → deterministic approval →
  remaining-week query. It uses synthetic data only.
- Video `artifacts/demo/zasky-demo.mp4` is 97 seconds, H.264/AAC, 1280×720, with
  local `espeak-ng` narration. It is explicitly labeled a local
  protocol/transcript demo, not a Discord screen capture.
- Tests: **95 passed**; `ruff check .` clean; `mypy src` clean.

## Phase 9 evidence

- Final tests: **95 passed**; `ruff check .` clean; `mypy src` clean.
- Secret scan: no API key, bearer token or real owner/room ID in tracked files.
- Final backup/restore: integrity `ok`, 0 foreign-key violations, 17 tables,
  3 goals, 3 commitments, 6 tasks, 2 day-plan items, schema `b23394c5a105`.
- Staging health: ready, Switch connected, schema current, model configured.
- Demo: `artifacts/demo/zasky-demo.mp4` (97.19s, 1280×720, H.264/AAC,
  local TTS, real model/tool transcript, synthetic data).
- Final release state: **verified-staging-awaiting-authorized-release**.
- No production deployment was performed.

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
7. **App-level Discord round-trip:** the user reports an initial greeting
   exchange, but this running container has not logged an owner message through
   the full app path. Please send one test message after the room privacy fix.
8. **Live Discord test is not the same as the local transcript demo.** The
   transcript uses the real model/tools/domain but not the Discord UI; this is
   documented in the video and production notes.

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
