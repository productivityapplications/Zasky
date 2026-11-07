# Configuration Reference

All configuration is validated at startup. Secrets are server-only. Unknown or invalid values should fail closed.

| Variable | Required | Purpose | Visibility / rules |
|---|---:|---|---|
| `APP_ENV` | Yes | `development`, `test`, `staging`, `production` | Server-only |
| `LOG_LEVEL` | No | Logging verbosity; default `INFO` | Server-only; never log secrets |
| `DATABASE_URL` | Yes | SQLite path or Neon/Postgres URL | Server-only. SQLite: `sqlite+aiosqlite:///absolute/path.db`. Postgres: `postgresql://...` or `postgresql+asyncpg://...`; `sslmode`/`channel_binding` are normalized for asyncpg |
| `SWITCH_BASE_URL` | Yes | Switch API base URL | Server-only; HTTPS/WSS; configured host allow-list |
| `SWITCH_AGENT_ID` | Yes | Registered agent identity | Server-only, not secret but private |
| `SWITCH_AGENT_API_KEY` | Yes | Runtime agent bearer credential | Secret |
| `SWITCH_REGISTRATION_KEY` | Only if registering | One-time registration credential | Secret; remove after successful registration |
| `SWITCH_CONNECTION_ID` | Yes | Stable connection identifier | Server-only |
| `SWITCH_ROOM_ID` | Yes | Exact allowed room ID | Server-only/private |
| `OWNER_SWITCH_PARTICIPANT_ID` | Yes | Exact owner participant ID | Server-only/private |
| `SWITCH_WS_URL` | No | Explicit WebSocket URL override; normally derived from `SWITCH_BASE_URL` and `SWITCH_AGENT_ID` | Server-only; `ws://` or `wss://` |
| `SWITCH_RECONNECT_MIN_SECONDS` | No | Initial reconnect backoff; default 1 | Bounded positive number |
| `SWITCH_RECONNECT_MAX_SECONDS` | No | Maximum reconnect backoff; default 30 | Bounded positive number |
| `OPENAI_API_KEY` | Yes for model | OpenRouter credential | Secret |
| `OPENAI_BASE_URL` | Yes for model | OpenRouter OpenAI-compatible base URL; default `https://openrouter.ai/api/v1` | Server-only; HTTPS |
| `OPENAI_MODEL` | Yes for model | Verified model ID; default `openai/gpt-4o-mini` | Server-only |
| `OPENAI_MAX_INPUT_TOKENS` | Yes | Maximum constructed request input tokens; bounds worst-case cost | Positive bounded integer |
| `OPENAI_MAX_OUTPUT_TOKENS` | Yes | Maximum generated output tokens per request; configured 600 | Positive bounded integer |
| `OPENAI_STORE` | No | Provider storage flag if supported; default false | Server-only |
| `TYPING_PLACEHOLDER_ENABLED` | No | Post an immediate `…` placeholder while the model works; default true | Boolean; Switch 0.31.0 has no edit/typing operation |
| `MAX_LLM_REQUESTS_PER_DAY` | Yes | Daily request hard ceiling | Positive integer; operator may lower |
| `MAX_LLM_SPEND_USD_MONTH` | Yes | Monthly spend hard ceiling | Required before enabling paid model |
| `OPENAI_INPUT_USD_PER_1M` | Yes for local cost enforcement | Input price per 1M tokens; configured `0.15` for gpt-4o-mini | Required; verified pricing source/date |
| `OPENAI_OUTPUT_USD_PER_1M` | Yes for local cost enforcement | Output price per 1M tokens; configured `0.60` for gpt-4o-mini | Required; verified pricing source/date |
| `OPENAI_PRICE_EFFECTIVE_DATE` | Yes | Effective date/source version for configured price schedule | Required for auditability |
| `TIMEZONE` | Yes | IANA zone; confirmed `Africa/Lagos` | Server-only |
| `CAPACITY_PCT` | Yes | Weekly capacity reserve setting; default 65 | Integer 60–70 |
| `WEEK_START_DAY` | Yes | Weekly boundary convention; confirmed Monday | Valid weekday |
| `DAILY_TASK_LIMIT` | Yes | Daily selected-task cap; fixed at 3 | Do not raise without product revision |
| `TRANSITION_BUFFER_MIN` | Yes | Buffer between blocks; candidate 10 | Non-negative integer |
| `MORNING_PREP_MIN` | Yes | Time needed after waking before first required start | Non-negative integer, owner-confirmed |
| `COMMUTE_BUFFER_MIN` | Yes | Commute buffer | Non-negative integer, owner-confirmed |
| `MORNING_PROMPT_TIME` | No | Morning reminder local time; candidate 07:00 | `HH:MM` |
| `EVENING_PROMPT_TIME` | No | Evening reminder local time; candidate 20:00 | `HH:MM` |
| `REMINDERS_ENABLED` | No | Enable reminders; default false | Boolean |
| `WEEKLY_AVAILABILITY_JSON` | Yes | Owner-supplied weekday work windows | Validated JSON; local `HH:MM` windows; no guessed hours |
| `HEALTH_BIND_HOST` | Yes | Health bind address | `127.0.0.1` default |
| `HEALTH_BIND_PORT` | Yes | Private health port | Host firewall/private only |
| `DISCORD_BOT_TOKEN` | For Discord routing | Bot token used only for outbound application notifications | Secret; server-only; same bot as Switch's Discord bridge |
| `DISCORD_GUILD_ID` | Setup script only | Target Discord server ID | Not needed by the runtime |
| `DISCORD_API_BASE_URL` | No | Discord REST base URL | Default `https://discord.com/api/v10`; server-only |
| `CALENDAR_FEED_TOKEN` | Optional | Read-only token for direct `.ics` subscription URLs | Secret; query `?token=`; dashboard bearer auth also works |
| `CALENDAR_ALARM_MINUTES` | No | VALARM lead time for day-plan tasks | Default `5`; 0–120 |
| `DISCORD_DAILY_BRIEFINGS_CHANNEL_ID` | For Daily Briefing routing | Destination for approved `plan_day` briefings | Discord snowflake; `#daily-briefings` |
| `DISCORD_RECONCILE_ALERTS_CHANNEL_ID` | For recovery routing | Destination for approved `reconcile` summaries | Discord snowflake; `#reconcile-alerts` |
| `DISCORD_AI_WORKSPACE_CHANNEL_ID` | For execution results | Destination for Execution Sub-Agent results | Discord snowflake; `#ai-workspace` |
| `DISCORD_CONTROL_CHANNEL_ID` | Optional | Created control channel ID | Discord snowflake; `#zasky-control` |
| `DISCORD_DASHBOARD_SYNC_CHANNEL_ID` | Optional | Created dashboard sync channel ID | Discord snowflake; `#dashboard-sync` |
| `DASHBOARD_BIND_HOST` | No | Owner dashboard API bind address | Default `0.0.0.0` so Vercel can reach it |
| `DASHBOARD_PORT` | No | Owner dashboard API port | Default `8100`; port 8000 is used by Switch |
| `DASHBOARD_API_KEY` | Yes for dashboard | Bearer token required by every dashboard route | Secret; never `NEXT_PUBLIC_*`; rotate after demos |
| `DASHBOARD_CORS_ORIGINS` | No | Comma-separated allowed origins, or `*` | Default `*` for the hackathon staging demo |
| `BACKUP_DIR` | Yes | Persistent encrypted backup destination | Server-only; restricted permissions |
| `MAX_MESSAGE_CHARS` | No | Inbound body size; default 8000 | Positive integer <= product cap |

