# Deployment Guide

## Topology
One Linux VPS with persistent storage runs the official Switch deployment and one Zasky service instance. Discord is connected by Switch's bridge. Zasky connects to Switch through the documented private or authenticated endpoint. Do not expose Zasky's health endpoints or SQLite file publicly.

## Deployment rules
1. Confirm `OPERATOR_INTAKE.md` has passed for host, Switch, credentials, cost cap and deployment authority.
2. Confirm the target is isolated staging/test unless production authority is explicitly recorded.
3. Pin images/dependencies and record versions/digests.
4. Configure firewall for SSH and only the ports required by the currently deployed Switch documentation.
5. Use non-root containers, restrictive volumes, read-only root filesystem where compatible, and restart policies.
6. Attach SQLite and backup directories to persistent volumes; do not use ephemeral container storage.
7. Run migration, start one Zasky replica, verify health, Switch connection and private-room echo.
8. Run security tests and a database restore drill.
9. Update preview/staging after each verified checkpoint; record exact URL/host scope and commit in the handoff.
10. Production deployment occurs only after explicit production authorization and final release gate.

## Rollback
- Stop Zasky writer before restoring or replacing its DB.
- Back up current DB and record commit/version.
- Roll back container image to last verified commit.
- For schema downgrade, follow tested Alembic downgrade only if data-safe; otherwise restore a verified backup.
- Reset Switch cursor only with verified protocol procedure; do not blindly replay old events.
- Re-run health, room round trip, query and owner authorization tests.
- Record rollback reason and resulting data state.

## Release authority
A permission to deploy staging is not production authority. If no exact production authority appears in `OPERATOR_INTAKE.md`, final status must be `verified-staging-awaiting-authorized-release`.
