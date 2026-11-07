# Zasky

**A single-owner planning manager that turns a broken day into a short recovery path — and delegates the digital work it can safely hand to an AI Execution Agent.**

Zasky lives in a private Discord room through Switch, keeps an owner-approved
year → month → week → day planning cascade, and provides a private Next.js
dashboard backed by Neon Postgres.

---

## Why Zasky is different

Zasky is not a task list with a chatbot bolted on.

1. **It protects the plan.** Weekly capacity is bounded at 65% by default
   (60–70% allowed), fixed events are immutable, and a day plan has exactly one
   MUST and at most three selected tasks.
2. **It makes recovery cheap.** When a day breaks, `reconcile` proposes what to
   keep, move, park or drop, and shows whether the week still holds.
3. **It knows what work is yours.** Every task is typed:
   - **👤 Human** — physical presence or personal authority. Zasky never offers
     to delegate these.
   - **🧠 AI Delegatable** — digital knowledge work. Zasky can propose an
     Execution Agent run, but the owner must explicitly approve both the
     delegation and the final deliverable.
4. **It delegates with context.** The Execution Agent receives the task, parent
   commitment, year goal and evidence of done, any resume note, and optional
   owner instructions. It returns a structured **Deliverable**, **What I Did**
   and **Verification Checklist**.
5. **It never lets the model own state.** Approval parsing, dates, capacity,
   permissions, persistence and completion are deterministic application code.
   The model has exactly seven domain tools and no shell, browser, SQL, file or
   payment access.

---

## Architecture

```text
Discord owner room ──────┐
Discord #judges-sandbox ─┤
                         ▼
                 Switch 0.31.0 bridge
                         │  WebSocket + HTTP operations
                         ▼
              Zasky FastAPI process on VPS
              ├── owner scope ──────► Neon Postgres
              ├── judge sandbox ────► isolated SQLite
              ├── OpenRouter ───────► gpt-4o-mini
              ├── Discord REST ─────► #daily-briefings
              │                       #reconcile-alerts
              │                       #ai-workspace
              └── dashboard API :8100
                         ▲
                         │ same-origin proxy / sandbox proxy
                  Vercel Next.js dashboard
```

- The **chat interface** is Switch/Discord.
- **Neon Postgres** is authoritative for owner data.
- The **judge sandbox** is a separate SQLite database and never writes owner data.
- **Vercel** serves the dashboard and proxies to the VPS with a server-side
  token. No dashboard token reaches the browser.
- **Calendar** is a dynamic `.ics` feed with task alarms and Google Calendar
  quick-add links.

---

## Prerequisites

- Python 3.12+, `uv`, Docker Engine + Docker Compose.
- A Linux VPS with a persistent disk and a public IP.
- A Switch 0.31.0 deployment with a Discord bridge.
- A Discord server and bot with:
  - View Channels, Manage Channels (setup);
  - Send Messages in the notification channels.
- Neon Postgres project and connection string.
- OpenRouter API key and a tool-capable model (`openai/gpt-4o-mini` in staging).
- Vercel account for the dashboard.
- Discord Developer Portal access for the bot token and application.

Cost boundaries: Zasky defaults to **$20/month** and **100 model requests/day**.
An API key is not unlimited spend authority.

---

## Phase 1 — Infrastructure & Switch

1. Provision the Linux VPS and Docker.
2. Install Switch **0.31.0** using its official Compose deployment. Confirm the
   Switch API, Gateway and bridge are healthy.
3. Register Zasky as a custom agent in Switch and assign it to the owner room.
   Store the agent ID, runtime key and room ID in a protected env file outside
   the repository.
4. Link the Discord owner account through Switch and confirm the exact owner
   participant ID.
5. Keep the Switch health/API ports private. Only the dashboard API port is
   public, and only with a bearer token.

Useful references:

- `docs/SETUP.md`
- `docs/DEPLOYMENT.md`
- `docs/OPERATOR_INTAKE.md`
- Switch: <https://github.com/sandbox-quantum/switch>

---

## Phase 2 — Database (Neon Postgres)

1. Create a Neon project and copy the connection string.
2. Put it in `/root/Zasky-secrets/zasky.env`:

