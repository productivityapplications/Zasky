# Zasky — Target Repository Structure

> **Layout update (2026-11-07):** Planning and implementation documents now live
> in `docs/` so the repository root stays focused on code, deployment and the
> README. The tree below records the original target layout; `docs/PROJECT_SPEC.md`,
> `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/AGENTS.md`,
> `docs/AI_HANDOFF.md`, `docs/OPERATOR_INTAKE.md`, `docs/REFERENCE_ASSETS.md`,
> `docs/DEMO_VIDEO_PLAN.md` and `docs/FINAL_PRE_IMPLEMENTATION_AUDIT.md` are the
> current paths.

This is the target application repository after implementation. The document package is committed alongside code. There is no `web/`, `app/`, `pages/` or static website directory in the MVP; the private Next.js dashboard lives in `frontend/` for the hackathon staging build.

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
├── .gitignore
├── .env.example
├── pyproject.toml
├── uv.lock                       # or the one lockfile selected during repo inspection
├── Dockerfile
├── compose.yaml
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
├── src/
│   └── zasky/
│       ├── __init__.py
│       ├── app.py                # process startup and lifespan
│       ├── config.py             # Pydantic settings
│       ├── logging_config.py     # redacted structured logs
│       ├── switch/
│       │   ├── client.py
│       │   ├── connection.py
│       │   ├── events.py
│       │   └── operations.py
│       ├── access/
│       │   ├── policy.py
│       │   ├── approvals.py
│       │   ├── dedupe.py
│       │   └── rate_limit.py
│       ├── agent/
│       │   ├── orchestrator.py
│       │   ├── context.py
│       │   ├── schemas.py
│       │   └── prompts/
│       │       └── system.md
│       ├── domain/
│       │   ├── goals.py
│       │   ├── commitments.py
│       │   ├── week_placement.py
│       │   ├── day_plan.py
│       │   ├── reconcile.py
│       │   ├── task_lifecycle.py
│       │   ├── proposals.py
│       │   └── queries.py
│       ├── planner/
│       │   ├── capacity.py
│       │   ├── scheduling.py
│       │   ├── backplan.py
│       │   ├── deadlines.py
│       │   └── recovery.py
│       ├── storage/
│       │   ├── database.py
│       │   ├── models.py
│       │   ├── repositories.py
│       │   └── transactions.py
│       ├── integrations/
│       │   └── openai/
│       │       ├── client.py
│       │       ├── responses.py
│       │       └── usage.py
│       ├── scheduler/
│       │   ├── reminders.py
│       │   └── proposal_expiry.py
│       └── ops/
│           ├── health.py
│           ├── backup.py
│           ├── restore.py
│           └── maintenance.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── security/
│   └── fixtures/
├── docs/
│   ├── SETUP.md
│   ├── CONFIGURATION.md
│   ├── TESTING.md
│   ├── DEPLOYMENT.md
│   ├── TROUBLESHOOTING.md
│   ├── DESIGN_NOTES.md
│   ├── OPERATOR_GUIDE.md
│   ├── API.md
│   ├── DATA_MODEL.md
│   ├── DATABASE_OPERATIONS.md
│   ├── REFERENCE_SOURCES.md
│   ├── REPOSITORY_STRUCTURE.md
│   ├── EDGE_CASES.md
│   └── BUILD_LOG.md
└── artifacts/
    └── demo/
        ├── narration-script.md
        ├── production-notes.md
        └── zasky-demo.mp4
```

## Directory responsibilities

- `switch/` is a transport adapter only; it contains no product logic.
- `access/` enforces room/owner checks, deduplication, rate limits and deterministic approval commands.
- `agent/` handles language and the bounded Responses API tool loop.
- `domain/` implements state changes and product rules; every write is owner-scoped and revalidated.
- `planner/` contains pure deterministic time/capacity/recovery calculations.
- `storage/` handles persistence, transactions, migrations-facing models and audit writes.
- `integrations/openai/` contains provider-specific request/response/cost handling.
- `scheduler/` contains one-process, idempotent reminder and proposal-expiry jobs.
- `ops/` contains private health, backup/restore and maintenance commands.
- `tests/` are organized by test level and risk.
- `artifacts/demo/` contains synthetic demo assets only; no production data or secrets.

## Implementation detail boundary

The coding agent may refine module names or split files if the separation of concerns and public domain contracts remain the same. It must not add a frontend directory or public API in MVP.
