# Zasky — Error and Edge-Case Matrix

| Area | Condition | Expected system behavior | State change | Test |
|---|---|---|---|---|
| Switch ingress | Sender ID is not configured owner | Ignore or neutral denial; disclose no plan facts | No domain write/model context | SEC-01 |
| Switch ingress | Room ID is not allow-listed | Ignore | None | SEC-02 |
| Switch ingress | Message is not addressed to agent | Do not process as an agent request | None | INT-01 |
| Switch ingress | Duplicate event ID/cursor | Return prior outcome or no-op | No duplicate write | INT-02 |
| Switch ingress | Malformed event envelope | Reject, log redacted error | None | INT-03 |
| Switch transport | WebSocket disconnect | Reconnect with same connection ID/cursor/generation per current protocol | Preserve event cursor | INT-04 |
| Switch transport | `gap` control frame | Re-read room context before next reply; don't replay old messages as new commands | Update cursor only per protocol | INT-05 |
| Switch transport | `evicted/taken_over` | Stop reconnecting from displaced instance; operator investigates | No domain write | INT-06 |
| Switch transport | Heartbeat lapse | Recover using documented reconnect behavior | Preserve highest processed sequence | INT-07 |
| Authentication | Wrong runtime key / registration key used | Fail closed; explain configuration error without echoing key | None | SEC-03 |
| Owner identity | Display name changes | No effect; exact opaque Switch ID remains authority | None | SEC-04 |
| Goals | More than five active goals in one year | Reject; ask owner to retire/replace a goal | None | DOM-01 |
| Goals | Missing evidence of done | Ask owner; do not create incomplete goal | None | DOM-02 |
| Goals | Duplicate normalized title | Warn/reject or require explicit update | None until confirmed | DOM-03 |
| Commitments | Missing estimate/month/title | Ask for required field | None | DOM-04 |
| Commitments | Goal no longer active | Reject link; allow unlinked commitment only if owner explicitly chooses | None | DOM-05 |
| Tasks | Model invents title from goal | Domain provenance validation rejects | None | SEC-05 |
| Tasks | Task title over 200 chars | Validation error | None | VAL-01 |
| Tasks | Estimate is zero/negative | Validation error | None | VAL-02 |
| Weekly plan | Availability missing | Do not claim capacity; request data or show unscheduled task list | Proposal not approved | DOM-06 |
| Weekly plan | Capacity budget exceeded | Show overage and ask owner to remove/reduce work | No weekly placement commit | DOM-07 |
| Weekly plan | Task date outside selected week | Reject item | None | VAL-03 |
| Weekly plan | Fixed event overlap | Reject or propose another gap; never move fixed event | Proposal not committed | DOM-08 |
| Weekly plan | Commitment already placed/task duplicated | Detect duplicate and ask update/confirm | No duplicate rows | DOM-09 |
| Day plan | No approved week tasks | Say no tasks are available; don't generate any | No day plan | DOM-10 |
| Day plan | All candidate tasks parked/completed | Show empty pool and status | No day plan | DOM-11 |
| Day plan | More than three candidate tasks | Select at most three by explicit priority/order; show omitted items still in pool | Proposal only | DOM-12 |
| Day plan | Zero candidate tasks selected | No `must` required | Approved empty plan only if owner explicitly requests | DOM-13 |
| Day plan | Non-empty plan without exactly one must | Reject before save | None | DOM-14 |
| Battery | Low battery | One must + at most one short/admin task from existing pool | Proposal only | DOM-15 |
| Backplan | Prep/commute missing | Show unavailable/assumed-only calculation; do not assert precise latest wake | No false promise | DOM-16 |
| Backplan | First task before fixed event conflict | Reorder only if safe; otherwise flag conflict | Proposal only | DOM-17 |
| Reconcile | Current time missing/ambiguous | Ask one essential clarification or use verified server local time if it truly matches "now" | None until understood | DOM-18 |
| Reconcile | Long call/scroll delay | Replan remaining day from existing pool | Proposal only | E2E-03 |
| Reconcile | Multi-day outage within current week | Bulk proposal within same week | Proposal only | E2E-04 |
| Reconcile | Week already ended | Leave work unplaced and ask to renegotiate next week | No cross-week auto-shift | DOM-19 |
| Reconcile | Insufficient weekly slack | Mark `week_at_risk`, show arithmetic and options | Proposal only | DOM-20 |
| Reconcile | Fixed event collision | Preserve event; flag no feasible schedule | Proposal only or fail | DOM-21 |
| Proposal | Code does not exist | No mutation; generic invalid code response | None | SEC-06 |
| Proposal | Expired | Mark expired; regenerate proposal | None | DOM-22 |
| Proposal | Base revision changed | Mark stale; require a fresh proposal | None | SEC-07 |
| Proposal | Two pending proposals for same scope | Exact code required; second approval serialized/stales as needed | At most one successful commit | CON-01 |
| Proposal | Natural-language "looks good" | Do not approve; explain exact command | None | SEC-08 |
| Proposal | Repeated approval | Idempotent "already applied" response | No second mutation | CON-02 |
| Park | Missing resume note | Ask for note; do not park | None | DOM-23 |
| Park | Task already completed | Reject/no-op | None | DOM-24 |
| Resume | Task not parked | Report current state; no write | None | DOM-25 |
| Complete | Ambiguous task name | Ask which exact task; no tool call | None | DOM-26 |
| Complete | Duplicate completion | Idempotent response | No new audit duplicate beyond optional duplicate record | CON-03 |
| Query | No matching data | Empty state statement | Read-only | E2E-05 |
| Query | Request refers to unknown ID | Not found; disclose no other record | Read-only | SEC-09 |
| AI | Provider timeout | Bounded retry once; then transparent error | No partial write | INT-08 |
| AI | Invalid tool arguments twice | Ask owner to restate; no mutation | None | SEC-10 |
| AI | Prompt injection requests secrets or new tools | Ignore instruction; continue only safe allowed intent or refuse | None | SEC-11 |
| AI/cost | 80% monthly budget | Warn once/at threshold | Ledger update | OPS-01 |
| AI/cost | 100% monthly spend cap | Hard stop model API calls | No paid request | OPS-02 |
| Database | Busy/locked | bounded retry on safe operation; no duplicate mutation | Transaction rollback | INT-09 |
| Database | Disk full | Fail closed, alert operator, preserve DB | No partial commit | INT-10 |
| Database | Corruption | Stop writes; preserve file and logs; restore tested backup only after operator-authorized recovery | No blind overwrite | OPS-03 |
| Scheduler | Duplicate reminder trigger | Unique date/type prevents second send | One reminder row | INT-11 |
| Scheduler | Service restarts after grace window | Record skipped reminder, don't spam late | Dispatch record | INT-12 |
| Backup | Backup copy made while WAL active | Use online backup or safe checkpoint process | Verified snapshot | OPS-04 |
| Backup | Restore test fails | Block release; preserve prior backup; diagnose | No production overwrite | OPS-05 |
| Deployment | New instance starts before old writer stops | Singleton lock prevents second writer; no room takeover | No duplicate event processing | CON-04 |
| Deployment | Production authority absent | Stop at staging/test and deliver release instructions | No production change | OPS-06 |
| Discord | Bridge unavailable | Mark integration unavailable; retry boundedly; do not use direct bot bypass | No fabricated response | INT-13 |
| Demo | Google free TTS unavailable | Use genuinely free permitted fallback or human narration; document | No charges | DEMO-01 |
| Demo | Private data visible | Stop recording, reset demo, redact and re-review | No artifact published | DEMO-02 |
