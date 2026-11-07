# AI_HANDOFF.md — Zasky Implementation State

**Last updated:** 2026-11-07  
**Project status:** Phases 1–9 complete; VPS staging with Neon Postgres, a deployed Vercel dashboard and the Discord HQ notification layout ready to run  
**Current phase:** Post-Phase 9 cloud/dashboard upgrade — verified staging, awaiting authorized release  
**Next task:** Review and run `scripts/setup_discord.py`, add the printed channel IDs plus the bot token to the protected env, then restart Zasky.

## Current state

- Product definition: fixed in `PROJECT_SPEC.md`.
- MVP scope: fixed; single-owner, chat-native agent with an explicit operator-approved dashboard scope change.
- Architecture: fixed in `ARCHITECTURE.md`.
- Implementation sequence: fixed in `IMPLEMENTATION_PLAN.md`.
- Persistent agent instructions: `AGENTS.md`.
- Operator intake: Switch/Discord access, agent registration, owner identity,
  VPS host, Neon Postgres, OpenRouter and cost caps are verified. Room privacy
  remains an operator action.
- Product code: Phase 1 transport/echo, Phase 2 durable schema/migrations/
  recovery, Phase 3 deterministic domain/planner/tool schemas, Phase 4
  OpenRouter Chat Completions orchestration, proactive features, Neon Postgres
  migration and a Vercel-ready Next.js dashboard.
- Database schema revision: `9f4c1a7b2d30`.
- Domain tools: exactly seven strict schemas; proposal approval is deterministic.
- Staging model: `openai/gpt-4o-mini` via OpenRouter Chat Completions; pricing
  `$0.15/$0.60` per 1M; `$20`/month and `100` requests/day caps.
- Cloud state: Neon Postgres is authoritative; SQLite remains the local test path.
- Dashboard: `frontend/` Next.js app with Today's Plan, All Tasks and
  Reconciliation History; token-gated API on port `8100`; server-side proxy.
- Demo video: produced — `artifacts/demo/zasky-demo.mp4` (97s, local transcript, honestly labeled).

## Current phase record

| Field | Status |
|---|---|
| Operator intake | Complete for staging scope — see `OPERATOR_INTAKE.md` |
| Existing repository inspected | Yes — application, tests, migrations and docs are present |
| Switch deployment/version verified | Yes — VPS Switch **0.31.0** |
| Switch agent registration status verified | Yes — `zasky` registered and connected |
| Discord private room / bridge verified | Bridge/room yes; room privacy still **needs operator action** (`channel_public`) |
| Owner participant ID and room ID verified | Yes — exact values in protected env only |
| OpenRouter model/tool capability and spend cap verified | Yes — live prose + tool calls; $20/$100 caps |
| VPS, persistent disk, SSH verified | Yes — Docker Compose on the Switch VPS |
| Neon Postgres verified | Yes — schema `9f4c1a7b2d30`, synthetic seed loaded |
| Owner timezone and availability supplied | Yes — Africa/Lagos; daily 09:00–21:00 |
| Seed goals/commitments/week tasks supplied | Yes — synthetic demo plan plus dashboard-today/reconcile seed |
| Backup destination/restore procedure validated | Yes — manual SQLite online backup + restore drill; Neon is provider-managed |
| Preview/staging authority | Verified VPS staging; Vercel deployment pending operator |
| Production authority | Not granted |
| Current preview URL | VPS dashboard API `http://VPS_IP:8100`; Vercel URL pending |
| Deployed commit | `b52cfdb` runtime; Discord routing pending operator channel IDs |
| Current Git commit | `562636a` |
| UI reference asset | Not applicable; dashboard has no supplied reference image |
| `stageshow` skill | Not used |
| Unit/integration/E2E evidence | 136 tests pass; live model/tool E2E; live Discord round-trip; live dashboard API read/write; Discord notifier routing tests |
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
- Tests: **113 passed**; `ruff check .` clean; `mypy src` clean.

## Phase 9 evidence

- Final tests: **113 passed**; `ruff check .` clean; `mypy src` clean.
- Secret scan: no API key, bearer token or real owner/room ID in tracked files.
- Final backup/restore: integrity `ok`, 0 foreign-key violations, 17 tables,
  3 goals, 3 commitments, 6 tasks, 2 day-plan items, schema `b23394c5a105`.
- Staging health: ready, Switch connected, schema current, model configured.
- Demo: `artifacts/demo/zasky-demo.mp4` (97.19s, 1280×720, H.264/AAC,
  local TTS, real model/tool transcript, synthetic data).
- Final release state: **verified-staging-awaiting-authorized-release**.
- No production deployment was performed.

## Phase 4 chat-context follow-up

- Last eight room messages are included as bounded, untrusted context via
  Switch `read_context`; raw room text is not persisted in SQLite.
- Plan requests with a date produce a `plan_day` pending proposal and code,
  including a deterministic fallback if the model chooses `query`.
- Plan/reconcile display blocks are deterministic from tool payloads.
- Conversational approvals are refused deterministically when a proposal is
  pending; the reply names the exact `approve ZK-XXXX` command.
- Tests: **113 passed**; `ruff` clean; `mypy src` clean.

## Phase 6 formatting follow-up

- Plan and reconcile responses are now generated by deterministic Discord
  Markdown templates, not model prose. They include bold headers, bullets,
  double line breaks, inline-code proposal codes, exact approval hints and
  separate KEEP/MOVE/DROP sections.
- Approval replies use deterministic Markdown.
- Owner-reported clock times and weekday references are normalized
  deterministically; the model's calendar cannot override them.
- Tests: **113 passed**; `ruff` clean; `mypy src` clean.

## Phase 6 edge-case follow-up

