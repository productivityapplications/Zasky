# Discord Server Setup

`scripts/setup_discord.py` is a one-off operator script that creates the Zasky
HQ category and five text channels through the Discord REST API. It does **not**
use Switch and does not read inbound Discord events.

## What it creates

```text
Zasky HQ
├── #zasky-control
├── #daily-briefings
├── #reconcile-alerts
├── #ai-workspace
└── #dashboard-sync
```

The script is idempotent:

- reuses an existing category named `Zasky HQ`;
- reuses an existing channel with the same name inside that category;
- refuses to move a same-named channel that exists outside the category;
- never deletes anything.

## Bot permissions

The Discord bot must have:

- View Channels;
- Manage Channels for the setup run;
- Send Messages and Embed Links in the three notification channels.

The bot token is read from the protected environment, never printed.

## Environment

Add the bot token and guild ID to `/root/Zasky-secrets/zasky.env` (mode `0600`):

```dotenv
DISCORD_BOT_TOKEN=<bot token>
DISCORD_GUILD_ID=<discord server ID>
```

The script also accepts `DISCORD_APP_BOT_TOKEN`, `DISCORD_TOKEN` or `BOT_TOKEN`
as fallback token names.

## Review and run

The script was reviewed before execution. Run it only after review:

```bash
cd /root/Zasky
uv run python scripts/setup_discord.py \
  --env-file /root/Zasky-secrets/zasky.env \
  --guild-id YOUR_DISCORD_SERVER_ID
```

Optional safe inspection:

```bash
uv run python scripts/setup_discord.py \
  --env-file /root/Zasky-secrets/zasky.env \
  --guild-id YOUR_DISCORD_SERVER_ID \
  --dry-run
```

The script writes `data/discord_channels.json` (mode `0600`) and prints the exact
channel-ID lines for the protected env file. `data/` is gitignored.

## Backend routing

After the run, add the printed lines:

```dotenv
DISCORD_CONTROL_CHANNEL_ID=...
DISCORD_DAILY_BRIEFINGS_CHANNEL_ID=...
DISCORD_RECONCILE_ALERTS_CHANNEL_ID=...
DISCORD_AI_WORKSPACE_CHANNEL_ID=...
DISCORD_DASHBOARD_SYNC_CHANNEL_ID=...
```

Routing behavior:

- approved `plan_day` → `#daily-briefings`;
- approved `reconcile` → `#reconcile-alerts`;
- Execution Sub-Agent results → `#ai-workspace` via
  `POST /api/internal/execution-results` with the dashboard bearer token.

`#zasky-control` and `#dashboard-sync` are created for the owner's future use but
are not automatically wired into the Switch room. The conversational interface
remains the configured Switch room.

If the channel IDs or bot token are absent, the Daily Briefing falls back to the
main Switch room and the other routes report that they are not configured.
