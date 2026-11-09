# Zasky — Product Specification

**Status:** Pre-implementation baseline  
**Version:** 1.0  
**Date:** 2026-11-05  
**Product type:** Single-owner, chat-native personal planning agent  
**Target:** Flip the Switch Hackathon — Best Personal or Creative Workflow

> **Product promise:** Zasky does not give the owner discipline. It makes coming back cheap.

## 1. Product definition

### 1.1 One-line description

Zasky is a personal task-manager agent that lives in a private chat room, holds the owner's plan from year goals down to today's tasks, and rebuilds a realistic plan when the day goes sideways.

### 1.2 Problem

The owner's day is frequently disrupted by long calls, scrolling, social commitments, illness, power cuts, unstable internet, laptop problems and late starts. When the day breaks, the owner loses the thread, panics, abandons the plan and loses confidence in deadlines. The expensive part is not writing a new list; it is reconstructing what mattered, what can move and whether the larger week/month still holds.

### 1.3 Existing alternatives/workarounds

- Todo lists and calendar reminders store tasks but leave the owner to reconcile a disrupted day.
- General-purpose AI chat can suggest plans but does not provide a constrained, persistent, auditable planning hierarchy.
- Paper notes and memory are easy to abandon or lose.
- Calendar apps represent time but do not enforce the rule that daily tasks must come from an owner-approved weekly pool.

These are problem-space observations, not claims that every alternative lacks every capability.

### 1.4 Target user and operating model

MVP is deliberately single-owner: the operator using Zasky for their own life and personal projects. The agent and owner share one private, dedicated chat room. The room must contain only the owner and Zasky (plus platform-managed bridge/system participants); no other human members may see planning data. There are no customer accounts, teams, public users or tenant model in the MVP.

### 1.5 Core value proposition

Zasky keeps a trusted plan across four horizons and makes disruption recovery a short chat interaction instead of a fresh planning exercise. It uses stored commitments, availability, estimates and evidence to explain what still fits and what must be renegotiated.

### 1.6 Differentiator

The defining behavior is not task capture or an attractive dashboard. It is the **reconcile loop**: the owner reports what happened and the current time; Zasky proposes a revised rest-of-day plan, identifies what moves, and reports whether the approved week remains feasible. Reassurance must be supported by schedule/capacity evidence.

### 1.7 Primary and secondary use cases

**Primary:** owner reports a disruption ("Back. A call ran for two hours; it is 4pm") and receives a constrained, approvable recovery plan.

**Secondary:**
- Build year goals with testable evidence of completion.
- Turn owner-named goals into owner-named monthly commitments.
- Place concrete work items into a week while preserving slack.
- Create the day plan from the approved week pool.
- Backplan wake time and the shape of tomorrow around fixed events.
- Mark work complete or park it with a resume note.
- Query the plan, commitments, deadlines and week status.
- Enter a low-energy/panic state and reduce the day to one existing, meaningful action.

### 1.8 Explicit non-goals

Zasky is not:
- A website, web app, mobile app, task dashboard or calendar replacement.
- A task generator that invents actions from abstract goals.
- A motivational or guilt-based productivity coach.
- A multi-user SaaS product, team project manager or public bot.
- A general-purpose autonomous agent with shell, browser, email or payment access.
- A calendar/email/social integration product in the MVP.
- A streak, analytics, gamification or goal-visualization product.
- A system that silently changes approved commitments or fixed events.
- A promise to prevent distraction, illness, power cuts or oversleeping.

## 2. Product boundaries and invariants

The following rules are product invariants, not prompt suggestions:

