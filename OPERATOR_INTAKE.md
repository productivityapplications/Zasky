# Zasky — Operator Intake / Readiness Check

**Purpose:** One consolidated intake before implementation. Complete once; do not interrupt implementation with routine questions later. Keep secrets out of this file. Record only where a secret is stored and whether presence/permissions were verified.

Status values: `PENDING`, `PASS`, `BLOCKED`, `NOT_APPLICABLE`.  
Priority: `CRITICAL` blocks the affected build path; `OPTIONAL` can use a documented default.

**Intake record date:** 2026-11-06  
**Scope decision:** local staging only; VPS deployment, encrypted backup automation, full micro-USD reservation ledger and production release are intentionally deferred. See `AI_HANDOFF.md`.

| ID | Input / decision | Required? | Current source / default | Operator answer | Validation evidence | Status | Where used / authorization boundary |
|---|---|---|---|---|---|---|---|
| I-01 | Existing repository URL/path and Git access | Critical | Local `/root/Zasky`; Git `main` | Local repository; read/write confirmed | Git status clean; `origin/main` reachable; no force-push | **PASS** | Preserve existing work |
| I-02 | Switch hosting URL, workspace and version | Critical | Local Switch 0.31.0 | Local Switch at `http://127.0.0.1:8000` | `/health` 200; server 0.31.0; WebSocket protocol 9 | **PASS** | WebSocket/HTTP endpoint |
| I-03 | Switch agent already registered? | Critical | Register once only if absent | Registered `zasky` | Agent row exists; ops endpoint 200 | **PASS** | Never duplicate registration |
| I-04 | Switch registration credential | Critical if agent absent | Store outside this file | Admin-created registration key used once | Temporary key revoked; value redacted | **PASS** | One-time registration only |
| I-05 | Switch agent ID and runtime API key | Critical | Exact existing agent identity | Stored in protected env | Key presence/length checked; value redacted; ops call 200 | **PASS** | Server-only; never log |
| I-06 | Switch room ID for Zasky | Critical | One private Discord room | Stored in protected env | Room claim/context success; exact value redacted | **PASS** | Hard allow-list |
| I-07 | Owner Switch participant ID | Critical | Exact opaque participant ID | Stored in protected env | Participant row and sender identity confirmed; value redacted | **PASS** | Exact allow-list before model/data access |
| I-08 | Discord server/private channel and bridge status | Critical for Discord path | Discord is preferred interface | Bridge connected; channel exists | Bridge/room present; **Switch reports `channel_public`** | **BLOCKED** | Must be `channel_private` or `@everyone` view denied |
| I-09 | Isolated test workspace/channel available? | Critical | Use non-production test data | Local test room exists | Only owner, agent, bridge and admin are members; visibility still public | **BLOCKED** | Fix channel privacy before acceptance/demo |
| I-10 | VPS provider, region, OS, IPv4/hostname | Critical for resilient deployment | Linux VPS with persistent disk | Deferred; local staging only | Local Ubuntu 24.04.5 host | **NOT_APPLICABLE** | Cloud architecture documented only |
| I-11 | SSH access and operator identity | Critical | Key-only access | Local host access only | Local shell; no VPS SSH configured | **NOT_APPLICABLE** | No production host |
| I-12 | Persistent disk location and size | Critical | Must persist SQLite and backups | Local `/root/Zasky/data` | 73 GiB free; SQLite on local disk | **NOT_APPLICABLE** | VPS disk deferred |
| I-13 | VPS monthly cost ceiling | Critical | No assumed free tier | $0 host spend | No VPS provisioned | **NOT_APPLICABLE** | Local only |
| I-14 | External network/firewall permissions | Critical | Only Switch-required ports + SSH | No public Zasky ports | Health binds `127.0.0.1`; Switch ports localhost-only | **NOT_APPLICABLE** | Production firewall review deferred |
| I-15 | OpenAI API account/key | Critical for hosted model | Store in secret manager/env file | Pending | No key present in repo/env | **BLOCKED** | Phase 4; key does not imply spend authority |
| I-16 | Model identifier and tool-call capability | Critical | Verify a currently supported Responses API model | Proposed `gpt-6-luna`; not yet tested | Pricing verified; live tool-schema test pending | **BLOCKED** | Phase 4 |
| I-17 | Monthly model spend cap | Critical | Hard cap required | **$20/month** | Cap recorded; 80% warning / 100% stop to implement | **PASS** | 80% warning; 100% hard stop |
| I-18 | Daily request/output token limits | Required | Safe default after cap | **100 requests/day** | Proposed 24k input / 2k output per request | **PASS** | Prevent runaway loops/cost |
| I-19 | Provider data retention/training preference | Critical | Verify current terms/settings; minimize stored data | Pending explicit acceptance | OpenAI API no training by default; abuse logs up to 30 days; `store=false` | **BLOCKED** | Phase 4 |
| I-20 | Owner timezone | Critical | Provisional `Africa/Lagos` | Pending confirmation | Host is `Europe/Berlin`; must confirm | **BLOCKED** | UTC instants; local dates |
| I-21 | Weekly availability windows by weekday | Critical | Must be owner supplied; no guessed capacity | Pending; synthetic demo option | None supplied | **BLOCKED** | Capacity and scheduling |
| I-22 | Fixed events for initial demo week | Critical for realistic schedule | Owner-supplied list | Pending; `none` acceptable | None supplied | **BLOCKED** | Zasky never moves these |
| I-23 | Morning preparation buffer | Required | Candidate 30 min; confirm | Pending confirmation | None confirmed | **BLOCKED** | Latest-wake math |
| I-24 | Commute buffer | Required | Candidate 0 min only if confirmed | Pending confirmation | None confirmed | **BLOCKED** | Latest-wake math |
| I-25 | Transition buffer between blocks | Required | Candidate 10 min | Pending confirmation | None confirmed | **BLOCKED** | Capacity and daily schedule |
| I-26 | Capacity percentage | Required | Locked baseline 65%; allowed 60–70% | 65% unless overridden | Product invariant | **PASS** | Slack reserve |
| I-27 | Daily task ceiling | Fixed | 3 | No change | Product invariant | **PASS** | Product invariant |
| I-28 | Morning/evening reminder times | Optional | Candidate 07:00 / 20:00; can disable | Defaults; reminders off | No reminder sent in Phase 1 | **PASS_WITH_DEFAULT** | No reminder if disabled |
| I-29 | Seed year goals and evidence of done | Optional for infrastructure | Owner chooses 3–5 | Pending synthetic approval | No owner content invented | **BLOCKED** | Demo only |
| I-30 | Seed month commitments, estimates, deadlines/consequences | Required for realistic planning demo | Owner supplies | Pending synthetic approval | No owner content invented | **BLOCKED** | Demo only |
| I-31 | Initial weekly task titles and estimates | Required for demo | Owner supplies specific work items | Pending synthetic approval | No owner content invented | **BLOCKED** | Demo only |
| I-32 | Privacy/data handling constraints | Critical | Owner defines prohibited data/categories | No secrets, no raw private text in logs, synthetic demo only | JSON logs exclude bodies; redaction active; DB stores no message body | **PASS** | Least data needed |
| I-33 | Backup destination and encryption key handling | Critical | Encrypted daily backups, 7 daily + 4 weekly | Deferred; manual online backup + restore | Phase 2 will prove restore; encryption production-only | **NOT_APPLICABLE** | Hackathon deferral |
| I-34 | Demo audience/story/pronunciation | Required before video | Hackathon judges; confirm pronunciation | Pending | Story documented; pronunciation not confirmed | **BLOCKED** | Demo only |
| I-35 | Demo output directory and permitted public artifacts | Required | `artifacts/demo/` | Pending publication permission | Path exists; synthetic-only rule | **BLOCKED** | No public secrets/private IDs |
| I-36 | Google AI TTS or fallback permission | Optional | Check free availability and terms first | Use free/local fallback; no charges | No paid service | **PASS_WITH_DEFAULT** | No charges without authorization |
| I-37 | Production deployment authority | Critical | **Not granted by default** | **Staging only** | Local staging only | **NOT_APPLICABLE** | No production release |
| I-38 | Destructive/irreversible action authority | Critical | **Not granted by default** | None | No destructive Zasky actions | **PASS** | No deletion/financial/legal actions |
| I-39 | Preview/staging deployment authority | Required if VPS deploy occurs | Exact test host/scope | Local staging authorized | Docker container on local host only | **PASS** | Does not authorize production |
| I-40 | Allowed monthly total cost (VPS + model + optional services) | Critical | No spending assumed | **$20/month** | Model cap $20; VPS $0; no other paid services | **PASS** | Hard stop at cap |
| I-41 | Current model input/output pricing and effective date | Critical if paid model enabled | Verify exact model pricing at intake | `gpt-6-luna`: $0.10 input / $0.50 output per 1M | OpenAI pricing page checked 2026-11-05; re-verify if model changes | **PASS** | Local cost guard |
| I-42 | Week start convention | Required | Monday recommended; confirm | Pending confirmation | None confirmed | **BLOCKED** | Placement/capacity calculations |

