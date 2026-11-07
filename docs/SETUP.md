# Setup Guide

## Hackathon VPS staging (current)

This repository is verified on the Switch VPS against Switch **0.31.0**, Neon
Postgres and a Vercel-ready Next.js dashboard. Use
`/root/Zasky-secrets/zasky.env` (mode `0600`) for secrets and runtime
configuration. Never copy it into Git.

```bash
cd /root/Zasky
uv sync --extra dev
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env migrate
uv run python scripts/seed_demo.py --env-file /root/Zasky-secrets/zasky.env
uv run python scripts/seed_dashboard_demo.py --env-file /root/Zasky-secrets/zasky.env
docker compose up -d --build
curl -sS http://127.0.0.1:8099/health/ready
```

The staging model is OpenRouter's OpenAI-compatible Chat Completions endpoint
with `openai/gpt-4o-mini`. The provider decision and pricing date are recorded in
`AI_HANDOFF.md` and `docs/CONFIGURATION.md`.

Dashboard API verification (token comes from the protected env file):

```bash
DASHBOARD_API_KEY="$(grep -m1 '^DASHBOARD_API_KEY=' /root/Zasky-secrets/zasky.env | cut -d= -f2-)"
curl -fsS -H "Authorization: Bearer ${DASHBOARD_API_KEY}" \
  http://127.0.0.1:8100/api/dashboard/today | head -c 300
```

The frontend lives in `frontend/` and deploys to Vercel. See
`frontend/README.md` for environment variables, root-directory settings and the
firewall command. Port `8100` is the dashboard API; port `8000` is Switch.

Discord HQ layout setup is a separate reviewed one-off step:

```bash
uv run python scripts/setup_discord.py \
  --env-file /root/Zasky-secrets/zasky.env \
  --guild-id YOUR_DISCORD_SERVER_ID
```

It requires `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID` in the protected env, and
a bot with View Channels + Manage Channels. It prints the channel-ID env lines
for `#daily-briefings`, `#reconcile-alerts`, `#ai-workspace` and the other
channels. See `docs/DISCORD_SETUP.md`.

This guide applies after the coding agent has completed the intake and implementation. Do not put secrets in Git.

## Prerequisites
- Linux VPS with persistent disk and SSH key access.
- Docker Engine and Docker Compose plugin.
- Running Switch workspace and the current documented agent WebSocket protocol.
- Discord private server/channel connected through Switch.
- OpenRouter API key and a verified Chat Completions model with tool calling
  (`openai/gpt-4o-mini` in staging).
- Neon Postgres URL for cloud state (SQLite remains supported for local tests).
- Operator-approved monthly infrastructure and model spend ceilings.

## First deployment
1. Clone the authorized repository and verify the expected commit.
2. Copy `.env.example` to a protected environment file outside the public repo or use Docker secrets.
3. Set file ownership to the service account and permissions to `0600`.
4. Verify required settings without printing secret values.
5. Run database migrations using the documented one-shot command.
6. Start the Zasky service with Docker Compose; deploy Switch using its official deployment instructions and pinned version.
7. Verify `/health/live` and private `/health/ready` from the host.
8. Verify the agent WebSocket connection; check logs for a successful handshake without token output.
9. In the exact private Discord room, send a harmless test message as the configured owner.
10. Confirm a reply appears in the same room; run a non-owner negative test.
11. Create and verify an encrypted backup; restore into a temporary isolated database.
12. Record service version, Git commit, connection test and backup evidence in `AI_HANDOFF.md`.

## First-run configuration
- Confirm owner participant ID and room ID using Switch's documented identifiers; treat both as opaque strings.
- Confirm IANA timezone and weekly availability windows.
- Enter fixed events, prep/commute/transition buffers and reminder preferences.
- Confirm capacity percentage (default 65%, allowed 60–70%).
- Add owner-chosen year goals and month commitments; add explicit weekly task titles and estimates.
- Do not ask Zasky to derive tasks automatically from goals.

## Local development
Use a separate `.env.test` and disposable SQLite database. Never point local tests at production data. Run tests and lint commands exactly as documented in `pyproject.toml`/CI. Local development is not a substitute for the protected Switch/Discord end-to-end round trip.
