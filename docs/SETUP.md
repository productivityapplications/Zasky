# Setup Guide

This guide applies after the coding agent has completed the intake and implementation. Do not put secrets in Git.

## Prerequisites
- Linux VPS with persistent disk and SSH key access.
- Docker Engine and Docker Compose plugin.
- Running Switch workspace and the current documented agent WebSocket protocol.
- Discord private server/channel connected through Switch.
- OpenAI API key and a verified Responses API model with function/tool calling.
- Operator-approved monthly infrastructure and model spend ceilings.

## First deployment
1. Clone the authorized repository and verify the expected commit.
2. Copy `.env.example` to a protected environment file outside the public repo or use Docker secrets.
3. Set file ownership to the service account and permissions to `0600`.
4. Verify required settings without printing secret values.
5. Run database migrations using the documented one-shot command.
6. Start the Zasky service with Docker Compose; deploy Switch using its official deployment instructions and pinned version.
7. Verify `/health/live` and private `/health/ready` from the host.
8. Verify the agent WebSocket connection; check logs for a successful handshake without token output.
9. In the exact private Discord room, send a harmless test message as the configured owner.
10. Confirm a reply appears in the same room; run a non-owner negative test.
11. Create and verify an encrypted backup; restore into a temporary isolated database.
12. Record service version, Git commit, connection test and backup evidence in `AI_HANDOFF.md`.

## First-run configuration
- Confirm owner participant ID and room ID using Switch's documented identifiers; treat both as opaque strings.
- Confirm IANA timezone and weekly availability windows.
- Enter fixed events, prep/commute/transition buffers and reminder preferences.
- Confirm capacity percentage (default 65%, allowed 60–70%).
- Add owner-chosen year goals and month commitments; add explicit weekly task titles and estimates.
- Do not ask Zasky to derive tasks automatically from goals.

## Local development
Use a separate `.env.test` and disposable SQLite database. Never point local tests at production data. Run tests and lint commands exactly as documented in `pyproject.toml`/CI. Local development is not a substitute for the protected Switch/Discord end-to-end round trip.