## Intake completion rules

- **PASS** only after objective evidence; a copied secret is not evidence and must not be placed here.
- A critical item can be marked `NOT_APPLICABLE` only with a documented reason and safe alternative.
- For noncritical unspecified settings, use the explicit documented defaults in `docs/CONFIGURATION.md`.
- If model spend or host spend cap is absent, no paid resource may be enabled.
- If production authority is not explicitly granted, the permitted final state is protected staging/test plus release instructions.
- The UI-reference image field from the generic workflow is **not applicable**: Zasky's MVP is chat-only and has no frontend. Do not ask the operator for mockups or invent reference assets.
- The `stageshow` UI skill is **not applicable** to the chat-only MVP. Do not install it unless a frontend becomes part of an explicitly revised scope.

## Readiness sign-off (operator inputs, not routine phase approvals)

- Critical inputs complete: **NO** — room privacy, OpenAI access, planning inputs and demo content remain open.
- Switch-to-private-Discord round trip verified: **NO** — transport/room ready; owner message pending.
- Owner/room access controls tested: **YES (automated)** — live negative test still to run.
- Cost ceilings and spend authorization recorded: **YES** — $20/month, 100 requests/day.
- Backup destination/restore plan verified: **NO** — Phase 2 manual online backup/restore.
- Production authority: **STAGING ONLY**
- Intake completed timestamp: `` (partial; 2026-11-06)
