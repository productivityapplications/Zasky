# Design Notes — Zasky Chat UX

## Why there is no visual UI reference
The product is deliberately chat-native. Discord, reached through Switch, is the interface. The generic workflow's website/frontend/reference-image and `stageshow` stages are not applicable. No image has been supplied or fabricated.

## Chat interaction principles
- Put the decision first: "Proposed plan", "Approved", "Week at risk", "Unable to verify".
- Separate stored facts from calculated values and proposed actions.
- Keep the first message on a phone screen useful without scrolling.
- Use one proposal code and one clear action command.
- State explicitly whether a write has happened.
- Keep daily plan to one must and at most two should items.
- Show the reason for a move and the exact capacity arithmetic when claiming the week holds.
- Never use guilt, streaks or vague motivational statements.
- Prefer short follow-up prompts; do not ask a form-like series of low-value questions in chat.
- Avoid emoji-only distinctions or color-dependent meaning.
- If messages must be split, number them and preserve sequence.

## Suggested message patterns

### Daily plan
```text
THURSDAY — 5 NOV
Battery: medium

MUST
• [task] — 45 min

SHOULD
• [task] — 20 min
• [task] — 15 min

Backplan
First required start: 08:30
Prep: 30 min | commute: 0 min
Latest acceptable wake: 08:00

Proposal ZK-4F8Q
Approve ZK-4F8Q / Reject ZK-4F8Q
Nothing is changed until approval.
```

### Reconcile
```text
RECOVERY PROPOSAL — 4:00 PM

Keep today:
1. [existing task] — 4:10–5:00
2. [existing task] — 5:10–5:30

Move:
• [existing task] → Friday (within this week)

Week status: HOLDS
Available planning budget: 780 min
Estimated remaining work: 510 min
Slack after proposal: 270 min

Proposal ZK-4F8Q
Approve ZK-4F8Q / Reject ZK-4F8Q
No changes applied yet.
```

These are layout examples, not fabricated state. The system fills them from actual stored/calculated data.

## Staging implementation notes (2026-11-06)

- The model-facing adapter uses OpenRouter Chat Completions with
  `openai/gpt-4o-mini`; the actual UI remains Discord through Switch.
- Proposal messages show one code and one exact command. The deterministic
  approval reply is separate from model text.
- Tool results include `*_display` local times and `task_title`; the prompt tells
  the model to use them verbatim to avoid UTC/local or title substitution errors.
- The model may prepare at most two proposals per inbound message; the tool loop
  is capped at five cycles.
- Plain text approval commands remain the fallback; no buttons/components are
  required for the MVP.
- The local demo is a protocol/transcript render, not a Discord screen capture;
  this is stated on every slide and in the narration.

## Conversational-context fixes (2026-11-06)

- The context builder now includes the last eight ordinary room messages from
  Switch `read_context` (owner and Zasky), bounded to 500 characters each. Raw
  room history is not persisted by Zasky; it is fetched per message and marked
  untrusted in the prompt.
- A request such as "What is my plan for Friday?" is treated as a **planning**
  request: `plan_day` must produce a pending proposal with a `ZK-XXXX` code.
  The deterministic fallback can create that proposal from the owner's date and
  battery even if the model chooses a read-only query.
- Plan/reconcile proposal text is rendered from the tool payload, not the
  model's calendar reasoning, so dates, local times, task titles and codes are
  exact.
- Short conversational approvals ("looks good", "lock that in", "go ahead")
  are intercepted by the app when a proposal is pending. They never commit.
  The reply is: "I cannot accept conversational approvals. Please reply with
  `approve ZK-XXXX` to lock this in."

## Discord formatting (2026-11-06)

Plan and reconcile messages are rendered by Python templates, not left to the
model. Headers and task names use bold, lists use `- ` bullets, sections use
double line breaks, proposal codes use inline code and the footer repeats the
exact approval command. Reconcile has explicit **KEEP**, **MOVE** and **DROP**
sections. The model is instructed to use the same style for general messages and
not to re-format the deterministic blocks.

## Latency tuning (2026-11-07)

- OpenRouter requests include `"provider": {"sort": "throughput"}`.
- The LLM `httpx.AsyncClient` is process-lifetime with keep-alive pooling
  (`max_keepalive_connections=10`, 60s expiry); it is not recreated per message.
- Output is capped at 600 tokens to bound generation time.
- After the owner/room gate and before the model call, the app posts an immediate
  `…` placeholder. Switch 0.31.0 has no message-edit operation, so the final
  reply follows as a second message rather than editing the placeholder. This is
  a provider limitation, not a fabricated typing indicator.
- Exact `approve`/`reject` commands skip the placeholder because they are handled
  deterministically without a model call.

## Native Switch capability audit (2026-11-06)

Switch 0.31.0 exposes 53 agent operations. It has `post_message` with an
optional `thread_id`, `read_context`, `create_room`, room documents and room
updates, but it has **no** `create_thread`, `pin_message`, or Discord
scheduled-event operation.

Implemented behavior:
- **Task-start alarms:** in-process scheduler posts a `Timebox Started` message
  through `post_message` at the approved task start (five-minute restart grace).
- **Focus mode:** the prompt supports focused co-worker behavior; replies stay in
  the owner's existing thread via `thread_id`. Zasky does not claim to create a
  thread it cannot create.
- **Daily Briefing:** on `plan_day` approval, Zasky posts a formatted Daily
  Briefing and creates a room document for persistence. Pinning and native
  Discord scheduled events are unavailable through Switch 0.31.0; pin the
  message manually in Discord if desired. No direct Discord API is used.

## Intentional exclusions
No website shell, dashboard, mockup, UI reference imagery, footer, web metadata, app icon or `stageshow` skill installation. Reconsider only after an explicit product scope change.