1. **Owner-authored work:** Zasky never invents goals, commitments or task titles. It may ask questions, calculate, organize and propose placements using facts the owner supplied.
2. **Week-pool source of truth:** a daily plan may contain only active tasks already placed in the approved week pool. Normal tasks link to a monthly commitment. An ad hoc task may have no month-commitment link only when the owner explicitly flags it as ad hoc; it must still be added to the approved week pool before it can become a day task.
3. **Proposal before mutation:** planning and reconciliation are proposals. Only a clear owner approval commits their changes.
4. **One must:** if a day has at least one selected task, exactly one is `must`; all other selected tasks are `should`. Unselected week-pool tasks remain in the pool; `drop` is a daily disposition, not deletion/cancellation.
5. **Daily ceiling (default):** no more than three selected tasks per day. Low battery means one must task and at most one additional short/admin task from the existing week pool. The task count is configurable only within the defined product constraint. The owner may explicitly command `override limits` / `ignore the limit` / `schedule all my tasks` to bypass the count cap for that day; override still keeps exactly one must and warns when the day's estimated work exceeds available hours.
6. **Slack:** week capacity is not planned at 100%. Default `capacity_pct=65`; permitted operator configuration is 60–70%. Remaining time is reserved as slack.
7. **Fixed events are fixed:** Zasky does not move or cancel fixed events. It places work around them and reports conflicts.
8. **No silent deadline relief:** when a deadline cannot be met, Zasky marks it at risk and asks the owner to renegotiate; it does not silently extend it.
9. **Evidence-based reassurance:** statements such as "the week still holds" must be backed by remaining capacity and task estimates. Otherwise say "the week is at risk" and show the arithmetic.
10. **Owner-only data:** only the configured owner may read or mutate personal planning data in the connected room.
11. **Deterministic authority:** application code, not the LLM, owns authorization, dates, time arithmetic, capacity, validation, state transitions and persistence.
12. **Cloud resilience:** production Zasky and Switch should run on an always-on host with persistent storage, so the owner's laptop/power/internet failure does not stop the agent. If only a local demo is available, document the limitation honestly.

## 3. MVP scope

### MUST HAVE
- One private Discord channel connected through Switch.
- Switch is the agent/chat transport and shared room context; removing Switch removes the product's intended chat workflow.
- One configured owner participant ID and one allowed room ID.
- Durable SQLite store and backup/restore procedure.
- Year goals, monthly commitments, fixed events, weekly placements and concrete week tasks.
- Seven domain tools exactly: `add_commitment`, `place_week`, `plan_day`, `reconcile`, `park_task`, `complete_task`, `query`.
- Daily plan built only from approved week tasks; exactly one must when nonempty; maximum three tasks by default, with an explicit owner `override limits` command for a full-day plan.
- `backplan` calculations inside `plan_day`, not as an eighth tool.
- Reconcile proposal with a clear summary of day and week effects.
- Owner approval/rejection for every plan mutation; deterministic chat command parsing, not an eighth LLM tool.
- Query and status summaries.
- Timezone-aware planning, fixed event protection and 65% capacity default.
- Battery check (`low`, `medium`, `high`).
- Retry-safe Switch event processing and reconnect handling.
- Basic morning/evening prompts that are configurable and can be disabled.
- Structured logs, audit events, tests, backup and restore validation.
- Safe LLM integration with explicit monthly cost ceiling and strict tool schemas.

### SHOULD HAVE
- Panic mode: one 10-minute action chosen from an existing approved task, followed by an evidence-based check-in.
- Timebox overrun check-in at planned end, with extend/park options.
- Actual-duration capture to improve estimates (never silently auto-rewrite estimates).
- Deadline ledger with days remaining, remaining work and owner-recorded consequence.
- Monthly goal-hours review.
- Bulk reconcile after a multi-day outage, within the active week; unresolved work is marked at risk rather than auto-shifted across a month boundary.

### NICE TO HAVE
- Import/export of owner data in a documented JSON format.
- Second chat bridge (Mattermost) after Discord MVP is reliable.
- Voice-note transcription only after separate privacy, data-retention and cost review.

### FUTURE
- Optional read-only personal report/export.
- Calendar sync, if later explicitly scoped and authorized.
- Multiple owners, shared household/team plans, more chat platforms.
- Hosted multi-tenant service and admin console.

### OUT OF SCOPE
- Website, SaaS landing page, browser frontend, dashboard, mobile app.
- Payments, billing, subscriptions, escrow, wallet or financial actions.
- Email, calendar, contacts, social media and browser automation.
- General internet research or arbitrary computer-control tools.
- Automatic goal-to-task generation, streaks, badges, productivity scores.
- Public Discord commands or data access by arbitrary server members.
- Production deployment without explicit intake authorization.

## 4. User roles and trust boundaries

| Role | Meaning | Permissions |
|---|---|---|
| Owner/operator | The one configured human participant | Create/update plan data, approve/reject proposals, query all personal data, configure preferences |
| Zasky agent | One registered Switch agent | Read allowed room context; call the seven validated domain tools on behalf of owner; post messages |
| Future-you | Same owner at a later time, using room history | Read historical decisions and current plan; approve/renegotiate as owner |
| Other room participant | Any other Switch participant | No read or write access to Zasky data; their events are ignored or receive a neutral denial without data disclosure |
| VPS operator | Infrastructure administrator | OS/container/storage access; no routine product interaction; access governed by server security and audit procedures |

