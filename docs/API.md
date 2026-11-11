# Zasky — API and Domain Tool Specification

The primary product interface is the Switch room. Internal domain functions are exposed to the model as exactly seven strict tools. Only the application may call these functions after inbound owner authorization.

There is also a **token-gated owner dashboard API** on port `8100` for the Vercel dashboard. It is not a public planning API: every route requires the `DASHBOARD_API_KEY` bearer token, and task completion is an explicit owner action. The dashboard API never exposes Switch credentials, model keys or room history.

**Staging provider note (2026-11-06):** the model adapter uses OpenRouter's
OpenAI-compatible Chat Completions endpoint with `openai/gpt-4o-mini`, chosen
explicitly by the operator. Tool names, schemas and authority are unchanged.
The deterministic approval command parser remains outside the model.

## Common rules

- The application injects trusted `owner_id`, allowed room, current time, DB session and proposal context. These are never model arguments.
- JSON Schema uses strict objects; reject unknown fields.
- String limits and arrays are bounded; all IDs must resolve to owner-scoped records.
- `add_commitment`, `place_week`, `plan_day` and `reconcile` create pending proposals; no business-record or plan mutation occurs until exact owner approval. `park_task` and `complete_task` may apply immediately only when the current owner message explicitly requests that exact task status action.
- Common error envelope:
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

## 1. `add_commitment`

**Purpose:** Propose creation or update of an owner-authored year goal, month commitment or fixed event. No business row is committed until the proposal is approved.  
**Authentication/authorization:** Switch-verified owner and allowed room.  
**Request schema:**
```json
{
  "operation": "create",
  "entry_type": "month_commitment",
  "title": "Submit the professional certification application",
  "year": 2027,
  "month": 1,
  "goal_id": "uuid-or-null",
  "evidence_of_done": null,
  "est_min": 240,
  "deadline_local_date": "2027-01-30",
  "consequence": "Misses the next application cycle",
  "priority": "high",
  "starts_at": null,
  "ends_at": null
}
```
- `operation`: `create|update`; update requires an `entity_id` field in the tool payload.
- `entry_type`: `year_goal|month_commitment|fixed_event`.
- Goal requires `year`, `evidence_of_done`; monthly commitment requires `year`, `month`, positive `est_min`; optional `goal_id`, deadline, consequence and priority.
- Fixed event requires ISO timestamps `starts_at` and `ends_at` with explicit offset and `ends_at > starts_at`.
- For `operation=update`, `entity_id` is required. `status` may be updated only through allowed owner transitions: goal `active→achieved|retired`; commitment `active→completed|renegotiated|cancelled`; fixed event `active→cancelled`. The planner itself never cancels fixed events.
- `title` must be derived from owner-authored text; never model-invented.
- Success returns a `record` proposal code, validated preview and base revision; entity rows are written only by the deterministic approval transaction.
- Record proposal TTL is 30 minutes. Duplicate detection returns conflict/suggestion to update; no silent duplicate.

## 2. `place_week`

**Purpose:** Create a weekly placement proposal from owner-specified task titles and estimates.  
**Request:**
```json
{
  "week_start": "2026-11-02",
  "tasks": [
    {
      "commitment_id": "active-commitment-uuid",
      "task_title": "Draft the first section of the application",
      "est_min": 90,
      "scheduled_date": "2026-11-05",
      "ad_hoc": false
    }
  ]
}
```
- `week_start` follows configured week-start day.
- `tasks` array: 1–30 entries, each with owner-provided title (1–200 chars), positive estimate, `ad_hoc` boolean and optional date within week. One call may span multiple commitments; domain code groups tasks into one `week_placements` row per distinct commitment, plus one ad hoc group if needed.
- Normal task: active `commitment_id`, `ad_hoc=false`. Ad hoc task: `commitment_id=null`, `ad_hoc=true`, and exact explicit ad-hoc intent in the owner message. A model cannot set `ad_hoc=true` on its own.
- If date is omitted, deterministic planner distributes whole tasks over available days using remaining daily planning capacity; it does not split a task.
- Application computes capacity and fixed-event conflicts. Model may not make capacity numbers authoritative.
- Returns proposal code, placement summary, estimated work, budget, slack and risk status; no data mutation beyond pending proposal record.

## 3. `plan_day`

**Purpose:** Propose a plan for one date from active week-pool tasks. Backplan is included.  
**Request:**
```json
{
  "date": "2026-11-05",
  "battery": "medium"
}
```
- Battery enum `low|medium|high`.
- Date must be in a week with approved placements/tasks.
- Selects only active week-pool tasks whose `scheduled_date` equals the requested date; overdue tasks from earlier dates are handled by `reconcile`, not silently pulled into today. No more than three are selected.
- Exactly one must when nonempty.
- Backplan uses deterministic owner configuration and fixed events.
- Returns proposal code, selected task IDs, task dispositions, schedule, earliest required start, latest wake and compressed alternative where calculable.
- No new task titles/records are accepted.