## Secret handling
- Never prefix a secret with `NEXT_PUBLIC_` or similar client exposure convention.
- Do not commit `.env`, provider keys, Discord tokens or SSH keys.
- `SWITCH_REGISTRATION_KEY` is not the same as `SWITCH_AGENT_API_KEY`; delete the registration secret from runtime configuration after registration if no longer needed.
- Discord bridge token remains in Switch's configuration, not Zasky.
- `DASHBOARD_API_KEY` is a server-side bearer secret. In Vercel it belongs in
  `ZASKY_DASHBOARD_TOKEN` with server-only visibility; never prefix either name
  with `NEXT_PUBLIC_`.
- `DISCORD_BOT_TOKEN` is server-only. The setup script reads it from the
  protected env file; it is never printed, committed or exposed to the model.
  The bot needs View Channels and Manage Channels for setup, plus Send Messages
  and Embed Links in the three notification channels.
- Keep encryption keys for backups separate from the backup files.
- Redact environment dumps, exception traces and CI output.

## Cost controls
- Provider decision: the operator explicitly selected OpenRouter Chat Completions rather than the OpenAI Responses API for this hackathon build. The seven-tool contract is unchanged.
- No paid service enabled until the operator records a cap.
- Before each provider call, reserve its upper-bound cost (bounded input + maximum output at the verified pricing schedule); settle against provider usage. Keep unknown outcomes reserved until reconciled. Warn at 80% of monthly model budget; hard-stop new model calls at 100%.
- VPS and AI cost together must remain below the operator's total monthly cap.
- No TTS/video service charge without explicit permission.


## Availability JSON example

This is a schema example only; do not treat the hours as the operator's schedule:

```json
{
  "monday": [{"start": "09:00", "end": "17:00"}],
  "tuesday": [{"start": "10:00", "end": "16:00"}],
  "wednesday": [],
  "thursday": [{"start": "09:00", "end": "17:00"}],
  "friday": [{"start": "09:00", "end": "15:00"}],
  "saturday": [],
  "sunday": []
}
```

Each weekday maps to zero or more non-overlapping local-time work availability windows. Validate `end > start`; overnight windows are out of scope for MVP unless explicitly added. The owner timezone determines local-time interpretation.

`OPENAI_MAX_INPUT_TOKENS` is required: cap the constructed request context before computing a worst-case cost reservation.