Switch addressing configuration is not a substitute for application authorization. The app must independently verify the exact configured room and owner participant ID for every inbound action.

## 5. Complete user flows

### F-01 — Initial activation and connection

**Entry:** operator starts deployment after all intake blockers have been answered.  
**Preconditions:** Switch workspace is reachable; Discord bridge and private channel exist; agent registration/credentials and exact IDs are available; OpenAI key and spend cap are available if using hosted model; VPS and persistent volume are ready.

1. Operator creates/registers Zasky once with Switch using the registration key.
2. Switch returns agent ID and agent API key. The application stores the key in a server-side secret store/environment file with restrictive permissions. It does not re-register at every boot.
3. Configure the exact Discord room and owner participant ID. Switch addressing is set to `owner_only` where supported.
4. Start Zasky and open its Switch WebSocket connection.
5. Send an echo/health message in the private channel.
6. Zasky checks room ID, sender ID, addressed flag and event deduplication before responding.
7. Zasky replies with a concise ready message; no personal data is created.

**State changes:** agent connection status and cursor/generation persisted; event audit record.  
**Validation:** connection ID, room ID, owner ID and agent credentials must match configured values.  
**Success:** owner sees Zasky's reply in the same room.  
**Failure:** auth/room failure is logged without printing tokens; bounded reconnect; operator receives exact nonsecret error.  
**Edge cases:** duplicate event, `gap`, `taken_over`, invalid bearer token, connection timeout, Discord bridge outage.  
**Permissions:** only configured owner can complete setup/test commands.  
**Exit:** connection established and `AI_HANDOFF.md` contains proof (redacted log reference, timestamp, commit).

### F-02 — Set year goals

**Entry:** owner says "Let's set my goals for 2027."  
**Preconditions:** owner authenticated by Switch participant ID; year goal count below five active goals or owner is editing/replacing one.  
**Steps:** Zasky asks what matters; owner supplies a title and evidence of done; Zasky validates the evidence is testable and asks for clarification if ambiguous; owner confirms; goal is saved.  
**State:** `year_goals` insert/update; audit event.  
**Validation:** year integer; nonempty title; nonempty evidence; max five active goals for a year; duplicate normalized title warning/constraint.  
**Success:** recap of goal and evidence.  
**Failure:** validation message; no partial write.  
**Edge:** goal exceeds cap → ask owner to retire/replace an existing goal; never silently discard.  
**Permissions:** owner only.  
**Exit:** active goal available for month commitments.

### F-03 — Plan a month and add commitments

**Entry:** owner starts monthly planning.  
**Preconditions:** year goals available where relevant; month and year known.  
**Steps:** owner names each concrete commitment; optionally links a goal; gives estimate, deadline and consequence where applicable. Zasky totals estimated work, compares with the owner's available capacity and asks whether to reduce/renegotiate if overloaded. Owner confirms each commitment.  
**State:** `month_commitments` records created/updated; monthly revision increments; audit events.  
**Validation:** title, estimate > 0, valid month/date, referenced goal exists and is active; deadlines cannot be silently moved.  
**Success:** month commitment summary showing total work and capacity pressure.  
**Failure:** no commitment saved until explicit confirmation.  
**Edge:** no goal link is acceptable; a goal link does not generate tasks; duplicate commitment requires explicit update/confirmation.  
**Permissions:** owner only.  
**Exit:** commitments become candidates for weekly placement.

### F-04 — Place work into a week

**Entry:** owner says "Plan this week."  
**Preconditions:** month commitments exist; weekly availability windows and fixed events are configured; current week or explicit `week_start` known.  
**Steps:** owner names the concrete work items/tasks and estimates for the week. Zasky links each to an existing month commitment. It computes available minutes from the supplied availability windows, subtracts fixed events and configured transition buffers, then applies `capacity_pct` (default 65%). It proposes dates/placements, shows load and slack, flags deadline risks, and asks for approval. It cannot compose task titles from goals or invent hidden subtasks.
**State:** proposal stored only; on approval, insert `week_placements` and `week_tasks` in one transaction and increment week revision.  
**Validation:** task title must be owner-provided; commitment must be active; date must belong to target week; estimate positive; total must not exceed planning budget without explicit renegotiation; no overlap with fixed events.  
**Success:** approved weekly pool and visible slack.  
**Failure:** proposal rejected/expired/stale; no partial placements.  
**Edge:** capacity exceeded → show exact overage and ask owner to remove/reduce work; no automatic overbooking. Commitment has no tasks → stays unplaced and is called out.  
**Permissions:** owner only.  
**Exit:** only approved tasks are eligible for `plan_day`.

