# Annkut Seva Bhakti — instructions for Claude Code

You are building **Annkut Seva Bhakti**, a production-ready, mobile-first web app for tracking volunteer seva (service) hours.

Read these files before writing any code:

1. `docs/SPEC.md`: the full product requirements. This is the source of truth for behaviour, validation, security and reporting.
2. `docs/DESIGN.md`: design tokens, components and a description of every screen.
3. `design/*.dc.html`: the approved screen mockups (HTML with inline styles). Match their layout, copy, spacing and colors. They use a small templating runtime (`{{hole}}`, `<sc-for>`, `<sc-if>`, `<x-dc>`) that is **not** part of the app. Treat them as visual reference and port them to React + TypeScript components. Each file's `<script data-dc-script>` block holds the sample data and the interaction states shown.

## Stack (required)

- Frontend: React + TypeScript (Vite), React Router, mobile-first responsive CSS. Suggested: TanStack Query for data fetching, React Hook Form + Zod for forms.
- Backend: Python + FastAPI, Pydantic v2 models, Motor (async MongoDB driver).
- Database: MongoDB. Store timestamps as BSON dates in UTC.
- Auth: JWT access tokens (short-lived) plus rotating refresh tokens, both in secure HttpOnly cookies. Passwords hashed with Argon2id (`argon2-cffi`).
- API: REST, with OpenAPI docs from FastAPI and consistent error responses.

## Suggested repo layout

```
backend/   app/{main.py, config.py, db.py, auth/, users/, sessions/, reports/, admin/, audit/}, tests/
frontend/  src/{api/, components/, features/{auth,dashboard,history,admin}/, routes/, styles/tokens.css}
docker-compose.yml   (mongo + backend + frontend)
```

## Non-negotiables

- Enforce role-based access control on the **backend** for every admin endpoint. Hiding UI is not enough.
- There is no way to self-register as Admin. Create admins with a CLI/setup command, e.g. `python -m app.scripts.create_admin`.
- All clock-in and clock-out times come from the **server clock**. Never trust a duration sent by the client; compute it from timestamps.
- Users can only ever read or modify their own sessions.
- Every edit to a session (by a user or an admin) writes an audit record: original value, new value, reason, who made the change, and when.
- Display times in America/New_York by default (configurable). Split sessions that cross midnight across calendar days in daily totals, and clip sessions to the selected range in range totals.
- Write tests for the duration, midnight-split, range-clipping, overlap-detection and RBAC logic.

## Build order

1. Backend skeleton, config, Mongo connection and indexes.
2. Auth (register, login, refresh, logout, me), rate limiting, admin-creation CLI.
3. Seva sessions: clock in/out, manual entry, edit with reason, overlap and flag rules, audit log.
4. Aggregation service for totals (day/week/month/range/lifetime, by volunteer/Mandal/type).
5. Admin endpoints: users, reports with filters, pagination, CSV/XLSX export, review queue, corrections, activate/deactivate.
6. Frontend screens in the order of the files in `design/`.
7. Tests, seed script, README with run instructions.