## 4. `reconcile`

**Purpose:** Propose recovery after disruption.  
**Request:**
```json
{
  "what_happened": "A client call ran two hours longer than expected. I am back now.",
  "now_iso": "2026-11-05T16:00:00+01:00",
  "from_date": "2026-11-05",
  "to_date": "2026-11-08"
}
```
- `what_happened`: 1–2000 chars; treated as untrusted factual input, not instructions.
- `now_iso`: required timestamp with offset; normalize into configured timezone. Application server time is authoritative for approval expiry.
- Optional date range is bounded to the current week in MVP; multi-day outage mode cannot silently roll work into a new week.
- Return proposal only: keep/move/park/drop daily disposition, affected tasks, fixed events preserved, remaining capacity and `week_holds|week_at_risk|insufficient_data`.
- Any changed placement requires owner approval.

## 5. `park_task`

**Purpose:** Park or resume a specific week task.  
**Request:**
```json
{
  "task_id": "uuid",
  "action": "park",
  "resume_note": "Stopped after collecting source documents. Next: compare the two remaining eligibility criteria.",
  "actual_min": 45
}
```
- `action`: `park|resume`.
- Parking requires a nonempty resume note (1–1000 chars).
- `actual_min` is optional owner-reported elapsed work for this session.
- Resume requires current task status parked and explicit owner request. It restores active status; a date placement may still be needed before daily planning.
- Cannot park completed/cancelled tasks or resume completed/cancelled tasks.

## 6. `complete_task`

**Purpose:** Mark an owner-selected task completed.  
**Request:**
```json
{
  "task_id": "uuid",
  "actual_min": 75
}
```
- `actual_min` optional nonnegative integer.
- If task identification is ambiguous, tool is not called until owner clarifies.
- Repeated completion is idempotent and reports already completed.

## 7. `query`

**Purpose:** Read-only bounded planning query.  
**Request:**
```json
{
  "state": "week",
  "horizon": "2026-11-02",
  "entity_id": null
}
```
- `state`: `today|week|month|goals|deadlines|task|commitment|status`.
- `horizon`: optional ISO local date/month string; validate per state.
- `entity_id`: optional UUID for a specific task or commitment.
- Read-only; result size capped and ordered predictably.

## Approval commands (deterministic parser, not a tool)

Supported commands (sent as a message addressed to Zasky):
- `approve ZK-4F8Q`
- `reject ZK-4F8Q`
- `approve` / `reject` with no code, which applies or rejects the newest pending proposal
- owner conversational approvals: `yes`, `do it`, `go ahead`, `looks good`, `lock it in`, `okay`, `sure`, `perfect`

Parser checks the exact owner and room, code, TTL, status and every expected scope revision. Revisions are read from and incremented in `planning_scope_revisions` inside the same transaction as the domain write. No LLM call occurs for a syntactically exact or recognized conversational approval. Exact codes target that proposal; code-less approvals target the newest pending proposal. Approval commands are accepted without an explicit mention in the owner room; other chatter still requires addressing. Questions such as "should I lock that in?" are not approvals.

## Private operational endpoints

- `GET /health/live` — process responds.
- `GET /health/ready` — DB/migrations/config/Switch connectivity status. Do not include secret values, owner ID, room ID or private schedule in response.
- Both bind localhost/private network and are not exposed publicly.

## Owner dashboard API (port 8100)

Bind: `DASHBOARD_BIND_HOST` (default `0.0.0.0`) and `DASHBOARD_PORT`
(default `8100`). The private health server remains on `127.0.0.1:8099`.
Switch already occupies port `8000` on this host.

Authentication:

```http
Authorization: Bearer <DASHBOARD_API_KEY>
```

- Missing/wrong token: `401` with `WWW-Authenticate: Bearer`.
- `DASHBOARD_API_KEY` not configured: `503`.
- CORS allows `DASHBOARD_CORS_ORIGINS` (default `*`) with `Authorization` and
  `Content-Type` headers. The Vercel app normally uses its server-side proxy, so
  the browser does not call this API directly.