### F-05 — Prepare tomorrow / plan today (`plan_day` + backplan)

**Entry:** morning prompt, evening preparation, or owner asks for a date.  
**Preconditions:** approved week pool for the requested date; fixed events and time configuration loaded.  
**Steps:** Zasky asks battery (`low`, `medium`, `high`) if not supplied. It reads only active tasks whose `scheduled_date` is the requested date; overdue tasks assigned to earlier dates enter only through an explicit reconcile proposal. It ranks using owner priority, deadlines and pre-existing placement order, and selects up to three by default. When the owner explicitly commands an override, it selects every active task for that date instead. Exactly one selected task is marked must. It schedules around fixed events and transition buffers. Backplan computes earliest required start and latest acceptable wake using morning prep and commute buffers; it may show a compressed alternative if the owner wakes later. It presents the plan and asks for approval.
**State:** draft `pending_proposal`; no day plan mutation before approval. Approval creates `day_plans` + `day_plan_items`, expires/replaces prior pending day plan for same date, and increments day revision.  
**Validation:** date in an approved week; no more than three items by default (all active tasks when `override_limits=true`); all task IDs active and in the approved week pool; one must if nonempty; no fixed-event overlap.  
**Success:** approved schedule, one must, up to two should by default (all active tasks on override), latest wake and compressed alternative.  
**Failure:** empty pool → state that no tasks are placed; ask owner to plan week rather than fabricate tasks. Invalid/missing availability → cannot give precise times; offer an unscheduled shortlist and request schedule data.  
**Edge:** low battery → one must plus at most one short/admin task from the pool by default; high battery does not increase week capacity; task estimates don't fit → report at risk and propose drops/moves, not arbitrary compression. Override mode schedules all active tasks for the date, keeps one must, and warns if total estimated time exceeds daily available hours.  
**Permissions:** owner only.  
**Exit:** approved day plan visible in chat and queryable.

**Backplan formula:** `latest_wake = first_required_start - morning_prep_min - commute_buffer_min`. `first_required_start` is the first fixed event or approved scheduled work block that requires the owner to be ready. Transition buffer is accounted for before that start where appropriate. The example plan must show the assumptions; Zasky must not claim precision if the owner has not supplied prep/commute values.

### F-06 — Reconcile a broken day (hero flow)

**Entry:** owner reports disruption ("Back, took a 2-hour call, it's 4pm").  
**Preconditions:** current/affected approved day plan and week pool available; current time and timezone known.  
**Steps:** Zasky interprets the disruption and confirms only materially ambiguous facts. It reads current day plan, incomplete tasks, fixed events, actual time and remaining week capacity. It proposes a new schedule using only existing week-pool tasks. It labels: keep now, move later today, defer to another day within same week, park with resume note, or leave unplaced. It calculates remaining weekly load vs budget/slack and states `week holds`, `week at risk` or `insufficient data`. It asks owner to approve/reject/edit.
**State:** draft proposal only. Approval transaction replaces current day plan and updates task target dates/placements only as authorized by proposal; it may create a `resume_note` for parked task. Audit event records decision summary.  
**Validation:** no new task titles; no fixed event moves; no task beyond approved week pool; approved work is not marked complete without explicit owner input; no task is silently removed.  
**Success:** owner sees clear recovery plan plus week status evidence.  
**Failure:** missing data → state exact unknowns; week capacity unavailable → cannot claim week holds; proposal expires/stales if base revision changed.  
**Edge:** multi-day outage → bulk mode for dates in same active week; if the week ended, leave tasks unplaced and ask owner to renegotiate next week; do not move automatically across month boundary.  
**Permissions:** owner only.  
**Exit:** approved revised plan or no changes if rejected.

### F-07 — Park/resume a task

