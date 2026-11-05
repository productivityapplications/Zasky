# Zasky — Operator Intake / Readiness Check

**Purpose:** One consolidated intake before implementation. Complete once; do not interrupt implementation with routine questions later. Keep secrets out of this file. Record only where a secret is stored and whether presence/permissions were verified.

Status values: `PENDING`, `PASS`, `BLOCKED`, `NOT_APPLICABLE`.  
Priority: `CRITICAL` blocks the affected build path; `OPTIONAL` can use a documented default.

| ID | Input / decision | Required? | Current source / default | Operator answer | Validation evidence | Status | Where used / authorization boundary |
|---|---|---|---|---|---|---|---|
| I-01 | Existing repository URL/path and Git access | Critical | Handoff says new build; inspect actual repo |  | Git status/read access | PENDING | Preserve existing work; no force-push |
| I-02 | Switch hosting URL, workspace and version | Critical | Confirm official current deployment |  | TLS/health/API verification | PENDING | WebSocket/HTTP endpoint; no access bypass |
| I-03 | Switch agent already registered? | Critical | Register once only if absent |  | Existing agent ID check | PENDING | Never duplicate or overwrite registration |
| I-04 | Switch registration credential | Critical if agent absent | Store outside this file | Secret stored at: ___ | Registration test, value redacted | PENDING | One-time registration only |
| I-05 | Switch agent ID and runtime API key | Critical | Exact existing agent identity | ID: ___; secret location: ___ | Authenticated non-mutating check | PENDING | Server-only, never log |
| I-06 | Switch room ID for Zasky | Critical | One private Discord room |  | Exact room claim/context test | PENDING | Hard allow-list |
| I-07 | Owner Switch participant ID | Critical | Exact opaque participant ID |  | Owner and negative test identity | PENDING | Exact allow-list before model/data access |
| I-08 | Discord server/private channel and bridge status | Critical for Discord path | Discord is preferred interface |  | Message round-trip / bot scope review | PENDING | Bridge token belongs to Switch, not Zasky |
| I-09 | Isolated test workspace/channel available? | Critical | Use non-production test data |  | Prove isolation | PENDING | Required for E2E/demo |
| I-10 | VPS provider, region, OS, IPv4/hostname | Critical for resilient deployment | Linux VPS with persistent disk |  | SSH + resource check | PENDING | Monthly host spend ceiling required |
| I-11 | SSH access and operator identity | Critical | Key-only access |  | Successful login; password login disabled where possible | PENDING | No root login; no private key in repo |
| I-12 | Persistent disk location and size | Critical | Must persist SQLite and backups |  | Write/restart/read test | PENDING | Do not use ephemeral container FS |
| I-13 | VPS monthly cost ceiling | Critical | No assumed free tier | USD/local currency cap: ___ | Provider billing settings checked | PENDING | Stop before exceeding cap |
| I-14 | External network/firewall permissions | Critical | Only Switch-required ports + SSH |  | Firewall inspection | PENDING | No public Zasky API/DB |
| I-15 | OpenAI API account/key | Critical for hosted model | Store in secret manager/env file | Secret location: ___ | Key presence check, redacted | PENDING | Key does not imply unlimited spending |
| I-16 | Model identifier and tool-call capability | Critical | Verify a currently supported Responses API model |  | Small non-production tool-schema test | PENDING | Do not assume model is available |
| I-17 | Monthly model spend cap | Critical | Hard cap required | USD cap: ___ | Billing/usage alert configuration | PENDING | 80% warning; 100% hard stop |
| I-18 | Daily request/output token limits | Required | Safe default to be set after cap |  | Config tested | PENDING | Prevent runaway loops/cost |
| I-19 | Provider data retention/training preference | Critical | Verify current terms/settings; minimize stored data |  | Settings/terms reviewed | PENDING | Do not promise deletion/retention not verified |
| I-20 | Owner timezone | Critical | Provisional: `Africa/Lagos` | Confirm/change: ___ | IANA timezone parses | PENDING | UTC instants; local dates |
| I-21 | Weekly availability windows by weekday | Critical | Must be owner supplied; no guessed capacity |  | Validate totals and overlaps | PENDING | Capacity and scheduling |
| I-22 | Fixed events for initial demo week | Critical for realistic schedule | Owner-supplied list |  | No conflicts in seed | PENDING | Zasky never moves these |
| I-23 | Morning preparation buffer | Required | Safe default candidate: 30 min; confirm |  | Backplan test | PENDING | Latest-wake math |
| I-24 | Commute buffer | Required | Safe default candidate: 0 min only if confirmed |  | Backplan test | PENDING | Latest-wake math |
| I-25 | Transition buffer between blocks | Required | Candidate: 10 min |  | Conflict tests | PENDING | Capacity and daily schedule |
| I-26 | Capacity percentage | Required | Locked baseline 65%; allowed 60–70% | Confirm 65% or choose 60–70: ___ | Config validation | PENDING | Slack reserve |
| I-27 | Daily task ceiling | Fixed | 3 | No change | Unit test | PASS | Product invariant |
| I-28 | Morning/evening reminder times | Optional | Candidate 07:00 / 20:00 local; reminders can be disabled |  | Delivery test | PENDING | No reminder if disabled |
| I-29 | Seed year goals and evidence of done | Optional for infrastructure, required for representative demo | Owner chooses 3–5 |  | Owner validates wording | PENDING | Never invent goal content |
| I-30 | Seed month commitments, estimates, deadlines/consequences | Required for realistic planning demo | Owner supplies |  | Capacity/reality check | PENDING | No inferred commitments |
| I-31 | Initial weekly task titles and estimates | Required for demo | Owner supplies specific work items |  | Every task maps to commitment | PENDING | Tasks not generated by model |
| I-32 | Privacy/data handling constraints | Critical | Owner defines prohibited data/categories |  | Review against logs, prompts, backups | PENDING | Least data needed |
| I-33 | Backup destination and encryption key handling | Critical | Encrypted daily backups, 7 daily + 4 weekly |  | Restore drill | PENDING | Key stored separately |
| I-34 | Demo audience/story/pronunciation | Required before video | Hackathon judges; pronounce "Zasky" as operator confirms |  | Script reviewed | PENDING | Do not show private data |
| I-35 | Demo output directory and permitted public artifacts | Required | Repo `artifacts/demo/` only if appropriate |  | Writable path and redaction | PENDING | No public secrets/private URLs |
| I-36 | Google AI TTS or fallback permission | Optional | Check free availability and terms first |  | Quota/terms/credentials checked | PENDING | No charges without authorization |
| I-37 | Production deployment authority | Critical | **Not granted by default** | Explicitly authorize exact scope or "staging only": ___ | Exact authorization recorded | PENDING | No production release without explicit scope |
| I-38 | Destructive/irreversible action authority | Critical | **Not granted by default** | Allowed actions/limits: ___ | Operator wording recorded | PENDING | No deletion, financial or legal actions |
| I-39 | Preview/staging deployment authority | Required if VPS deploy occurs | Exact test host/scope |  | Deployment smoke test | PENDING | Does not authorize production |
| I-40 | Allowed monthly total cost (VPS + model + optional services) | Critical | No spending assumed | Cap and currency: ___ | Provider billing checks | PENDING | Hard stop at cap |
| I-41 | Current model input/output pricing and effective date | Critical if paid model enabled | Verify exact model pricing at intake; no hard-coded stale price | Input/output rate + source/date: ___ | Pricing schedule checked against provider source | PENDING | Used for local cost ledger/hard stop |
| I-42 | Week start convention | Required | Monday recommended; must be confirmed | Day: ___ | Week/date-boundary test | PENDING | Placement and capacity calculations |

## Intake completion rules

- **PASS** only after objective evidence; a copied secret is not evidence and must not be placed here.
- A critical item can be marked `NOT_APPLICABLE` only with a documented reason and safe alternative.
- For noncritical unspecified settings, use the explicit documented defaults in `docs/CONFIGURATION.md`.
- If model spend or host spend cap is absent, no paid resource may be enabled.
- If production authority is not explicitly granted, the permitted final state is protected staging/test plus release instructions.
- The UI-reference image field from the generic workflow is **not applicable**: Zasky's MVP is chat-only and has no frontend. Do not ask the operator for mockups or invent reference assets.
- The `stageshow` UI skill is **not applicable** to the chat-only MVP. Do not install it unless a frontend becomes part of an explicitly revised scope.

## Readiness sign-off (operator inputs, not routine phase approvals)

- Critical inputs complete: `YES / NO`
- Switch-to-private-Discord round trip verified: `YES / NO`
- Owner/room access controls tested: `YES / NO`
- Cost ceilings and spend authorization recorded: `YES / NO`
- Backup destination/restore plan verified: `YES / NO`
- Production authority: `STAGING ONLY / EXPLICITLY AUTHORIZED (attach exact scope)`
- Intake completed timestamp: ``
