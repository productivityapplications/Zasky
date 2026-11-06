# Zasky — API and Domain Tool Specification

There is no public product REST API in the MVP. The agent's public interface is the Switch room. Internal domain functions are exposed to the model as exactly seven strict tools. Only the application may call these functions after inbound owner authorization.

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
- `approve` or `reject` only when exactly one pending proposal exists for this owner and room.

Parser checks Switch `payload.addressed=true`, owner, room, code, TTL, status and every expected scope revision. Revisions are read from and incremented in `planning_scope_revisions` inside the same transaction as the domain write. No LLM call occurs for a syntactically exact approval/rejection. "Looks good", "fine", "okay" and ambiguous conversational language do not approve. The plain-text message still has to address Zasky according to the room's Switch addressing rules; do not rely on slash-command events or an `addressed`-only filter if it suppresses those commands.

## Private operational endpoints

- `GET /health/live` — process responds.
- `GET /health/ready` — DB/migrations/config/Switch connectivity status. Do not include secret values, owner ID, room ID or private schedule in response.
- Both bind localhost/private network and are not exposed publicly.

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
- Process a message only when its room is allowed, sender is the owner and `addressed=true`.
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