**Entry:** owner says "park this; next step is..." or asks to resume a parked task.  
**Preconditions:** task is active/parked and belongs to owner's plan.  
**Steps:** park requires a concrete resume note (where work stopped and next action); resume requires the owner to confirm it is ready to return to the week pool.  
**State:** status becomes `parked` or `active`; note updated; audit event.  
**Validation:** cannot park completed tasks; cannot resume cancelled tasks; parked tasks are excluded from daily plans until resumed and assigned a valid date.  
**Success:** task state and note echoed.  
**Failure:** no state change; explain why.  
**Edge:** empty resume note → ask owner to supply it before parking.  
**Permissions:** owner only.  
**Exit:** task remains durable and queryable.

### F-08 — Complete a task

**Entry:** owner says "done" or invokes completion for a specific task.  
**Preconditions:** task is active or parked; identity and target unambiguous.  
**Steps:** Zasky confirms target if more than one match; captures actual minutes if supplied; sets completed status.  
**State:** task completed_at/actual_min; related day item records completed outcome; audit event.  
**Validation:** task id exists; only owner may complete; duplicate completion is idempotent.  
**Success:** completion confirmation and remaining day/week count.  
**Failure:** ambiguous task → ask which; unknown task → no write.  
**Edge:** already completed → report already complete, no duplicate side effect.  
**Permissions:** owner only.  
**Exit:** completed task remains historical and never reappears in active pool.

### F-09 — Query the plan

**Entry:** owner asks "What's left this week?", "What is due?", or "Which goal got no time?"  
**Preconditions:** owner authorization.  
**Steps:** query current stored state for the requested horizon/state; calculate status deterministically; format a short answer with IDs when disambiguation is needed.  
**State:** read-only; optional audit event for query category, not full personal text.  
**Validation:** allowed state/horizon enum; limit result size.  
**Success:** factual summary with estimates, deadlines and risk.  
**Failure:** data unavailable → say so, do not hallucinate.  
**Edge:** no records → clear empty state; stale proposals excluded or labeled.  
**Permissions:** owner only.  
**Exit:** no state change.

### F-10 — Morning/evening reminders

**Entry:** internal scheduler reaches configured local time.  
**Preconditions:** reminders enabled; service online; local day known; configured room reachable.  
**Steps:** use unique `(local_date, reminder_type)` key; send morning battery check or evening tomorrow-planning prompt once; on restart, send only if within 60-minute grace period.  
**State:** `reminder_dispatches` row inserted transactionally with send outcome.  
**Validation:** correct IANA timezone; valid send window; idempotent unique key.  
**Success:** one chat message at most per type/day.  
**Failure:** log retryable delivery issue; no duplicate reminder on reconnect.  
**Edge:** offline beyond grace → skip and record reason; timezone/DST change → use IANA zone.  
**Permissions:** operator-controlled preference; no reminders if disabled.  
**Exit:** normal room conversation.

## 6. Functional requirements and acceptance criteria

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-01 | Switch room connection | A test message in the configured private Discord room produces a reply in that room; an unconfigured room is ignored. |
| FR-02 | Owner authorization | A message from any participant other than the exact configured owner ID cannot query or mutate private data; test verifies no data is disclosed. |
| FR-03 | Year goals | Create no more than five active goals per year; each requires owner-supplied evidence of done. |
| FR-04 | Monthly commitments | Each commitment is owner-authored, optionally linked to an active year goal, and stores estimate/deadline/consequence. |
| FR-05 | Weekly placement | Only owner-named task titles can enter week pool; capacity is calculated and approval is required before writes. |
| FR-06 | Week capacity | Default planning budget is 65% of available work minutes after fixed events/buffers; configured value must be 60–70%; slack is surfaced. |
| FR-07 | Day pool constraint | Every day-plan item references an active week task assigned to that date/week; no LLM-generated task can bypass this. |
| FR-08 | One must / three max by default | A non-empty approved day plan has exactly one must and no more than three selected tasks by default. Explicit `override_limits=true` selects all active tasks for the date while retaining exactly one must. |
| FR-09 | Battery shaping | Low battery results in one must and at most one additional short/admin task by default; medium/high never exceeds three unless the owner explicitly overrides the limit. |
| FR-10 | Backplan | Wake time derives only from configured prep/commute buffers and first required start; calculation details are shown and tested. |
| FR-11 | Reconcile | A disruption creates a proposal from existing week tasks; fixed events remain unchanged; proposal reports week feasibility with arithmetic. |
| FR-12 | Approval gate | Only exact owner approval of a pending, unexpired, non-stale proposal commits mutations. Ambiguous "okay"/conversation text does not approve. |
| FR-13 | Park/resume | Park requires a resume note; parked task is excluded from daily planning until resumed. |
| FR-14 | Complete | Completion is idempotent; completed tasks cannot re-enter active plan. |
| FR-15 | Query | Query is read-only and all results are derived from stored data. |
| FR-16 | Reminder idempotency | At most one morning and one evening reminder per local date; duplicate scheduler runs do not duplicate messages. |
| FR-17 | Restart recovery | After process restart, Switch reconnect resumes safely from saved cursor/generation; a gap triggers context reread. |
| FR-18 | Cost controls | Requests/day and monthly spend are capped; at 80% warn; at 100% disable model calls until reset/operator action. |
| FR-19 | Data durability | Automated backup exists; restore test recreates goals, commitments, placements and tasks with referential integrity. |
| FR-20 | Privacy | Logs and prompts do not include secrets; raw chat is not retained in the product DB beyond minimum event dedupe metadata. |

