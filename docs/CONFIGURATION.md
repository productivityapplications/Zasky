# Configuration Reference

All configuration is validated at startup. Secrets are server-only. Unknown or invalid values should fail closed.

| Variable | Required | Purpose | Visibility / rules |
|---|---:|---|---|
| `APP_ENV` | Yes | `development`, `test`, `staging`, `production` | Server-only |
| `LOG_LEVEL` | No | Logging verbosity; default `INFO` | Server-only; never log secrets |
| `DATABASE_URL` | Yes | SQLite DB path on persistent volume | Server-only; absolute persistent path in production |
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
| `OPENAI_API_KEY` | Yes for model | Responses API credential | Secret |
| `OPENAI_MODEL` | Yes for model | Verified supported model ID | Server-only |
| `OPENAI_MAX_INPUT_TOKENS` | Yes | Maximum constructed request input tokens; cap context before cost reservation | Positive bounded integer |
| `OPENAI_MAX_OUTPUT_TOKENS` | Yes | Maximum generated output tokens per request | Positive bounded integer |
| `OPENAI_STORE` | No | Provider storage behavior if supported; default false where available | Server-only; verify current API semantics |
| `MAX_LLM_REQUESTS_PER_DAY` | Yes | Daily request hard ceiling | Positive integer; operator may lower |
| `MAX_LLM_SPEND_USD_MONTH` | Yes | Monthly spend hard ceiling | Required before enabling paid model |
| `OPENAI_INPUT_USD_PER_1M` | Yes for local cost enforcement | Verified input-token price per 1M tokens | Required; from current provider pricing, not a guessed value |
| `OPENAI_OUTPUT_USD_PER_1M` | Yes for local cost enforcement | Verified output-token price per 1M tokens | Required; from current provider pricing, not a guessed value |
| `OPENAI_PRICE_EFFECTIVE_DATE` | Yes | Effective date/source version for configured price schedule | Required for auditability |
| `TIMEZONE` | Yes | IANA zone, provisional `Africa/Lagos` | Server-only |
| `CAPACITY_PCT` | Yes | Weekly capacity reserve setting; default 65 | Integer 60–70 |
| `WEEK_START_DAY` | Yes | Weekly boundary convention; Monday recommended | Valid weekday; confirmed at intake |
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
| `BACKUP_DIR` | Yes | Persistent encrypted backup destination | Server-only; restricted permissions |
| `MAX_MESSAGE_CHARS` | No | Inbound body size; default 8000 | Positive integer <= product cap |

## Secret handling
- Never prefix a secret with `NEXT_PUBLIC_` or similar client exposure convention.
- Do not commit `.env`, provider keys, Discord tokens or SSH keys.
- `SWITCH_REGISTRATION_KEY` is not the same as `SWITCH_AGENT_API_KEY`; delete the registration secret from runtime configuration after registration if no longer needed.
- Discord bridge token remains in Switch's configuration, not Zasky.
- Keep encryption keys for backups separate from the backup files.
- Redact environment dumps, exception traces and CI output.

## Cost controls
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