```dotenv
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

3. Apply Alembic migrations while the writer is stopped:

```bash
cd /root/Zasky
docker compose stop
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env migrate
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env status
```

Expected head: `5234927536a9` (or the latest migration in the repository).

4. Optional synthetic demo seed:

```bash
uv run python scripts/seed_demo.py --env-file /root/Zasky-secrets/zasky.env
uv run python scripts/seed_dashboard_demo.py --env-file /root/Zasky-secrets/zasky.env
```

The app refuses readiness if the database schema is not at the migration head.

---

## Phase 3 — Backend Setup

### Environment file

Create `/root/Zasky-secrets/zasky.env` with mode `0600`. Use `.env.example` as
the complete template. At minimum:

```dotenv
APP_ENV=staging
DATABASE_URL=postgresql://...
SWITCH_BASE_URL=http://127.0.0.1:8000
SWITCH_AGENT_ID=...
SWITCH_AGENT_API_KEY=...
SWITCH_CONNECTION_ID=...
SWITCH_ROOM_ID=...
OWNER_SWITCH_PARTICIPANT_ID=...
OPENAI_API_KEY=...
OPENAI_MODEL=openai/gpt-4o-mini
DASHBOARD_API_KEY=...
DASHBOARD_PORT=8100
DISCORD_BOT_TOKEN=...
DISCORD_DAILY_BRIEFINGS_CHANNEL_ID=...
DISCORD_RECONCILE_ALERTS_CHANNEL_ID=...
DISCORD_AI_WORKSPACE_CHANNEL_ID=...
CALENDAR_FEED_TOKEN=...
SANDBOX_DATABASE_URL=sqlite+aiosqlite:////app/data/sandbox.db
SANDBOX_OWNER_SWITCH_PARTICIPANT_ID=@sandbox:judge
SANDBOX_SWITCH_ROOM_ID=
```

### Discord layout

Create the Zasky HQ category and five channels:

```bash
uv run python scripts/setup_discord.py \
  --env-file /root/Zasky-secrets/zasky.env \
  --guild-id YOUR_DISCORD_SERVER_ID
```

This creates:

```text
Zasky HQ
├── #zasky-control
├── #daily-briefings
├── #reconcile-alerts
├── #ai-workspace
└── #dashboard-sync
```

Add the printed channel IDs to the env file. `#zasky-control` and
`#dashboard-sync` are reserved for future control/sync notices.

### Run the backend

```bash
docker compose up -d --build
curl -sS http://127.0.0.1:8099/health/ready
```

Expected:

```json
{"status":"ready","database":"ok","switch":"connected","schema":"current","model":"configured"}
```

### Task typing

Each task has `execution_type`:

- `human` (default) — never delegatable;
- `ai` — eligible for the two-step Execution Agent workflow.

The dashboard Add Task modal exposes this choice. The chat prompt and domain
service enforce it independently, so the model cannot override a human-only
task.

---

## Phase 4 — Frontend Deployment (Vercel)

1. Push the repository to GitHub.
2. In Vercel, import `productivityapplications/Zasky`.
3. Set **Root Directory** to `frontend`.
4. Framework preset: **Next.js**.
5. Add environment variables:

```dotenv
NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8100
ZASKY_DASHBOARD_TOKEN=<same value as DASHBOARD_API_KEY>
NEXT_PUBLIC_DEMO_MODE=false
```

6. Deploy.

The browser calls a same-origin Next.js proxy. The proxy adds the dashboard
bearer token server-side; the token never reaches the browser.

If the host firewall is enabled:

```bash
sudo ufw allow 8100/tcp
```

Port `8000` is used by Switch, not the dashboard.

---

## Public judge sandbox

The sandbox is an **isolated SQLite database**, never the owner Neon database.

### 1. Enable the sandbox

```dotenv
SANDBOX_DATABASE_URL=sqlite+aiosqlite:////app/data/sandbox.db
SANDBOX_OWNER_SWITCH_PARTICIPANT_ID=@sandbox:judge
SANDBOX_SWITCH_ROOM_ID=
```

Restart the backend. On first boot, Zasky creates the sandbox schema, a dummy
owner, and three demo tasks: two AI-delegatable and one human-only.

The app also creates the sandbox owner automatically. To regenerate it
manually:

```bash
sqlite3 /root/Zasky/data/sandbox.db < scripts/sandbox-owner.sql
```

The SQL uses the dummy Discord participant ID `@sandbox:judge` and the room
placeholder `sandbox-room`.

### 2. Discord sandbox

1. Create `#judges-sandbox` in Discord.
2. Create/attach a Switch room bridged to that channel and assign Zasky.
3. Find the assigned Switch room ID:

