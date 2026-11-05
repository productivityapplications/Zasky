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

## Boundaries

Zasky cannot stop you scrolling, control your sleep, guarantee that a deadline will be met or prevent service outages. It can preserve the plan, show the consequences and make the return path short.
