# AI_HANDOFF.md — Zasky Implementation State

**Last updated:** 2026-11-06  
**Project status:** Phase 1 implemented and running in local staging; live owner round-trip evidence pending  
**Current phase:** Phase 1 — Switch-connected chat shell  
**Next task:** Observe one owner message in the Discord room, fix the room's `channel_public` privacy setting, then start Phase 2.

## Current state

- Product definition: fixed in `PROJECT_SPEC.md`.
- MVP scope: fixed; single-owner, chat-native agent.
- Architecture: fixed in `ARCHITECTURE.md`.
- Implementation sequence: fixed in `IMPLEMENTATION_PLAN.md`.
- Persistent agent instructions: `AGENTS.md`.
- Operator intake: partially complete. Switch/Discord access, agent registration,
  owner identity, local host and cost caps are verified. OpenAI access, planning
  inputs, demo data and some planning defaults remain open.
- Product code: Phase 1 only. No domain tools, planner, model calls or planning
  data yet.
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
| Owner timezone and availability supplied | Pending |
| Seed goals/commitments/week tasks supplied | Pending (demo content) |
| Backup destination/restore procedure validated | Not yet — Phase 2 |
| Preview/staging authority | Local staging only |
| Production authority | Not granted |
| Current preview URL | None — local process/container only |
| Deployed commit | Not yet — Phase 1 checkpoint pending |
| Current Git commit | Pending commit |
| UI reference asset | Not applicable |
| `stageshow` skill | Not applicable; no frontend |
| Unit/integration/E2E evidence | 33 tests pass; live owner round-trip pending |
| Demo video | Not produced |

## Phase 1 evidence

- Local Switch 0.31.0 Compose stack is running with the `collab` and `gateway`
  profiles. Postgres and Gateway are bound to localhost only.
- Zasky is a registered custom agent in the configured room, owned by the linked
  Discord owner account. Exact IDs are redacted here and held only in
  `/root/Zasky-secrets/zasky.env` (mode `0600`).
- The temporary registration key was used once and revoked.
- `/health/live` returns `200`; `/health/ready` returns
  `{"status":"ready","database":"ok","switch":"connected"}`.
- Docker image builds. Container runs as uid `10001`, with a read-only root
  filesystem, `CAP_DROP=ALL`, `no-new-privileges`, and a persistent `./data`
  bind mount.
- Tests: `33 passed`; `ruff check .` clean; `mypy src` clean.
- The client accepts the deployed Switch envelope (`event`/`data`), answers
  pings, resumes with cursor/generation, rereads context after `gap`, stops on
  `taken_over`, deduplicates event sequences and posts one deterministic echo.
- **Pending acceptance evidence:** an actual owner message in the Discord room
  and Zasky's reply in the same room.

## Known issues and blockers

1. **Room privacy:** Switch reports the room as `channel_public`. The application
   still enforces exact owner and room checks, but Discord channel visibility must
   be restricted before Phase 1 acceptance and any demo. Apply
   `@everyone → View Channel = deny` or replace the room with a private one.
2. **OpenAI:** key, verified Responses model/tool capability and provider data
   acceptance are still pending. Phase 1 does not need them.
3. **Planning inputs:** timezone confirmation, availability, fixed events,
   prep/commute/transition buffers and week-start confirmation are pending.
   Synthetic demo inputs are acceptable if explicitly approved.
4. **Demo:** synthetic seed content, pronunciation, output permission and a
   Discord capture path are pending.
5. **Backup:** Phase 2 will implement and prove a manual online SQLite backup and
   restore drill. Encrypted backup automation is deferred to production scope.

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
