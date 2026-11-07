# Deployment Guide

## Hackathon staging status (2026-11-07)

The hackathon build runs on the Switch VPS and uses **Neon Postgres** as the
authoritative database. The Next.js dashboard is deployed separately to Vercel.
This is still **staging**: production release authority has not been granted.

- Zasky health: `127.0.0.1:8099` (private).
- Owner dashboard API: `0.0.0.0:8100` behind a bearer token.
- Switch API: port `8000`; Gateway `3001`; Switch Postgres `5433`.
- Port `8000` is **not** available for the dashboard because Switch uses it.
- Interface: chat in the Switch/Discord room plus the Vercel owner dashboard.

The staging model is OpenRouter `openai/gpt-4o-mini` via Chat Completions. The
operator accepted sending owner planning text with `store=false`; the ledger
enforces $20/month and 100 requests/day. The room should still be private before
real owner data or a public demo.

## Topology
One Linux VPS with persistent storage runs the official Switch deployment and one Zasky service instance. Discord is connected by Switch's bridge. Zasky connects to Switch through the documented private or authenticated endpoint. Product state lives in Neon Postgres; SQLite remains supported for local tests. The Vercel dashboard calls the VPS dashboard API through a server-side Next.js proxy, so the dashboard token never reaches the browser.

Do not expose Zasky's health endpoint, database credentials or Switch agent key
publicly. The dashboard API is intentionally reachable but token-gated.

## Deployment rules
1. Confirm `OPERATOR_INTAKE.md` has passed for host, Switch, credentials, cost cap and deployment authority.
2. Confirm the target is isolated staging/test unless production authority is explicitly recorded.
3. Pin images/dependencies and record versions/digests.
4. Configure firewall for SSH and only the ports required by the currently deployed Switch documentation.
5. Use non-root containers, restrictive volumes, read-only root filesystem where compatible, and restart policies.
6. Attach SQLite and backup directories to persistent volumes; do not use ephemeral container storage.
7. Run migration, start one Zasky replica, verify health, Switch connection and private-room echo.
8. Run security tests and a database restore drill.
9. Update preview/staging after each verified checkpoint; record exact URL/host scope and commit in the handoff.
10. Production deployment occurs only after explicit production authorization and final release gate.

## Neon Postgres migration

1. Put the Neon URL in the protected env file as `DATABASE_URL`. Accepts
   `postgres://`, `postgresql://` or `postgresql+asyncpg://`; SSL query
   parameters are normalized for asyncpg.
2. Apply migrations while the writer is stopped:

```bash
cd /root/Zasky
docker compose stop
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env migrate
uv run zasky-maintenance --env-file /root/Zasky-secrets/zasky.env status
```

3. Seed synthetic demo data (only against the intended database):

```bash
uv run python scripts/seed_demo.py --env-file /root/Zasky-secrets/zasky.env
uv run python scripts/seed_dashboard_demo.py --env-file /root/Zasky-secrets/zasky.env
```

4. Rebuild and start one writer:

```bash
docker compose up -d --build
curl -sS http://127.0.0.1:8099/health/ready
```

Expected: `database: ok`, `switch: connected`, `schema: current`.

The container uses the async `asyncpg` driver and disables the asyncpg statement
cache for Neon/PgBouncer compatibility. The app does not run `create_all` on
Postgres; Alembic owns the schema.

## Owner dashboard API and Vercel

The API listens on port `8100` with `DASHBOARD_API_KEY` required. The Vercel
project lives in `frontend/`; see `frontend/README.md` for the full deployment
steps. Required Vercel environment variables:

```dotenv
NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8100
ZASKY_DASHBOARD_TOKEN=<same value as DASHBOARD_API_KEY>
```

`ZASKY_API_URL` is an optional server-side override. The token must never use a
`NEXT_PUBLIC_` prefix.

If the host firewall is enabled, allow only the dashboard API port:

```bash
sudo ufw allow 8100/tcp
sudo ufw status
```

Do **not** run `sudo ufw allow 8000/tcp` for the dashboard; port 8000 is the
Switch API. If UFW is inactive, no command is needed. A cloud provider firewall
or security group must allow `8100/tcp` too.

For real personal use, terminate TLS in front of port 8100 and use the HTTPS URL
in Vercel. Rotate `DASHBOARD_API_KEY` after the demo.

## Calendar feed

The Vercel dashboard's **📅 Sync to Calendar** button points at the same-origin
`/api/dashboard/calendar.ics` proxy, which authenticates to the VPS with the
dashboard token. Google Calendar can subscribe to that Vercel URL
(**Other calendars → From URL**).

For a direct VPS subscription URL, set a separate `CALENDAR_FEED_TOKEN` in the
protected env and use:

```text
http://YOUR_VPS_IP:8100/api/dashboard/calendar.ics?token=YOUR_FEED_TOKEN
```

The feed contains active fixed events and approved day-plan tasks. Each task has
a display alarm `CALENDAR_ALARM_MINUTES` before its start (default 5). The
dashboard bearer token also works for this route.

## Discord channel expansion

The one-off `scripts/setup_discord.py` creates the Zasky HQ category and its five
text channels with the Discord REST API. It is idempotent and is **not run
automatically** by deployment. See `docs/DISCORD_SETUP.md` for review, run,
permission and environment details.

After the script prints channel IDs, add them and `DISCORD_BOT_TOKEN` to the
protected env file, then restart the Zasky container:

```bash
docker compose up -d --force-recreate
```

Routing:

- `#daily-briefings` ← approved `plan_day`;
- `#reconcile-alerts` ← approved `reconcile`;
- `#ai-workspace` ← Execution Sub-Agent results;
- `#zasky-control` and `#dashboard-sync` are created but not auto-wired.

## Rollback
- Stop Zasky writer before restoring or replacing its DB.
- Back up current DB and record commit/version.
- Roll back container image to last verified commit.
- For schema downgrade, follow tested Alembic downgrade only if data-safe; otherwise restore a verified backup.
- Reset Switch cursor only with verified protocol procedure; do not blindly replay old events.
- Re-run health, room round trip, query and owner authorization tests.
- Record rollback reason and resulting data state.

## Release authority
A permission to deploy staging is not production authority. If no exact production authority appears in `OPERATOR_INTAKE.md`, final status must be `verified-staging-awaiting-authorized-release`.
