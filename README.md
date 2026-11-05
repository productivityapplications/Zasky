# Zasky — Implementation Source Document Package

This package is the pre-implementation source of truth for building Zasky with an AI coding agent.

> **Zasky doesn't give me discipline. It makes coming back cheap.**

## What this package defines

Zasky is a single-owner, chat-native personal task-manager agent. It lives in a private Discord room through Switch, holds the owner's planning cascade (year → month → week → day), and proposes recovery when the day goes sideways.

The coding agent is an implementation executor. Product scope, business rules, architecture, tool count, data model, access control, cost boundaries, test requirements and implementation sequence are decided here.

## Read order for the coding agent

1. `ZASKY_IMPLEMENTATION_BLUEPRINT.md` — integrated 30-section blueprint.
2. `AGENTS.md`
3. `AI_HANDOFF.md`
4. `PROJECT_SPEC.md`
5. `ARCHITECTURE.md`
6. `IMPLEMENTATION_PLAN.md`
7. `OPERATOR_INTAKE.md`
8. `REFERENCE_ASSETS.md`
9. `docs/DATA_MODEL.md`
10. `docs/API.md`
11. Remaining `docs/`

Before changing the repository, complete one consolidated Phase 0 intake and readiness check. Do not begin coding while critical inputs or authority are missing.

## Package contents

```text
zasky/
├── ZASKY_IMPLEMENTATION_BLUEPRINT.md
├── PROJECT_SPEC.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── AGENTS.md
├── AI_HANDOFF.md
├── OPERATOR_INTAKE.md
├── REFERENCE_ASSETS.md
├── DEMO_VIDEO_PLAN.md
├── README.md
├── FINAL_PRE_IMPLEMENTATION_AUDIT.md
└── docs/
    ├── SETUP.md
    ├── CONFIGURATION.md
    ├── TESTING.md
    ├── DEPLOYMENT.md
    ├── TROUBLESHOOTING.md
    ├── DESIGN_NOTES.md
    ├── OPERATOR_GUIDE.md
    ├── API.md
    ├── DATA_MODEL.md
    ├── DATABASE_OPERATIONS.md
    ├── REFERENCE_SOURCES.md
    ├── REPOSITORY_STRUCTURE.md
    ├── EDGE_CASES.md
    └── BUILD_LOG.md
```

## Important workflow adaptations

The provided general workflow is applied, but it is not followed blindly:

| Generic workflow requirement | Zasky treatment |
|---|---|
| One consolidated operator intake | Retained |
| Autonomous implementation checkpoints | Retained |
| Early skeletal frontend deployment | Adapted to an early Switch-connected Discord round trip and protected test deployment |
| Complete functionality before final visual work | Retained as core E2E gate before chat UX refinement |
| Supplied UI reference images | Not applicable; no browser/mobile frontend exists in MVP |
| `stageshow` frontend skill | Not applicable; no frontend work exists |
| Website, landing page, footer, metadata/icons | Out of scope |
| README and relevant docs | Retained |
| <=3-minute real product demo video | Retained |
| Security and explicit production authorization | Retained |

Do not ask the operator for mockups or pretend a reference image exists. If a frontend is added later, revise the project scope and architecture first.

## Fixed product rules

- One owner and one private room.
- Switch is central; Discord is the intended chat bridge.
- Goals do not generate tasks. The owner names actual commitments and work items. Ad hoc tasks require an explicit owner flag and still enter the approved week pool.
- A day plan may use only active, approved week-pool tasks.
- A non-empty day plan has exactly one `must` and no more than three selected tasks.
- Default weekly capacity is 65%, configurable only from 60–70%.
- `reconcile` is the central recovery loop.
- `backplan` is inside `plan_day`, not an eighth tool.
- Exactly seven domain tools: `add_commitment`, `place_week`, `plan_day`, `reconcile`, `park_task`, `complete_task`, `query`.
- Planning changes are proposals; deterministic owner approval commits them.
- Application code—not the model—owns authorization, time arithmetic, capacity, state and persistence.

## Current status

This is a blueprint package, not an implementation. Product code has not been written, no repository has been changed, no Switch/Discord/OpenAI credentials have been tested and no deployment has occurred.

The first implementation-agent task is to inspect the actual repository and complete the consolidated operator intake. See the bottom of `AI_HANDOFF.md` and `IMPLEMENTATION_PLAN.md`.
