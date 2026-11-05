# AI_HANDOFF.md — Zasky Implementation State

**Last updated:** 2026-11-05  
**Project status:** Blueprint authored; implementation not started  
**Current phase:** Phase 0 — Operator Intake / Readiness  
**Next task:** Coding agent reads the complete package, inspects the existing repository without modifying it, and completes the one consolidated operator intake.

## Current state

- Product definition: documented in `PROJECT_SPEC.md`.
- MVP scope: defined; single-owner, chat-native agent.
- Architecture: fixed in `ARCHITECTURE.md`.
- Implementation sequence: fixed in `IMPLEMENTATION_PLAN.md`.
- Persistent agent instructions: `AGENTS.md`.
- Operator intake: template prepared; answers and validation evidence pending.
- Reference assets: UI reference image not applicable; no frontend in MVP.
- Demo video: plan prepared; video not yet produced.
- Product code: **not started**. No claim of a working service or deployment is made.

## Current phase record

| Field | Status |
|---|---|
| Operator intake | Pending |
| Existing repository inspected | Pending |
| Switch deployment/version verified | Pending |
| Switch agent registration status verified | Pending |
| Discord private room / bridge verified | Pending |
| Owner participant ID and room ID verified | Pending |
| OpenAI model/tool capability and spend cap verified | Pending |
| VPS, persistent disk, SSH, firewall verified | Pending |
| Owner timezone and availability supplied | Pending |
| Seed goals/commitments/week tasks supplied | Pending |
| Backup destination/restore procedure validated | Pending |
| Preview/staging authority | Pending |
| Production authority | Not granted by default |
| Current preview URL | None — no deployment performed |
| Deployed commit | None |
| Current Git commit | Not established; inspect repository |
| UI reference asset | Not applicable |
| `stageshow` skill | Not applicable; no frontend |
| Unit/integration/E2E evidence | None — implementation not started |
| Demo video | Not produced |

## Locked boundaries

- One owner and one private room.
- Switch + Discord is the intended MVP integration.
- Use current Switch WebSocket protocol and documented HTTP operations; verify version at intake.
- Exactly seven domain tools.
- SQLite, one active writer, no public product API.
- No frontend, website, dashboard, payments or external calendar/email.
- No generated tasks from goals.
- Owner approval is required before plan mutation.
- No production deployment unless the operator explicitly grants exact authority.
- No costs incurred unless within an explicit ceiling.

## Checkpoint template

Copy and update at every phase boundary:

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

If a coding-agent session ends, read `AGENTS.md`, this file and `docs/BUILD_LOG.md`; inspect Git status and the last verified commit; continue from the next incomplete task in `IMPLEMENTATION_PLAN.md`. Do not redo completed work without evidence it is invalid. Do not start Phase 1 until all critical intake items pass.