## 7. Business logic and state machines

### 7.1 Planning capacity

- Owner supplies weekly availability windows in the configured timezone.
- Subtract fixed events overlapping those windows.
- Subtract configured transition buffers between adjacent fixed/work blocks. Do not double-count overlapping events.
- `available_work_min = max(0, availability_min - fixed_event_overlap_min - transition_buffer_min)`.
- For each date: `daily_available_work_min = availability_window_minutes - fixed_event_overlap_min - transition_buffer_min`; `daily_planning_budget_min = floor(daily_available_work_min * capacity_pct / 100)`.
- For a week: sum daily available minutes for dates in the configured week, then `weekly_planning_budget_min = floor(weekly_available_work_min * capacity_pct / 100)`.
- Default `capacity_pct = 65`; allowed range 60–70.
- `slack_min = available_work_min - planning_budget_min`; show daily and weekly slack separately.
- For monthly planning, sum availability windows for dates falling within that calendar month, subtract fixed-event overlap and transition buffers, then apply the same capacity percentage. This is the month work budget used to pressure-test the total estimated commitment work.
- Do not count unavailable hours as available merely because the calendar is empty.
- If owner availability is not configured, the planner may list tasks but must not give a false capacity/feasibility claim.

### 7.2 Prioritization and scheduling

1. Fixed events are immutable anchors.
2. For deterministic tie-breaking, order candidate tasks by commitment priority (`high`, `normal`, `low`), then earliest known deadline, then owner-approved placement order/creation time. Commitment-free ad hoc tasks use normal priority unless the owner explicitly sets another allowed priority.
3. Weekly auto-placement (when the owner did not name a date) distributes whole tasks across available dates in the selected week using remaining daily planning capacity, choosing the least-loaded eligible day first; preserve owner-specified dates. Never split a task automatically. If no date can fit the estimate, leave it unplaced and report why.
4. Previously approved day placements are preserved unless the owner initiates a plan/reconcile.
5. Fit selected tasks into available slots using estimates and buffers; if they do not fit, do not overlap events or compress estimates without the owner's agreement.
6. By default, `battery=low` limits the plan to one must and at most one short/admin should selected from the week pool. Medium/high may select up to three. An explicit owner override schedules all active tasks for that date, keeps one must, and reports a capacity warning if the total exceeds daily available hours.
7. Exactly one must is assigned whenever at least one item is selected. Other selected items are should. "Drop" is a proposed daily disposition only, not task cancellation.

### 7.3 Proposal lifecycle

`draft → pending → approved | rejected | expired | stale`

- `record`, `day` and `reconcile` proposals expire after 30 minutes; `week` proposals expire after 24 hours.
- Create a random human-readable code such as `ZK-4F8Q` (collision checked).
- Store `scope_key` plus `base_revision` read from `planning_scope_revisions`; for a proposal touching more than one independently versioned scope, store all expected scope/revision pairs in the validated proposal payload.
- Every committed mutation increments all affected scope revisions in the same transaction. Before approval, require configured owner participant, correct room, exact code (or plain `approve` only when exactly one pending proposal exists), unexpired status, and matching current revision(s).
- If the revision changed, mark `stale` and regenerate rather than apply old assumptions.
- Approval is a database transaction. Repeated approval is idempotent; a second approval reports already resolved.
- `reject ZK-4F8Q` or an explicit reject action resolves without business-data mutation.
- Natural-language "looks good" does not approve. No LLM tool may set proposal status directly.

