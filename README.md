<div align="center">

# Zasky

### The Proactive Multi-Agent Task Manager

**A chat-native planning agent that protects your week, makes recovery cheap, and delegates the digital work it can safely hand off.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.162-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/Neon-Postgres-00E599?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Switch](https://img.shields.io/badge/Switch-0.31-7C3AED?style=for-the-badge)](https://github.com/sandbox-quantum/switch)
[![Hackathon](https://img.shields.io/badge/Built_for-WeMakeDevs_×_Switch-FF6B6B?style=for-the-badge)](https://github.com/productivityapplications/Zasky)

**[Live Dashboard](https://zasky-flax.vercel.app/) · [Watch the Demo](https://github.com/productivityapplications/Zasky/blob/main/artifacts/demo/zasky-demo.mp4) · [Join the Discord](https://discord.gg/PQvNZd4jhM)**

</div>

---

## 🚀 Quickstart & How to Test (Judges Start Here)

> **The 60-second judge path:** open the dashboard, watch the demo, then talk to Zasky live in Discord.

| Step | Action | Link |
|:---:|---|---|
| **1** | **Open the live dashboard** — today's plan, the week pool, goals, commitments and reconciliation history. | [**zasky-flax.vercel.app →**](https://zasky-flax.vercel.app/) |
| **2** | **Watch the 97-second demo** — a real model/tool/approval transcript with a concise product walkthrough. | [**Watch the demo →**](https://github.com/productivityapplications/Zasky/blob/main/artifacts/demo/zasky-demo.mp4) · [Download MP4](https://github.com/productivityapplications/Zasky/raw/main/artifacts/demo/zasky-demo.mp4) |
| **3** | **Join The Cockpit** — the Zasky Discord server. Start in `#welcome-and-how-to-test`. | [**discord.gg/PQvNZd4jhM →**](https://discord.gg/PQvNZd4jhM) |
| **4** | **Test the bot live** — go to `#judges-sandbox` and send a message. The sandbox is isolated from owner data. | `hello` or `@zasky what is my plan?` |

### Try these in `#judges-sandbox`

```text
hello
@zasky what is my plan?
@zasky I only have 45 minutes today
@zasky reconcile my week
```

- **No `@zasky` mention is required in the sandbox.** The sandbox deliberately accepts ordinary judge messages.
- **`#zasky-control` is the owner room.** It is the place for main planning, proposals, approvals and the full owner workflow.
- **The sandbox never writes to the owner database.** It runs on its own SQLite database and its own Switch connection.

---

## The Core Problem & Solution

Most task managers fail because they assume the plan you made on Sunday will survive Tuesday. They optimize capture, streaks and backlog size, then turn a missed task into guilt and a manual rebuild. The real problem is not storing tasks; it is making a **feasible** plan and making **recovery cheap** when reality breaks it.

Zasky treats the plan as a promise with slack, not a wish list. It maintains an owner-approved **year → month → week → day** cascade, protects a default **65% weekly capacity** (configurable only from 60–70%), and treats fixed events as immutable. When a day breaks, the **Reconcile Loop** proposes what to keep, move, park or drop using deterministic capacity arithmetic. For digital work, the **Execution Sub-Agent** turns a typed AI task into a structured deliverable and verification checklist, then waits for explicit owner approval before anything is marked complete.

---

## ✨ Key Features

| | Feature | What it does |
|:---:|---|---|
| 🧭 | **Reconcile Loop** | The primary recovery loop. `reconcile` proposes keep / move / park / drop choices and shows whether the week still holds after the disruption. |
| 🤖 | **Execution Sub-Agent** | Delegates only tasks typed as AI-delegatable. It receives the task, parent commitment, year goal, evidence of done and resume note, then returns a **Deliverable**, **What I Did** and a **Verification Checklist**. Delegation and completion both require explicit owner approval. |
| 🧠 | **Human vs. AI task typing** | Every task is either `human` (physical presence or personal authority) or `ai` (digital knowledge work). Zasky never offers to delegate a human-only task. |
| 📅 | **Google Calendar sync** | A dynamic `.ics` feed exposes fixed events and approved day-plan tasks with alarms, plus Google Calendar quick-add links for individual tasks. |
| 📊 | **Next.js dashboard** | A private, dark-mode owner dashboard on Vercel for today's MUST/SHOULD plan, the week pool, goals, commitments, reconciliation history and delegation. The dashboard token stays server-side. |

> **Deterministic by design:** validation, capacity, schedule arithmetic, approvals, state transitions, persistence and audit are application code. The model gets exactly seven domain tools and no shell, browser, SQL, file or payment access.

---

## 🏗️ Architecture

```text
┌──────────────────────────────┐
│  Vercel · Next.js 16         │
│  private owner dashboard     │
└──────────────┬───────────────┘
               │ HTTPS · same-origin proxy · server-side bearer token
               ▼
┌──────────────────────────────┐          SQL / asyncpg          ┌──────────────────────────┐
│  FastAPI · Zasky on the VPS  │ ──────────────────────────────► │  Neon Postgres           │
│  deterministic planning core │ ◄────────────────────────────── │  authoritative state     │
└──────────────┬───────────────┘                                 └──────────────────────────┘
               │ WebSocket events + HTTP operations
               ▼
┌──────────────────────────────┐
│  Switch 0.31                 │
│  agent runtime + bridge      │
└──────────────┬───────────────┘
               │ Discord bridge
               ▼
┌──────────────────────────────┐
│  Discord · The Cockpit       │
│  #zasky-control              │
│  #judges-sandbox             │
│  #daily-briefings            │
│  #reconcile-alerts           │
│  #ai-workspace               │
└──────────────────────────────┘
```

**Separation of concerns**

- The **chat interface** is Discord, bridged through **Switch**. Zasky is not a direct Discord bot and not a standalone CLI.
- **Neon Postgres** is authoritative for owner state. The **judge sandbox** uses an isolated SQLite database.
- **Switch** carries room events over WebSocket and exposes HTTP operations for context reads, replies and room management.
- **Vercel** serves the dashboard and proxies API calls with a server-side token; the token never reaches the browser.

---

## 💻 Local Development (Setup)

### Prerequisites

- **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/)
- **Docker Engine** + **Docker Compose**
- **Node.js 20.9+** and `npm` for the dashboard
- A **Switch 0.31** deployment with a Discord bridge, plus a Discord bot/server for chat testing
- A **Neon Postgres** project (or local SQLite for development)
- An OpenRouter API key and a tool-capable model such as `openai/gpt-4o-mini`

### 1. Clone and configure the backend

```bash
git clone https://github.com/productivityapplications/Zasky.git
cd Zasky

# Keep secrets out of Git. Use a protected file outside the repo in real use.
cp .env.example .env
chmod 600 .env

# Generate the local SQLite database URL:
# DATABASE_URL=sqlite+aiosqlite:///./data/zasky.db
#
# Or use Neon Postgres:
# DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

Fill in the Switch, Discord, OpenRouter and dashboard values in `.env`. The complete reference is in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) and [`docs/SETUP.md`](docs/SETUP.md).

### 2. Prepare the database

```bash
uv sync --extra dev

# Apply the schema at the migration head.
uv run zasky-maintenance --env-file .env migrate
uv run zasky-maintenance --env-file .env status
```

For a local SQLite checkout:

```dotenv
DATABASE_URL=sqlite+aiosqlite:///./data/zasky.db
```

For Neon, create a project, copy the pooled connection string and apply the same migration command. The app refuses readiness if the schema is not current.

### 3. Run the backend with Docker

```bash
ZASKY_ENV_FILE="$PWD/.env" docker compose up -d --build

curl -sS http://127.0.0.1:8099/health/ready
```

Expected:

```json
{"status":"ready","database":"ok","switch":"connected","schema":"current","model":"configured"}
```

The health endpoint is private. Chat requires a running Switch deployment and a Discord room bridged to it. For the full Switch/Discord setup, follow [`docs/SETUP.md`](docs/SETUP.md) and [`docs/DISCORD_SETUP.md`](docs/DISCORD_SETUP.md).

### 4. Run the Next.js dashboard

```bash
cd frontend
cp .env.example .env.local

# Point the server-side proxy at the local backend:
# NEXT_PUBLIC_API_URL=http://127.0.0.1:8100
# ZASKY_DASHBOARD_TOKEN=<same value as DASHBOARD_API_KEY>
# NEXT_PUBLIC_DEMO_MODE=false

npm install
npm run dev
```

Open **<http://localhost:3000>**. The dashboard calls the FastAPI API on port `8100` through a same-origin Next.js proxy.

### 5. Run the checks

```bash
# Backend
uv run ruff check .
uv run mypy src
uv run pytest -q

# Dashboard
cd frontend
npm run build
```

For migrations, backups, restore drills and deployment, see [`docs/DATABASE_OPERATIONS.md`](docs/DATABASE_OPERATIONS.md) and [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## 📚 Documentation

Planning and implementation documents moved into [`docs/`](docs/):

| Document | What it covers |
|---|---|
| [`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) | Product scope, roles, journeys, invariants and the seven domain tools |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Fixed stack, transport, security and integration decisions |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Phase order, checkpoints and test expectations |
| [`docs/AI_HANDOFF.md`](docs/AI_HANDOFF.md) | Current implementation state, evidence and known limitations |
| [`docs/API.md`](docs/API.md) | Dashboard API and runtime contracts |
| [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) | Entities, relationships and state transitions |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy and reproducible commands |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | VPS, Neon, Vercel and release procedures |
| [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) | Build history, decisions and verification evidence |

<div align="center">

**Built with Python, FastAPI, Next.js, Neon Postgres and Switch.**

*One owner. One plan. A cheaper way back from a broken day.*

</div>
