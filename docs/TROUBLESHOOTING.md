# Troubleshooting

| Symptom | Likely cause | Safe diagnosis / resolution |
|---|---|---|
| WebSocket authentication fails | Wrong credential type, expired key or wrong agent ID | Confirm registration key vs runtime agent key; rotate through Switch process; never print key |
| Agent registered twice | Startup registration ran repeatedly | Stop duplicate process; inspect Switch agents; preserve intended agent ID; change startup to reuse stored ID |
| No message in Discord | Bridge/room/agent connection issue | Check Switch bridge status, room claim, allowed room ID and event delivery |
| Agent sees room event but ignores it | Not addressed to agent, wrong owner or wrong room | Inspect redacted identity fields; verify exact opaque participant/room IDs |
| Agent replies twice | Duplicate process or missing event dedupe | Enforce singleton; inspect event ID ledger and outbound idempotency |
| Reconnect loops | Invalid cursor/generation or host outage | Follow current Switch reconnect contract; on `gap` read room context; on `taken_over` stop reconnect |
| Plan contains an invented task | Model/domain validation gap | Treat as blocker; test title provenance and task ID membership; no plan mutation until fixed |
| Approval did not apply | Proposal expired/stale/wrong code or not unique | Query pending proposals; confirm exact command and revision; regenerate stale proposal |
| Week says "holds" incorrectly | Availability/fixed event/estimate inputs incomplete | Recompute deterministic capacity; if missing data, report `insufficient_data` |
| Task missing from day plan | Not in approved week pool, parked/completed or assigned another date | Query task status and placement; do not create replacement task automatically |
| Latest wake looks wrong | Wrong prep/commute buffer, timezone or first required start | Verify IANA zone and owner-provided buffers; inspect backplan inputs |
| SQLite locked | Multiple writers or long transaction | Confirm one process; shorten transaction; use configured busy timeout; investigate WAL health |
| Database missing after restart | Volume not mounted or wrong DB path | Stop writes, inspect mounts and paths, restore verified backup only after confirmation |
| Reminder duplicates | Scheduler idempotency not enforced | Verify unique `(local_date,type)` key and transaction |
| Model errors | OpenRouter quota/key/model/network/schema mismatch | Verify `OPENAI_BASE_URL`, model ID, key presence without printing it; check provider status; bounded retry; clear unavailable response |
| Neon/Postgres connection fails | Wrong URL, SSL query mismatch, paused project or firewall | Check `DATABASE_URL` presence without printing it; URL normalization handles `sslmode`/`channel_binding`; run `zasky-maintenance status`; verify Neon is awake |
| `cached statement plan is invalid` | PgBouncer/Neon prepared statement cache after DDL | The app disables asyncpg statement caching; restart the writer after migrations |
| `value out of int32 range` on Switch sequence | Old `INTEGER` cursor columns | Apply migration `9f4c1a7b2d30`; both sequence columns must be `BIGINT` |
| Dashboard API 401 | Missing/wrong `DASHBOARD_API_KEY` bearer token | Confirm the Vercel `ZASKY_DASHBOARD_TOKEN` matches the protected env value; never print the token |
| Dashboard API 503 | Backend token not configured or Vercel token missing | Set `DASHBOARD_API_KEY` on the VPS and `ZASKY_DASHBOARD_TOKEN` in Vercel, then restart/redeploy |
| Vercel dashboard cannot reach VPS | Port 8100 blocked or wrong `NEXT_PUBLIC_API_URL` | `sudo ufw allow 8100/tcp`; check cloud security group; use `http://VPS_IP:8100` (port 8000 is Switch) |
| Dashboard shows empty today | No approved plan for the local date | Confirm `TIMEZONE`; approve a `plan_day` proposal or run the dashboard seed script |
| Discord setup returns 403 | Bot lacks Manage Channels or is not in the guild | Grant View Channels + Manage Channels, verify guild ID, rerun the setup script |
| Discord setup returns 401 | Invalid bot token or wrong token type | Set `DISCORD_BOT_TOKEN` to the bot token, not the application/client secret |
| Briefing stays in main room | Channel ID or bot token not configured | Add the `#daily-briefings` ID and `DISCORD_BOT_TOKEN` to the protected env and restart |
| Reconcile summary not posted | `DISCORD_RECONCILE_ALERTS_CHANNEL_ID` missing or bot lacks Send Messages | Add the ID, grant Send Messages in `#reconcile-alerts`, restart |
| Execution result returns 503 | `DISCORD_AI_WORKSPACE_CHANNEL_ID` or token missing | Add both, restart, retry the internal endpoint |
| Execution result returns 502 | Discord rejected the message | Check bot permissions in `#ai-workspace`; inspect the logged `DISCORD_HTTP_*` code only |
| Spend cap reached | Monthly hard limit | Stop model calls; do not silently raise cap; operator must authorize changed cap |
| Backup fails | Disk full, encryption key unavailable or SQLite copied unsafely | Preserve DB, free only safe space, use SQLite online backup/checkpoint process; retest restore |
| `gap` event received | Switch could not replay full continuity | Reread room context; do not interpret old events as fresh commands |
| `taken_over` received | Another connection generation took control | Stop reconnecting from this instance; investigate duplicate process/deployment |

When diagnosing, capture timestamps, correlation IDs and error codes only. Never paste secret values or raw private task/message bodies into logs or bug reports.