### 7.4 Task lifecycle

`active → parked → active`  
`active → completed`  
`parked → completed`  
`active|parked → cancelled` only as an atomic consequence of an explicitly approved parent commitment cancellation; no standalone task-cancel command in MVP.

No delete in MVP. Daily dispositions `must|should|drop` are not lifecycle states. Completed and cancelled tasks remain historical. The only task-cancellation path is an atomic side effect of an explicitly approved parent-commitment cancellation through `add_commitment`; there is no standalone task-cancel command.

### 7.5 Commitment and goal lifecycle

- Goal: `active | achieved | retired`.
- Commitment: `active | completed | renegotiated | cancelled`.
- Goal may be retired only by explicit owner request.
- Commitment can link to at most one goal; it may be unlinked.
- A goal does not create commitments/tasks automatically.
- At month review, report actual task time linked to goal when known; unknown actual time is not treated as zero.

### 7.6 Deadline logic

For each commitment: `days_left = deadline_local_date - local_today`; `work_remaining_min` is the sum of estimates for active/parked incomplete tasks linked to it plus the known unplaced remainder from `est_total_min`, without double-counting placed task estimates. Consequence is owner-authored. Calculate future available work windows from now to the local deadline, subtract fixed-event overlaps and buffers, then apply `capacity_pct`. If remaining work exceeds that budget, mark `at_risk`; show assumptions and request owner renegotiation. Never silently alter a deadline or create work.

### 7.7 Reconcile feasibility

- `future_available_work_min` = owner availability-window minutes from the current instant through the end of the configured week, minus fixed-event overlap and applicable transition buffers.
- `remaining_week_budget_min = floor(future_available_work_min * capacity_pct / 100)`.
- `remaining_week_work_min` = sum of `est_min` for all incomplete, non-cancelled tasks in that week's approved pool, including parked tasks and tasks whose target date has already passed.
- The week `holds` only if `remaining_week_work_min <= remaining_week_budget_min`.
- If work exceeds the remaining budget, report the exact overage and mark `week_at_risk`; propose owner-approved reductions/moves only.
- If availability or fixed-event data is missing, report `insufficient_data` rather than guessing.

### 7.8 Supporting behaviors (after the recovery loop is proven)

These are `SHOULD HAVE`; they must not delay the core `plan_day`/`reconcile` path.

**Timebox check-in**
- When an approved day-plan task reaches its scheduled end and remains active, an optional one-time check-in asks: `Done, extend 15 minutes, or park?`
- `Done` calls `complete_task`; `park` calls `park_task` and requires the next-step resume note; `extend 15` invokes `reconcile` to propose a new time block.
- Never infer completion, silently extend a block or auto-park.
- If the task is completed/parked before the check-in, cancel the pending check-in.

**Stuck detection**
- Compare owner-reported actual minutes with the original estimate. If a task exceeds its estimate by a configured threshold twice (two distinct sessions), ask whether the estimate is too small or the task needs owner-defined decomposition.
- Do not change the estimate or invent sub-tasks automatically. The owner decides the new task/estimate and uses the existing `place_week`/`add_commitment` flow.

**Panic mode**
- Trigger only when the owner explicitly says they are overwhelmed or asks for panic mode.
- Collapse the response to one existing active must task and one concrete 10-minute action derived from owner-supplied task details/resume note. If no grounded next action exists, ask the owner to name it.
- Do not create a new task, change the week pool or claim progress. Offer a 10-minute check-in; owner can ignore it.
- Return to the full plan only when the owner asks or after the short check-in.

### 7.9 Conflict and duplicate rules

- Fixed event overlap: reject proposed schedule or find another gap.
- Double placement of same task on same date: unique constraint; no duplicate day item.
- Duplicate inbound Switch event: process once using unique event ID/sequence.
- Duplicate completion/approval: idempotent.
- Competing proposals based on same revision: first valid approval wins; other becomes stale.
- Two simultaneous writes: single-writer process plus SQLite transaction and revision check.

## 8. Domain tool contracts (exactly seven)

Tools are internal domain functions exposed to the model with strict JSON schemas. `owner_id`, permissions, current time, database handles and proposal status are injected by trusted application code; the model cannot supply them.

