# Zasky — Database Operations Map

All writes are owner-scoped and performed through domain services. The LLM never writes SQL. Each multi-row operation is atomic and appends an audit event in the same transaction unless noted.

| Owner action | Read/validate | Database operations | Transaction/idempotency behavior |
|---|---|---|---|
| Create year goal | Owner + room; year/title/evidence; max-five rule; duplicate normalized title | `INSERT year_goals`; `INSERT audit_events` | One transaction; rollback if max-five/unique constraint fails |
| Update/achieve/retire goal | Load exact goal ID; validate allowed transition | `UPDATE year_goals`; `INSERT audit_events` | One transaction; goal deletion is not used |
| Create month commitment | Validate title/month/estimate, optional active goal FK; monthly budget | `INSERT month_commitments`; `INSERT audit_events` | One transaction; no downstream tasks auto-created |
| Update/cancel commitment | Load exact ID; validate status transition; review linked placements | `UPDATE month_commitments`; optionally mark future placements as needing owner review; audit | One transaction; do not delete task history |
| Add/update fixed event | Validate explicit offset and end after start; check event ID for update | `INSERT/UPDATE fixed_events`; `INSERT audit_events` | Owner explicitly requests update/cancel; planner never does |
| Create weekly placement proposal | Validate owner-authored title provenance, commitment/ad hoc rule, estimate/date; compute budget | `INSERT pending_proposals` only | No planning state changes before approval |
| Approve weekly placement | Verify owner/room/code/TTL/revision; re-check availability/events and all items | `INSERT week_placements`; `INSERT week_tasks`; `UPDATE pending_proposals`; `UPDATE scope revision`; `INSERT audit_events` | Single `BEGIN IMMEDIATE` transaction; unique constraints prevent duplicates; rollback all on any failure |
| Create day-plan proposal | Read active tasks assigned to date; battery; fixed events; schedule/backplan | `INSERT pending_proposals` | No day plan mutation |
| Approve day plan | Verify proposal; re-read pool/revision; verify exactly one must and <=3; ensure no overlaps | `UPDATE prior day_plans.status='replaced'`; `INSERT day_plans`; `INSERT day_plan_items`; `UPDATE proposal`; `INSERT audit_events` | Single transaction; unique `(day_plan_id,task_id)`; repeated approval idempotent |
| Reconcile proposal | Read current day plan, task statuses, week budget, fixed events; derive move/park/keep/drop | `INSERT pending_proposals` | No task/date/day changes yet |
| Approve reconcile | Revalidate base revision, dates, pool and capacity; apply all changes | `UPDATE week_tasks.scheduled_date` for moved tasks; `UPDATE week_tasks.status/resume_note` if parked; replace current day plan and items; resolve proposal; audit | Single transaction. Drop is proposal-only and leaves task active in week pool. No automatic cross-week move |
| Park task | Exact task ID; task is active; resume note required | `UPDATE week_tasks.status='parked', resume_note=...`; `INSERT audit_events` | One transaction; idempotent if already parked with same note |
| Resume task | Task parked; explicit owner request | `UPDATE week_tasks.status='active'`; clear/retain resume note per owner decision; `INSERT audit_events` | One transaction; it remains out of a day plan until assigned a valid date |
| Complete task | Exact, unambiguous task; not already completed | `UPDATE week_tasks.status='completed', completed_at, actual_min`; `UPDATE day_plan_items.outcome` where applicable; audit | One transaction; repeated completion returns prior result |
| Query | Owner + room; validate state/horizon; bounded result size | `SELECT` only from indexed tables | Read-only; no state mutation |
| Process inbound Switch event | Validate connection, room, sender, addressed flag; compare event sequence | Insert `processed_switch_events`; update `switch_connection_state.highest_processed_sequence` after safe processing | Unique `(agent_id,event_sequence)`; duplicate event no-op/reuse prior outcome |
| Morning/evening reminder | Check local date, time window and setting | `INSERT reminder_dispatches` pending; send; update status/sent_at | Unique `(local_date,reminder_type)`; use outbox/claim semantics if send/retry may race |
| Model call usage | Provider response ID, model, token count and verified pricing | `INSERT model_usage_records`; update monthly aggregate/cache if used | Usage record idempotent by provider request ID; if unknown after timeout, count conservatively until reconciled |

## Transaction and concurrency requirements

- One active Zasky writer process; host lock prevents double-start.
- SQLite WAL, foreign keys, busy timeout; parameterized ORM queries.
- Use `BEGIN IMMEDIATE` for proposal approval and any multi-row mutation sensitive to concurrency.
- Use compare-and-set revision checks to prevent stale proposals.
- Never call an external provider while holding a write transaction longer than necessary.
- Mark inbound event processed and apply domain mutation atomically where feasible. External message post is not part of SQLite transaction; use a durable result/outbox record if the protocol doesn't provide an idempotent send key.
- No destructive deletes in normal flows; use explicit statuses and preserve history.
- Do not use an in-memory cache as source of truth; recompute from SQLite. If any cache is added as an implementation detail, invalidation must be tested and no correctness decision can depend on stale cached state.