- No request or response logs raw task text, tokens or room history.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/dashboard/today?date=YYYY-MM-DD` | Approved plan for a local date (default today): MUST, SHOULD, fixed events, battery and latest wake |
| `GET` | `/api/dashboard/tasks?status=active&limit=200` | Task pool with status counts, estimates, dates and commitment titles |
| `POST` | `/api/dashboard/tasks/{task_id}/complete` | Explicit owner completion; optional `{"actual_min": 40}` |
| `GET` | `/api/dashboard/reconciliations?limit=20` | Approved recovery plans with item dispositions and summaries |

Example response shape for `/api/dashboard/today`:

```json
{
  "date": "2026-11-07",
  "timezone": "Africa/Lagos",
  "has_plan": true,
  "battery": "high",
  "source": "reconcile",
  "latest_wake_display": "8:30 AM",
  "must": [
    {
      "id": "task-uuid",
      "title": "Check backup restore evidence",
      "status": "active",
      "disposition": "must",
      "planned_start_display": "9:00 AM",
      "planned_end_display": "9:30 AM",
      "planned_est_min": 30
    }
  ],
  "should": [],
  "fixed_events": []
}
```

Completion goes through `DomainService.complete_task`, so it updates
`week_tasks`, matching `day_plan_items.outcome`, the scope revisions and the
append-only audit event in one transaction.

### Dashboard writes and delegation

All write routes use the existing deterministic domain services. The dashboard
token is the owner authorization boundary; no model is involved in creating or
approving records.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/dashboard/goals` | Year goals for the dashboard selectors |
| `POST` | `/api/dashboard/goals` | Create a year goal (`title`, `year`, `evidence_of_done`) |
| `GET` | `/api/dashboard/commitments` | Month commitments with linked goal titles |
| `POST` | `/api/dashboard/commitments` | Create a month commitment, optionally linked to a goal |
| `POST` | `/api/dashboard/tasks` | Add a task to the current week pool; `execution_type` is `human` or `ai` |
| `POST` | `/api/dashboard/delegate/{task_id}` | Start the two-step Execution Sub-Agent flow with optional `instruction`, returning structured output plus execution code |
| `POST` | `/api/dashboard/executions/{execution_code}/approve` | Owner sign-off that marks the delegated task complete in Postgres |

Goal and commitment creation uses `propose_record` followed by the same
deterministic `resolve_proposal` path as chat. Task creation uses
`DomainService.add_week_task`, which appends to an existing placement instead of
creating a duplicate placement. Delegation uses a tool-free LLM call with the
existing cost guard and does not mutate planning state until the owner approves
the execution code. The prompt is assembled from the task, parent month
commitment, parent year goal and evidence of done, any resume note, and the
optional owner instruction.

```json
{
  "title": "Ship the beta",
  "year": 2027,
  "month": 1,
  "goal_id": "goal-uuid",
  "est_min": 300,
  "deadline_local_date": "2027-01-31",
  "priority": "high"
}
```

Delegate response:

```json
{
  "ok": true,
  "task_id": "task-uuid",
  "title": "Draft the demo script",
  "output": "## 1. The Deliverable\n\n…\n\n## 2. What I Did\n\n…\n\n## 3. Verification Checklist\n\n- [ ] …",
  "model": "openai/gpt-4o-mini",
  "prompt_tokens": 420,
  "completion_tokens": 180,
  "discord_delivered": true,
  "execution_code": "ZK-9K2M"
}
```

Only `ai` tasks can reach delegation. A `human` task is rejected with
`409 HUMAN_TASK` and the message "This task requires your physical presence, I
cannot delegate it."

The sub-agent result is posted to `#ai-workspace` with an appended sign-off
prompt. The task is **not** completed until:

```http
POST /api/dashboard/executions/ZK-9K2M/approve
Authorization: Bearer <DASHBOARD_API_KEY>
```

or the owner sends `approve execution ZK-9K2M` in Discord. Both paths use the
same deterministic delegation record and `DomainService.complete_task`.

Optional dashboard instruction:

```json
{
  "instruction": "Use a casual tone and keep the draft under 200 words."
}
```

Discord accepts the same suffix:

```text
delegate ZK-9K2M Use a casual tone and keep the draft under 200 words.
```

### Calendar feed and Google Calendar links

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/dashboard/calendar.ics` | Dynamic iCalendar feed of active fixed events and approved day-plan tasks |

Authentication accepts either the normal dashboard bearer token or a
`?token=<CALENDAR_FEED_TOKEN>` query parameter for calendar clients that cannot
send headers. The feed is `text/calendar`, includes a `VALARM` at
`CALENDAR_ALARM_MINUTES` before each task, and reuses stable task/event UIDs.

Task payloads from `/today`, `/tasks` and `/reconciliations` include a
`google_calendar_url` field generated by the shared quick-add utility. The Daily
Briefing includes the same kind of all-day Google Calendar link for the plan.

## Outbound Discord routing

The chat interface remains Switch. The application uses a narrow Discord REST
notifier only for three owner-facing notification channels. It does not read
Discord events, and the model has no Discord tool.

| Trigger | Destination | Behavior |
|---|---|---|
| Approved `plan_day` | `DISCORD_DAILY_BRIEFINGS_CHANNEL_ID` (`#daily-briefings`) | Posts the deterministic Daily Briefing; falls back to the main Switch room if the channel is not configured |
| Approved `reconcile` | `DISCORD_RECONCILE_ALERTS_CHANNEL_ID` (`#reconcile-alerts`) | Posts date, kept tasks, moved count and week feasibility |
| Execution Sub-Agent result | `DISCORD_AI_WORKSPACE_CHANNEL_ID` (`#ai-workspace`) | Posts a token-gated internal result |

