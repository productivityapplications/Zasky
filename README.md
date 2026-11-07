# Zasky — Implementation Source Document Package

This package is the pre-implementation source of truth for building Zasky with an AI coding agent.

> **Zasky doesn't give me discipline. It makes coming back cheap.**

## Implementation status — 2026-11-07

Phases 1–9 are implemented and verified in **VPS staging** against Switch
**0.31.0**, Neon Postgres and a Vercel-ready Next.js dashboard. The agent is
registered as `zasky`, connected to the configured room, and the private health
endpoint reports ready.

- **Chat** is the primary interface: seven deterministic tools, exact owner
  approval, proactive task-start alarms, focus mode and Daily Briefing.
- **State** lives in Neon Postgres (`DATABASE_URL`); SQLite remains supported
  for local tests. Alembic owns the cloud schema.
- **Dashboard** is in `frontend/` with Today's Plan, All Tasks and Reconciliation
  History. Checkbox completion writes through the same deterministic domain
  service.
- **Calendar** is available as a dynamic `.ics` feed with task alarms, Google
  Calendar quick-add links on task rows, and a Daily Briefing calendar link.
- **Dashboard API** is token-gated on port `8100`; port `8000` is used by Switch.
- **Model** is OpenRouter `openai/gpt-4o-mini` via Chat Completions with
  `provider.sort=throughput`, a 600-token cap and hard $20/month,
  100 requests/day limits.

```bash
# Migrate the configured database (Neon in staging)
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env migrate

# Seed synthetic demo data
uv run python scripts/seed_demo.py --env-file /root/Zasky-secrets/zasky.env
uv run python scripts/seed_dashboard_demo.py --env-file /root/Zasky-secrets/zasky.env

# Run the verified staging container
docker compose up -d --build
curl -sS http://127.0.0.1:8099/health/ready
# {"status":"ready","database":"ok","switch":"connected","schema":"current","model":"configured"}
```

Test chat with a message addressed to the agent:

```text
@zasky What is my plan for today? Battery medium.
```

Test the dashboard locally:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8100 \
ZASKY_DASHBOARD_TOKEN=<DASHBOARD_API_KEY> \
npm run dev
```

Then deploy `frontend/` to Vercel using `frontend/README.md`. The token stays
server-side in `ZASKY_DASHBOARD_TOKEN`; never expose it as `NEXT_PUBLIC_*`.

The final Discord layout was created by the reviewed one-off script
`scripts/setup_discord.py`:

```text
Zasky HQ
├── #zasky-control
├── #daily-briefings
├── #reconcile-alerts
├── #ai-workspace
└── #dashboard-sync
```

The script's channel IDs and `DISCORD_BOT_TOKEN` are in the protected env file.
Approved briefings go to `#daily-briefings`, recovery summaries to
`#reconcile-alerts`, and Execution Sub-Agent results to `#ai-workspace`. See
`docs/DISCORD_SETUP.md`.

The local protocol/transcript demo is in `artifacts/demo/`:

- `zasky-demo.mp4` — 97 seconds, 1280×720, local TTS, real OpenRouter/tool
  transcript, synthetic data, explicitly labeled **not a Discord screen capture**.
- `narration-script.md`, `production-notes.md`, `demo-seed.md`, `transcript.txt`.

Secrets live outside the repository in `/root/Zasky-secrets/zasky.env` with mode
`0600`. `.env.example` documents the required names; no real values belong in Git.
The Discord room privacy setting (`@everyone → View Channel = deny`) remains an
operator action before real personal use.

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
├── frontend/                  # Next.js owner dashboard (Vercel)
├── scripts/                   # synthetic demo seed + demo build helpers
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
    ├── DISCORD_SETUP.md
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
| Early skeletal frontend deployment | Replaced by the Switch-connected Discord round trip and protected staging deployment |
| Complete functionality before final visual work | Retained; the dashboard was added only after the domain and chat loop passed |
| Supplied UI reference images | Not applicable; the operator requested a clean dark dashboard without a reference image |
| `stageshow` frontend skill | Not used; the dashboard is a small purpose-built Next.js app |
| Website, landing page, footer, metadata/icons | Out of scope; `frontend/` is a private owner dashboard only |
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

The implementation is complete for the hackathon staging scope: chat, deterministic
planning, proactive features, Neon Postgres, the dashboard API and the Vercel-ready
frontend. Tests, migration status, health and live API evidence are recorded in
`AI_HANDOFF.md`, `docs/BUILD_LOG.md` and `docs/TESTING.md`.

Remaining operator actions:

1. Set the Discord room to private (`@everyone → View Channel = deny`).
2. Deploy `frontend/` to Vercel with `NEXT_PUBLIC_API_URL` and
   `ZASKY_DASHBOARD_TOKEN`.
3. For real use, put the dashboard API behind HTTPS and rotate the token.
4. Production release still requires explicit operator authorization.
