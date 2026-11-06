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
- OpenAI Responses API schema and tool call parsing; model timeout/quota/invalid output.
- Spend ledger and daily/monthly hard stops.
- Backup, restore, integrity check and migration compatibility.
- Scheduler restart grace period and reminder uniqueness.

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

## Phase 1–2 evidence — 2026-11-06

```bash
uv run pytest -q                 # 95 passed
uv run ruff check .              # clean
uv run mypy src                  # clean
docker build -t zasky:phase1 .   # success
docker compose up -d             # container healthy
curl -sS http://127.0.0.1:8099/health/ready
# {"status":"ready","database":"ok","switch":"connected","schema":"current"}
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env status
# database: b23394c5a105
# head:     b23394c5a105
```

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
tool-loop validation, cost/request caps, hallucinated-code rejection and
unauthorized events never reaching the model handler.

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

Still pending for Phase 1 acceptance: one real owner message in the private
Discord room and a reply in that room, plus confirmation that the room is
`channel_private` (or that `@everyone` view access is denied).

## Acceptance / release gate
- All required unit and integration suites pass.
- All critical E2E paths pass against isolated Switch + Discord.
- No open critical/high severity security issue.
- Database restore succeeds and integrity checks pass.
- Cost limits and event rate limits are tested.
- `AI_HANDOFF.md` records exact commit, environment, test evidence, known limitations and authorization.