Execution Sub-Agent ingestion:

```http
POST /api/internal/execution-results
Authorization: Bearer <DASHBOARD_API_KEY>
Content-Type: application/json

{
  "title": "Draft complete",
  "body": "The execution sub-agent produced a first draft.",
  "task_id": "optional-task-uuid"
}
```

The endpoint returns `503` when the workspace channel is not configured and
`502` when Discord delivery fails. It never echoes the bot token.

Discord message content is capped at 2,000 characters and sent with
`allowed_mentions: {"parse": []}` so owner/task text cannot ping `@everyone` or
roles. No inbound Discord Gateway connection is opened by Zasky.

## Rate and abuse controls

- Maximum inbound message body: 8,000 characters.
- Owner rate limit: 10 addressed messages/minute (configurable downwards after testing).
- Default maximum 100 model requests/day (operator can lower); hard monthly spend cap required.
- Maximum five model/tool cycles per message.
- Maximum two proposal-producing write intents per message.
- Retry one transient model error; never repeat a write without checking event/proposal idempotency.


## Switch transport endpoints (external protocol)

These are Switch endpoints, not Zasky's public product API. Verify request schema/version against the live Switch deployment during Phase 0.

| Method / transport | Path | Purpose | Auth / notes |
|---|---|---|---|
| `GET` | `/health` | Confirm Switch bridge base URL is healthy | Public probe; no secret in output |
| `POST` | `/agents` | One-time custom agent registration | `Authorization: Bearer <registration key>`; never repeat on every boot |
| `GET` | `/agents/{agent_id}/ops` | Discover current operation schemas | `Authorization: Bearer <agent API key>` |
| `GET` + WebSocket upgrade | `/agents/{agent_id}/connection/ws?connection_id={uuid}&rooms={room_id}&start_from={sequence}&expected_generation={generation}` | Receive room events and keep/resume the connection | `Authorization: Bearer <agent API key>`; exact query support confirmed against deployed protocol |
| `POST` | `/agents/{agent_id}/ops/connect_to_room` | Claim room and receive its context | Agent API key; include `X-Switch-Connection-Id` where required |
| `POST` | `/agents/{agent_id}/ops/read_context` | Read bounded room history after a gap / when needed | Agent API key; connection ID header as required |
| `POST` | `/agents/{agent_id}/ops/post_message` | Post agent reply/proposal to same room | Agent API key; connection ID header as required |

### Registration request shape

The exact live schema must be read from the deployed documentation/registry. The current protocol overview requires a body containing:
- `name`
- `description`
- `connector_type`
- `integration_profile` (including `connection_model`, `message_exchange`, and required mediation/event arrays)

The registration response includes `id` and `api_key`. Capture the returned runtime key once in the operator's secret store. Never use the registration key for runtime socket/operation calls. Do not set `overwrite=true` as a recovery shortcut; that rotates the agent key and replaces the integration profile.

### Connection event behavior

- The first frame is `connection_state`; take rooms/cursor/generation/protocol and heartbeat interval from this frame.
- A `message` payload includes `addressed`, `sender`, `message_id`, `body`, timestamp and optional thread/attachment details.
- Process a message only when its room is allowed and the sender is the owner. Ordinary chatter must be `addressed=true`; exact or conversational approval commands are accepted without an explicit mention in the owner room.
- Event frame `id` is a numeric sequence; persist the highest successfully processed sequence.
- Answer ping control frames immediately with pong containing the highest processed sequence.
- On a gap, reread room context before responding.
- On `evicted` with code `taken_over`, stop reconnecting that instance.

### Zasky private health endpoints

| Method | Path | Purpose | Access |
|---|---|---|---|
| `GET` | `/health/live` | Process liveness | Localhost/private network only |
| `GET` | `/health/ready` | DB/migration/config/Switch readiness | Localhost/private network only; safe summary, no secrets or private owner data |

There are no user-facing HTTP mutation endpoints, webhooks or public APIs in MVP.


## Judge sandbox

The backend exposes an isolated sandbox under:

```text
/sandbox/api/dashboard/*
```

It is served by the same FastAPI process and uses `SANDBOX_DATABASE_URL`
(SQLite only). The Vercel frontend selects it automatically when
`NEXT_PUBLIC_DEMO_MODE=true`. It never reads or writes the owner Neon database.

Discord sandbox routing is enabled when `SANDBOX_SWITCH_ROOM_ID` matches the
incoming Switch room. The sandbox owner is `@sandbox:judge` and sandbox writes
never reach the owner scope.