1. **`add_commitment`** — propose create/update of owner-authored hierarchy records. Required `operation: create|update`; `entry_type: year_goal|month_commitment|fixed_event`; `title`; for update, `entity_id`; type-specific fields include `year`, `month`, `goal_id`, `evidence_of_done`, `est_min`, `deadline_local_date`, `consequence`, `priority`, `starts_at`, `ends_at`. Return a `record` proposal; do not write the business record until exact owner approval. Reject ambiguous or incomplete payloads. It must not infer task titles.
2. **`place_week`** — `week_start` plus a list of owner-provided `{commitment_id, task_title, est_min, scheduled_date?, ad_hoc}` items. Normal tasks require an active `commitment_id` and `ad_hoc=false`. An ad hoc task requires `commitment_id=null`, `ad_hoc=true`, and an explicit owner instruction to add it ad hoc; it still enters the approved week pool and is subject to the same capacity rules. One tool call may contain tasks for multiple commitments; the deterministic service groups them into one `week_placements` row per commitment plus one ad hoc placement group as needed. A date may be omitted so deterministic scheduling proposes one. Task titles must originate from owner message/context and be quoted in tool input; no invented decomposition.
3. **`plan_day`** — `{date, battery: low|medium|high}`. Selects only active week-pool tasks with `scheduled_date` equal to the requested date; overdue work requires `reconcile`. Returns selected task IDs, daily dispositions, planned intervals, backplan fields and an approval proposal. No free-form task creation.
4. **`reconcile`** — `{what_happened, now_iso, from_date?, to_date?}`. `now_iso` includes an offset; normalize using configured timezone. Returns a proposal built from existing active week tasks, fixed events and current revisions.
5. **`park_task`** — `{task_id, action: park|resume, resume_note?, actual_min?}`. Park requires note; resume requires explicit owner intent and an available placement date before it can appear in a day plan. `actual_min` is owner-reported session time, not model-estimated.
6. **`complete_task`** — `{task_id, actual_min?}`. Owner-only and idempotent.
7. **`query`** — `{state: today|week|month|goals|deadlines|task|commitment|status, horizon? , entity_id?}`. Read-only and bounded.

**Approval command parser is not an eighth model tool.** `add_commitment` returns an uncommitted `record` proposal just like week/day planning. `place_week`, `plan_day` and `reconcile` also return proposals. `park_task` and `complete_task` are direct only when the owner explicitly requested that exact status action in the current message. The Switch event handler intercepts exact commands (`approve ZK-XXXX`, `reject ZK-XXXX`, `approve`, `reject`) before model invocation, verifies owner+room, resolves the pending proposal deterministically, then posts the outcome. The LLM cannot approve proposals by interpreting conversational tone.

## 9. API and system interface

There is no public product API in the MVP. Internal interfaces are:
- Seven validated domain tools above.
- Switch WebSocket events and Switch HTTP operations.
- `GET /health/live` and `GET /health/ready`, bound to localhost/private network only.
- Optional local-only maintenance CLI for backup/restore and migration status; no public admin endpoints.

Common internal error envelope:
```json
{
  "ok": false,
  "error": {
    "code": "PROPOSAL_STALE",
    "message": "That plan changed before approval. I have not applied it.",
    "retryable": false,
    "correlation_id": "opaque-id"
  }
}
```

Required error categories include `UNAUTHORIZED`, `ROOM_NOT_ALLOWED`, `INVALID_INPUT`, `NOT_FOUND`, `CONFLICT`, `CAPACITY_EXCEEDED`, `FIXED_EVENT_CONFLICT`, `PROPOSAL_EXPIRED`, `PROPOSAL_STALE`, `DUPLICATE_EVENT`, `RATE_LIMITED`, `MODEL_UNAVAILABLE`, `BUDGET_EXCEEDED`, `STORAGE_UNAVAILABLE`, `SWITCH_UNAVAILABLE`.

## 10. Data privacy classification

**Owner-private:** goals, evidence, commitments, task titles, estimates, deadlines, consequences, fixed events, availability, actual times, resume notes, battery states, proposals and room conversation context.

**Infrastructure secrets:** Switch registration/API keys, OpenAI key, SSH keys, database encryption/backup key. Secrets never enter prompts, audit rows or logs.

**Operator-only:** host/IP, backup paths, deployment state, redacted operational logs. No public access.

No data is intentionally public. Do not put private details in a public demo repo, screenshots, issue reports or demo video. Demo data must be synthetic or explicitly sanitized.
