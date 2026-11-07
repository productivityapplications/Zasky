# Testing Strategy

## Unit tests
Test pure domain behavior without Switch or a model:
- Goal limit (maximum five active per year), evidence requirement and duplicate title.
- Commitment validation, estimate/deadline/consequence.
- Week start/date validation and week-pool provenance.
- Capacity budget at 60%, 65%, 70%; slack calculation; fixed-event overlaps; buffers.
- Daily selection from active week tasks only; exactly one must; max three; low-battery rule.
- Backplan/latest-wake arithmetic, timezone and daylight-saving edge cases.
- Reconcile outcomes: within-day recovery, later-in-week move, insufficient capacity, expired week.
- Task park/resume/completion state machine.
- Proposal TTL, code validation, stale revision, duplicate approval and rejection.
- Deadline at-risk calculation and uncertainty reporting.
- Prompt/context builder redaction and truncation.

## Integration tests
- SQLite migrations, constraints, foreign keys and transaction rollback.
- Proposal approval is atomic under concurrent requests.
- Event dedupe ledger prevents repeat tool execution.
- Switch WebSocket heartbeat, reconnect, cursor/generation resume, `gap`, `taken_over`.
- Switch HTTP context/post operations; retry only transient failures.
- OpenRouter Chat Completions schema and tool call parsing; model timeout/quota/
  invalid output.
- Spend ledger and daily/monthly hard stops.
- Backup, restore, integrity check and migration compatibility.
- Scheduler restart grace period and reminder uniqueness.
- Dashboard bearer auth, CORS preflight, today/tasks/reconciliation payloads,
  explicit task completion and unknown-task/status errors.

## End-to-end tests
1. Add year goal → add monthly commitment → create weekly tasks → approve week.
2. Plan day from week pool → inspect latest wake/backplan → approve.
3. Report disruption → reconcile proposal → inspect week status → approve.
4. Park task with resume note → resume → plan on a later date → complete.
5. Query today, week, month and deadline ledger.
6. Non-owner and wrong-room requests do not receive private data or invoke model.
7. Duplicate Switch event and repeated approval produce no duplicate mutation.
8. Switch restarts/outage and reconnects safely.
9. Model budget reached: no further paid model call is made.

## Security tests
- Non-owner sender ID, spoofed display name, wrong room, unaddressed event.
- Prompt injection asking for system prompt, keys, database, another user's data or arbitrary tool.
- Forged tool arguments with unknown IDs, invented title, extra fields, oversized string/list, negative minutes.
- Approval phrase "looks good" and ambiguous "yes" do not approve.
- Expired/stale proposal, wrong code, replayed approval, simultaneous approvals.
- SQL injection strings treated as data.
- Oversized messages and rate limit.
- Secrets absent from logs, prompt, database, audit and demo.
- Host ports/firewall expose no public DB or Zasky API.

## Final staging evidence — 2026-11-07

```bash
uv run pytest -q                 # 124 passed
uv run ruff check .              # clean
uv run mypy src                  # clean
cd frontend && npm run build     # Next.js production build succeeds
docker compose up -d --build     # container healthy
curl -sS http://127.0.0.1:8099/health/ready
# {"status":"ready","database":"ok","switch":"connected","schema":"current","model":"configured"}
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env status
# database: 9f4c1a7b2d30
# head:     9f4c1a7b2d30
```

Postgres/dashboard evidence:

- Alembic migrated the Neon database through `9f4c1a7b2d30`.
- Synthetic seed data exists in Neon; a live API check returned
  `has_plan: true`, MUST/SHOULD items and one reconciliation history entry.
- A dashboard `POST /api/dashboard/tasks/{id}/complete` changed the task to
  `completed` in Postgres and updated the `/tasks` counts.
- The Next.js server proxy returned the same live payload on a local production
  server; the browser receives no dashboard token.
- Postgres sequence columns were widened to `BIGINT` after Switch delivered a
  sequence above signed 32-bit range.
- The asyncpg statement cache is disabled for Neon/PgBouncer compatibility.

The automated suite covers event parsing, owner/room/addressed filtering,
duplicate sequences, heartbeat pong, gap context reread, reconnect cursor/
generation, `taken_over`, database state/ledger behavior, configuration
validation, health responses, the single-writer lock, owner seeding, scope
revisions, audit writes, migration upgrade/check/downgrade, append-only audit
triggers, online backup, restore integrity, foreign-key checks, retention, the
seven strict tool schemas, goal/commitment limits, capacity and slack, week
placement, day-plan one-must/three-max, low battery, backplan, fixed-event
avoidance, proposal stale/expired/reject/duplicate approval, concurrent
approval, park/resume/complete, deadline risk, reconcile arithmetic, bounded
tool-loop validation, cost/request caps, hallucinated-code rejection,
unauthorized events never reaching the model handler, exact Discord Markdown
templates, owner-clock/date normalization, conversational-approval refusal,
empty-schedule messaging, battery clarification, helpful fallback errors,
task-start alarm dedupe/grace, Daily Briefing formatting/persistence,
thread-aware replies, throughput routing, 600-token cap and typing placeholder
ordering.

Live staging evidence (2026-11-06):

- OpenRouter `openai/gpt-4o-mini` returned normal prose and valid tool calls.
- A live goal → commitment → week placement → day plan chain produced and
  approved real proposals. The model omitted redundant month fields once; the
  deterministic argument normalizer filled them from the owner's deadline.
- A live query → reconcile → approve → query chain produced the demo transcript
  in `artifacts/demo/transcript.txt`.
- Prompt-injection probe asking for system prompt/API key/room ID was refused.
- The local transcript demo is rendered in `artifacts/demo/zasky-demo.mp4`
  (97s) and explicitly labeled not a Discord screen capture.

Still pending before real personal use: confirmation that the Discord room is
`channel_private` (or that `@everyone` view access is denied). The owner
round-trip in the room has been observed; the dashboard API is token-gated and
was exercised from the VPS and through the Next.js proxy.

## Acceptance / release gate
- All required unit and integration suites pass.
- All critical E2E paths pass against isolated Switch + Discord.
- No open critical/high severity security issue.
- Database restore succeeds and integrity checks pass.
- Cost limits and event rate limits are tested.
- `AI_HANDOFF.md` records exact commit, environment, test evidence, known limitations and authorization.
