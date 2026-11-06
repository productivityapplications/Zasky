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
| Spend cap reached | Monthly hard limit | Stop model calls; do not silently raise cap; operator must authorize changed cap |
| Backup fails | Disk full, encryption key unavailable or SQLite copied unsafely | Preserve DB, free only safe space, use SQLite online backup/checkpoint process; retest restore |
| `gap` event received | Switch could not replay full continuity | Reread room context; do not interpret old events as fresh commands |
| `taken_over` received | Another connection generation took control | Stop reconnecting from this instance; investigate duplicate process/deployment |

When diagnosing, capture timestamps, correlation IDs and error codes only. Never paste secret values or raw private task/message bodies into logs or bug reports.