- Empty day-plan requests return the specific "You don't have any tasks
  scheduled for {Weekday}..." message, including when the model calls
  `plan_day` and when the deterministic fallback runs.
- Battery clarification is handled deterministically when the owner asks what
  "battery" means after a battery question.
- Generic validation failures now return a helpful example command instead of
  "I couldn't validate that request."
- Tests: **113 passed**; `ruff` clean; `mypy src` clean.

## Phase 6 proactive features

- Task-start alarms are sent through Switch at approved item start with
  `alarm_dispatches` dedupe and five-minute restart grace.
- Plan approval posts a deterministic Daily Briefing and creates a room document.
- Focus mode is prompt-driven; replies stay in an existing thread via `thread_id`.
- Switch 0.31.0 has no create-thread, pin, or scheduled-event operation. No
  direct Discord API was added. Daily Briefing pinning and thread creation remain
  manual/provider-limited.
- Tests: **113 passed**; `ruff` clean; `mypy src` clean.

## Phase 6 latency tuning

- OpenRouter uses `provider.sort=throughput`.
- LLM HTTP client is process-lifetime with keep-alive pooling.
- Output cap is 600 tokens.
- A `…` placeholder is posted after the security gate and before the model call.
  Switch 0.31.0 has no edit/typing operation, so the final reply follows as a
  second message; approval commands skip the placeholder.
- Tests: **113 passed**; `ruff` clean; `mypy src` clean.

## Postgres + dashboard upgrade (2026-11-07)

- Added `asyncpg`, URL normalization for Neon (`sslmode`/`channel_binding`), and
  SQLite/Postgres engine branching. Postgres schema is owned by Alembic; the app
  does not run `create_all` on Postgres.
- Migrated Neon through `b23394c5a105` → `6823aaca3872` →
  `9f4c1a7b2d30`. The last migration widens Switch sequence columns to
  `BIGINT` after Switch delivered `4294967315`, which exceeds signed 32-bit.
- Disabled the asyncpg prepared-statement cache for Neon/PgBouncer compatibility.
- Added an authenticated dashboard API on `0.0.0.0:8100`:
  `today`, `tasks`, `tasks/{id}/complete`, `reconciliations`. Every route
  requires the `DASHBOARD_API_KEY` bearer token.
- Added `frontend/`, a Next.js 16 dark-mode dashboard with Today's Plan, All
  Tasks (interactive completion) and Reconciliation History. The browser calls a
  same-origin Next.js proxy; `ZASKY_DASHBOARD_TOKEN` stays server-side.
- Added `scripts/seed_dashboard_demo.py` for an idempotent today plan and one
  reconciliation history record. Synthetic data only.
- Live verification: dashboard API returned `has_plan: true`, MUST/SHOULD items
  and one reconciliation entry; a completion POST changed the task to
  `completed` in Neon and updated counts. The Next.js production server proxy
  returned the same payload on `localhost:3100`.
- Tests: **124 passed**; `ruff check .` clean; `mypy src` clean; frontend
  `npm run build` clean.
- Port `8000` was requested for the dashboard but is occupied by Switch; the
  dashboard API uses `8100`. The exact optional firewall command is
  `sudo ufw allow 8100/tcp`.

## Discord HQ layout and notification routing (2026-11-07)

- Added `scripts/setup_discord.py`, a one-off Discord REST setup script. It
  creates the `Zasky HQ` category and `#zasky-control`, `#daily-briefings`,
  `#reconcile-alerts`, `#ai-workspace`, `#dashboard-sync`.
- The script is idempotent, refuses to move same-named channels outside the
  category, writes `data/discord_channels.json` (mode `0600`) and prints the
  backend env lines. It was **not executed**; it was syntax-checked only.
- Added a narrow outbound `DiscordNotifier` for the three routing channels.
  Chat remains Switch; no inbound Discord Gateway connection and no model tool.
- Approved `plan_day` → `#daily-briefings`; approved `reconcile` →
  `#reconcile-alerts`; Execution Sub-Agent results →
  `POST /api/internal/execution-results` → `#ai-workspace`.
- Discord messages cap at 2,000 characters and disable all mention parsing.
- Added `docs/DISCORD_SETUP.md`, `DISCORD_*` settings and tests for routing,
  unconfigured fallback, 429 retry, permission failure and truncation.
- Tests: **136 passed**; `ruff check .` clean; `mypy src` clean.
- The setup script remains unexecuted by design. The operator must provide
  `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` in the protected env before running.

## Known issues and blockers

1. **Room privacy:** Switch reports the room as `channel_public`. The application
   enforces exact owner and room checks, but `@everyone → View Channel = deny`
   must be applied before real personal use or a public demo.
2. **Discord channel IDs:** the setup script creates the channels, but the
   backend routes stay on fallback until the operator adds `DISCORD_BOT_TOKEN`
   and the printed channel IDs to the protected env and restarts Zasky.
3. **Plain HTTP:** the dashboard API is reachable on port 8100 over HTTP for the
   hackathon. The bearer token crosses the network; use HTTPS and rotate the
   token for real personal data.
4. **Live Discord test is not the same as the local transcript demo.** The
   transcript uses the real model/tools/domain but not the Discord UI; this is
   documented in the video and production notes.
5. **Production deployment authority is not granted.** Final state is
   `verified-staging-awaiting-authorized-release`.
6. **Switch cursor reset:** the failed 32-bit insert left no connection-state
   row; the client restarted from zero after the BIGINT migration. Event claims
   still deduplicate replay.

## Intentional hackathon deferrals

These are recorded before further code and must not be silently changed:

1. **VPS + Neon staging demonstrated.** Production release and public ingress
   approval remain separate; the Vercel deployment is the operator's final step.
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
