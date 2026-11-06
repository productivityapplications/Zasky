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

## Intentional exclusions
No website shell, dashboard, mockup, UI reference imagery, footer, web metadata, app icon or `stageshow` skill installation. Reconsider only after an explicit product scope change.