```bash
uv run python scripts/find_switch_room.py \
  --env-file /root/Zasky-secrets/zasky.env \
  --channel-id YOUR_JUDGES_SANDBOX_CHANNEL_ID
```

4. Set the result:

```dotenv
SANDBOX_SWITCH_ROOM_ID=<printed room ID>
SANDBOX_DISCORD_CHANNEL_ID=YOUR_JUDGES_SANDBOX_CHANNEL_ID
```

5. Restart the container:

```bash
docker compose up -d --force-recreate
```

Messages from that exact Switch room are routed to the sandbox scope and may
come from any judge. Every other room keeps the strict owner-only gate.

### 3. Vercel sandbox

Set this Vercel variable and redeploy:

```dotenv
NEXT_PUBLIC_DEMO_MODE=true
```

The frontend proxies to `/sandbox/api/dashboard` and shows:

> 🧪 You are viewing the interactive Hackathon Demo.

Judges can add tasks, complete them, and delegate AI tasks. The sandbox path
never touches the owner Neon database.

Reset the sandbox at any time:

```bash
docker compose stop
rm -f /root/Zasky/data/sandbox.db
docker compose start
```

---

## User guide

### Discord

- **Plan a day:** “What is my plan for tomorrow? Battery medium.”
- **Approve a proposal:** reply with the exact `approve ZK-XXXX` code.
- **Recover a broken day:** “Back, a call ran two hours over; it’s 4pm.”
- **Start work:** “I’m starting the demo script, I need help.”
- **Delegation:** say “I can’t do [AI task]” or “that task is at risk.” Zasky
  replies with a delegation code. Reply `delegate ZK-XXXX` or
  `delegate ZK-XXXX Use a casual tone.` Then review the structured deliverable
  in `#ai-workspace` and reply `approve execution ZK-YYYY`.
- **Human task protection:** “This task requires your physical presence, I
  cannot delegate it.”

### Dashboard

- **Today’s Plan:** calendar-style MUST/SHOULD timeline and fixed events.
- **All Tasks:** dark queue with filters, completion checkboxes, task-type
  badges, Google Calendar links and delegation.
- **New Goal / New Commitment / Add Task:** build the planning cascade.
- **Reconciliation History:** approved recovery plans.
- **Analytics dock:** completion, task mix and weekly activity.
- **📅 Sync to Calendar:** subscribe to the `.ics` feed in Google Calendar via
  **Other calendars → From URL**.
- **⚡ Delegate to AI:** only appears for AI-delegatable tasks. Confirm, review
  the three sections, then **✅ Approve Execution & Complete Task**.

### Execution Agent

The Execution Agent can only draft copy, write code snippets, outline plans and
format documents. It cannot browse, modify the database, send messages, run
commands or approve its own work. Its output is always:

```markdown
## 1. The Deliverable
## 2. What I Did
## 3. Verification Checklist
```

### Calendar

The ICS feed contains active fixed events and approved day-plan tasks. Each task
event has a display alarm controlled by `CALENDAR_ALARM_MINUTES` (default 5).
Auth accepts the dashboard bearer token or `?token=CALENDAR_FEED_TOKEN`.

---

## Hackathon demo note for judges

1. Open the Vercel dashboard with `NEXT_PUBLIC_DEMO_MODE=true`.
2. Add a task, mark one complete, and delegate an **AI Delegatable** task.
3. Review the structured output and approve execution.
4. In Discord, use `#judges-sandbox` for the same isolated sandbox.
5. Human tasks will not show a delegation button and will be rejected by the
   backend if delegation is attempted directly.

This is a staging/demo deployment. Production release authority remains with the
operator.

---

## Verification

```bash
uv run pytest -q       # 165 tests
uv run ruff check .
uv run mypy src
cd frontend && npm run build
docker compose ps
curl -sS http://127.0.0.1:8099/health/ready
```

Evidence and detailed operational notes are in:

- `AI_HANDOFF.md`
- `docs/BUILD_LOG.md`
- `docs/TESTING.md`
- `docs/API.md`
- `docs/DATA_MODEL.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`

---

## Links

- [GitHub repository](https://github.com/productivityapplications/Zasky)
- [Documentation](https://github.com/productivityapplications/Zasky/tree/main/docs)
- [Switch](https://github.com/sandbox-quantum/switch)
- Made for **WeMakeDevs Hackathon**
