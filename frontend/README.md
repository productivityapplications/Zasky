# Zasky Dashboard

A private, dark-mode owner dashboard for the Zasky planning agent. It reads
today's approved MUST/SHOULD plan, the full task pool and reconciliation history
from the VPS dashboard API. From the UI the owner can create year goals, month
commitments and week-pool tasks, complete tasks, and run the bounded Execution
Sub-Agent against a task. All writes go to the same Neon Postgres database used
by Discord.

## Architecture

```text
Browser (Vercel)
  └─ same-origin /api/dashboard/*       (Next.js route handler, server-side)
       └─ Authorization: Bearer ...     (token never reaches the browser)
            └─ VPS FastAPI dashboard API on port 8100
                 └─ Neon Postgres
```

The browser never calls the VPS directly, so the dashboard token stays on the
Vercel server. `NEXT_PUBLIC_API_URL` is read by the server-side proxy only; the
`NEXT_PUBLIC_` name is kept because that is the URL the deployment contract
expects.

## Local development

Requirements: Node.js 20.9+ and npm.

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local:
#   NEXT_PUBLIC_API_URL=http://YOUR_VPS_IP:8100
#   ZASKY_DASHBOARD_TOKEN=<the DASHBOARD_API_KEY value>
npm install
npm run dev
```

Open `http://localhost:3000`.

The VPS backend must be reachable and its firewall must allow port `8100`:

```bash
sudo ufw allow 8100/tcp
sudo ufw status
```

Port `8000` is already used by Switch on this VPS, so the dashboard API uses
`8100`. Do not open `8000` for the dashboard.

## Deploy to Vercel

### 1. Import the repository

1. In Vercel, choose **Add New → Project**.
2. Import the GitHub repository `productivityapplications/Zasky`.
3. Set **Root Directory** to `frontend`.
4. Framework preset: **Next.js**.
5. Build command: `npm run build` (default).
6. Output directory: leave the Next.js default.

### 2. Add environment variables

Add these for **Production**, **Preview** and **Development**:

| Variable | Value | Visibility |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://YOUR_VPS_IP:8100` | Public value, but only used server-side |
| `ZASKY_DASHBOARD_TOKEN` | the `DASHBOARD_API_KEY` value from `/root/Zasky-secrets/zasky.env` | **Server-only secret** |

Optional server-side override:

| Variable | Value | Visibility |
|---|---|---|
| `ZASKY_API_URL` | `http://YOUR_VPS_IP:8100` | Server-only |

`ZASKY_API_URL` wins over `NEXT_PUBLIC_API_URL` when both are set. Never put the
dashboard token in a `NEXT_PUBLIC_*` variable.

### 3. Deploy

Click **Deploy**. After the build finishes, open the Vercel URL.

To deploy from the CLI instead:

```bash
cd frontend
npm install
npx vercel
npx vercel --prod
```

Set the same environment variables in the Vercel project settings before the
production deployment.

## Verify the VPS side

From the Vercel deployment, the proxy calls:

```text
GET  /api/dashboard/today
GET  /api/dashboard/tasks
GET  /api/dashboard/reconciliations
POST /api/dashboard/tasks/{task_id}/complete
```

You can verify the backend directly from the VPS without printing the token:

```bash
DASHBOARD_API_KEY="$(grep -m1 '^DASHBOARD_API_KEY=' /root/Zasky-secrets/zasky.env | cut -d= -f2-)"
curl -fsS \
  -H "Authorization: Bearer ${DASHBOARD_API_KEY}" \
  "http://127.0.0.1:8100/api/dashboard/today" | head -c 300
```

Expected: JSON with `date`, `has_plan`, `must`, `should` and `fixed_events`.

## Delegation duration

The `/api/dashboard/delegate/{task_id}` route keeps the browser request open
while the sub-agent drafts. The Next.js proxy waits up to 55 seconds and sets
`maxDuration = 60`. If the Vercel plan caps functions below that, the route will
time out before the model returns; raise the function limit or lower the
execution output budget.

## Security notes

- The dashboard token is mandatory. The backend refuses dashboard requests with
  `503` when `DASHBOARD_API_KEY` is not configured and `401` for a missing or
  wrong bearer token.
- The token is held in the Next.js server process and is never shipped to the
  browser.
- HTTP is acceptable only for a short-lived demo. For real personal use, put the
  VPS behind HTTPS (for example Caddy or a Cloudflare Tunnel) and use the HTTPS
  URL in `NEXT_PUBLIC_API_URL`.
- Rotate `DASHBOARD_API_KEY` after the demo, update the Vercel variable and
  redeploy.
- The dashboard is a private owner surface. Do not add public analytics,
  marketing pages or unauthenticated data routes.
