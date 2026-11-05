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

## Acceptance / release gate
- All required unit and integration suites pass.
- All critical E2E paths pass against isolated Switch + Discord.
- No open critical/high severity security issue.
- Database restore succeeds and integrity checks pass.
- Cost limits and event rate limits are tested.
- `AI_HANDOFF.md` records exact commit, environment, test evidence, known limitations and authorization.
