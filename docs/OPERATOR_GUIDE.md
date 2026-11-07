# Zasky — Operator Guide

## What you do vs. what Zasky does

You choose goals, commitments and concrete work. You supply estimates, deadlines, fixed events and your available time. Zasky remembers these inputs, does the arithmetic, proposes a realistic week/day and helps rebuild a plan when life interrupts it. It does not generate work from goals.

## The planning cascade

1. **Year:** choose up to five goals with evidence of done.
2. **Month:** name concrete commitments. Give estimates, deadlines and consequences where useful.
3. **Week:** choose actual tasks and dates. Zasky calculates capacity using your availability and protects slack. Approve the week.
4. **Day:** Zasky selects only from the approved week pool, gives one must and up to two should tasks, asks about battery and backplans around fixed events.

Default planning capacity is 65% of your available work time. The remaining 35% is not "wasted"; it is the buffer that makes the plan survive real life.

## Approval

Plan proposals do not change the schedule until you send the exact approval command:
- `approve ZK-XXXX`
- `reject ZK-XXXX`

If there is exactly one pending proposal, `approve`/`reject` without code is accepted. Natural language such as "looks good" does not execute a change.

## When the day breaks

Send what happened and the current local time, for example: "Back, a call ran two hours over; it's 4pm." Zasky will use existing week tasks, preserve fixed events, propose what to keep/move/park and show whether the week still holds. Review the proposal and approve or reject it.

## Parking work

When parking, provide a resume note: where you stopped and the next concrete action. A parked task will not appear in a day plan until resumed.

## Battery and panic

- Low battery: one must and at most one short/admin task from the approved week pool.
- Medium/high: up to three total tasks; high battery does not increase the weekly capacity budget.
- If overwhelmed, ask for panic mode. The intended behavior is to identify one 10-minute action from an existing task, not invent a new task.

## Reminders

Morning/evening reminders can be disabled. If enabled, they are sent at configured local times and at most once per type/day. A long outage may cause a reminder to be skipped rather than sent late.

## Discord channel layout (2026-11-07)

The one-off `scripts/setup_discord.py` creates a private server layout:

```text
Zasky HQ
├── #zasky-control
├── #daily-briefings
├── #reconcile-alerts
├── #ai-workspace
└── #dashboard-sync
```

Routing after setup:

- approved Daily Briefings go to `#daily-briefings`;
- approved recovery summaries go to `#reconcile-alerts`;
- Execution Sub-Agent results go to `#ai-workspace`;
- `#zasky-control` and `#dashboard-sync` are ready for future use but are not
  auto-wired to the Switch room.

The bot token stays in the protected env file. The model cannot post arbitrary
Discord content and `@everyone` mentions are disabled on notification messages.

## Owner dashboard (2026-11-07)

Open the Vercel dashboard URL to see:

- **Today's Plan** — the approved MUST/SHOULD items, fixed events, battery and
  latest wake.
- **All Tasks** — the task pool with interactive checkboxes to mark a task
  complete.
- **Reconciliation History** — approved recovery plans with kept/moved items.

The dashboard also has **New Goal**, **New Commitment** and **Add Task** actions
for building the planning cascade directly in the UI. Existing goals and
commitments appear in the modal selectors. Created tasks enter the current week
pool immediately and are readable by Zasky in Discord.

On incomplete tasks, **⚡ Delegate to AI** starts the two-step execution flow:

1. **Confirm Delegation** runs the bounded Execution Sub-Agent. It can only
   draft copy, write code snippets, outline plans and format documents. It
   cannot browse, modify the database or approve its own work.
2. The modal renders the three-section output: **The Deliverable**, **What I
   Did** and **Verification Checklist**.
3. **✅ Approve Execution & Complete Task** is the sign-off. Only then is the
   task marked complete in Postgres.

The result is also posted to `#ai-workspace`.

In Discord, when you say you cannot do a task or a task is at risk, Zasky
creates a delegation proposal:

```text
You don't have time for [Task]. Should I delegate this to the Execution Agent?
Reply `delegate ZK-XXXX`.
```

After the exact `delegate ZK-XXXX` command, the Execution Agent posts the
structured deliverable to `#ai-workspace` and appends:

```text
Please review the deliverable above. If this meets your standards, reply
`approve execution ZK-YYYY` to mark the task complete.
```

Only `approve execution ZK-YYYY` marks the task complete. Natural language such
as "looks good" does not.

The dashboard writes to the same Neon Postgres database as chat. A checkbox is an
explicit owner completion, not a model action. The dashboard token stays on the
Vercel server. Do not share the Vercel URL publicly or put the token in a browser
variable.

**📅 Sync to Calendar** opens the dynamic iCalendar feed. Subscribe to it in
Google Calendar under **Other calendars → From URL** to receive fixed events and
approved day-plan tasks with a 5-minute display alarm. Each task also has a small
📅 quick-add link, and the Discord Daily Briefing ends with an all-day Google
Calendar link for the plan.

## Staging configuration (2026-11-07)

- Timezone: Africa/Lagos.
- Week start: Monday.
- Capacity: 65% of 09:00–21:00 availability every day.
- Buffers: 30 min morning prep, 0 min commute, 10 min transition.
- Model: `openai/gpt-4o-mini` through OpenRouter Chat Completions.
- Caps: $20/month and 100 requests/day. At the cap the model path stops; the
  deterministic approval parser, health checks and stored data remain available.
- Synthetic demo data is seeded in the staging database for testing.

## Test messages

```text
@zasky What is my plan for Friday?
@zasky Back. A two-hour call ran over; it's 4pm on Friday.
approve ZK-XXXX
@zasky What is left this week?
```

The proposal code must be copied exactly from Zasky's message. "Looks good",
"lock that in", "go ahead" and similar phrases are not approvals. If a proposal
is pending, Zasky replies with the exact command to use.

Zasky keeps the last eight ordinary room messages as bounded conversational
context. It does not persist raw room messages in SQLite. A request containing
"plan" and a date produces a `plan_day` proposal (not a read-only list).

## Proactive behavior

- At an approved task's start time, Zasky posts: `⏰ **Timebox Started:** ...`
  once per day-plan item. Alarms missed by more than five minutes are skipped.
- A plan approval also posts a formatted Daily Briefing and saves it as a room
  document. Switch 0.31.0 has no pin or scheduled-event operation; pin the
  message manually in Discord if you want it at the top.
- Focus mode is conversational. If you are already in a thread, Zasky replies
  in that thread. Switch 0.31.0 does not expose thread creation, so Zasky cannot
  create a new thread programmatically.
- While the model is working you may see a `…` placeholder followed by the
  answer. Switch 0.31.0 has no message-edit or native typing operation, so the
  placeholder cannot be edited or deleted.
- No third-party calendar, Google, or direct Discord API is used.

## Boundaries

Zasky cannot stop you scrolling, control your sleep, guarantee that a deadline will be met or prevent service outages. It can preserve the plan, show the consequences and make the return path short.
