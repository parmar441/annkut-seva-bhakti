# Annkut Seva Bhakti

A mobile-first web app for tracking volunteer seva hours. Volunteers clock in and out from their phones. Organizers (admins) see live totals, run filtered reports, export CSV or Excel files, and review or correct flagged sessions. Every correction is recorded in an audit log.

- **Frontend:** React + TypeScript (Vite), React Router, TanStack Query, React Hook Form + Zod: `frontend/`
- **Backend:** FastAPI, Pydantic v2, Motor (MongoDB): `backend/`
- **Shared:** Mandal names and types, plus the common-password list, used by both sides: `shared/`
- **Specs:** `docs/SPEC.md`, `docs/DESIGN.md`, mockups in `design/`

## Quick start with Docker

```bash
cp .env.example .env              # then set JWT_SECRET to a long random string
docker compose up --build -d
docker compose exec backend python -m app.scripts.create_admin \
  --username organizer --full-name "Edison Organizer" --mandal-name Edison --mandal-type Yuvti
# Optional sample data (20 volunteers, about 60 days of sessions):
docker compose exec backend python -m app.scripts.seed
```

Open http://localhost:8080. nginx serves the app and proxies `/api` to the backend, so cookies stay first-party.

## Deploy to Render

`render.yaml` defines one Docker web service. The root `Dockerfile` builds the React app and FastAPI serves it next to the API, so the site and API share one origin. Separate `*.onrender.com` services would count as different sites, and browsers would then refuse to send the login cookies.

1. **MongoDB Atlas:** under Network Access, allow `0.0.0.0/0`, because Render's outbound IPs change unless you buy static IPs. The database password still protects the cluster.
2. **Render:** go to Dashboard → **New → Blueprint**, pick this repository, and enter `MONGO_URL` (your Atlas `mongodb+srv://…` string) when prompted. `JWT_SECRET` is generated for you, and `RENDER_EXTERNAL_URL` is picked up automatically for the origin check.
3. Create the first admin from your own machine, with `backend/.env` pointing at the same Atlas database (the free plan has no Shell):
   `python -m app.scripts.create_admin --username organizer --full-name "Edison Organizer" --mandal-name Edison --mandal-type Yuvti`
   You can skip this if an admin already exists in the database.

Sizing: the Blueprint uses Render's **free** plan (512 MB, 0.1 CPU) with 1 process and 2 parallel password checks. The free plan sleeps after 15 minutes idle, so the first visit after that takes about a minute. Each sign-in costs about 0.4 s of its CPU, so a rush of 500 sign-ins takes a few minutes to clear. All of them succeed, but people wait. Before a big event, switch to a paid plan (Standard, 2 GB) and set `WEB_CONCURRENCY=2` and `HASH_CONCURRENCY=8`. On the free plan there is no Shell, so create admins locally with the CLI pointed at the same Atlas database.

## Local development

Requirements: Python 3.12+, Node 18+, and MongoDB 6+ (or the in-memory demo mode below).

```bash
# Backend
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp ../.env.example .env            # set MONGO_URL and JWT_SECRET
.venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                        # http://localhost:5173, proxies /api to :8000
```

**No MongoDB installed?** Start the backend with `MONGO_URL=mongomock:// COOKIE_SECURE=false`. It runs an in-memory database preloaded with sample data, which is lost on restart. Sign in as `organizer` (admin) or `anjali.p` (volunteer) with the password `Seva-Demo-2026!`. This mode is for development only and refuses to start when `ENVIRONMENT=production`.

### Creating admins

Nobody can register as an admin. Admins are created only from the command line:

```bash
python -m app.scripts.create_admin --username <name> --full-name "<Full Name>" \
  --mandal-name Edison --mandal-type Yuvti
# Promote an existing volunteer instead:
python -m app.scripts.create_admin --username <name> --full-name x --promote
```

The script prompts for the password, or reads it from `ADMIN_PASSWORD`. It never takes the password as an argument.

### Tests

```bash
cd backend && .venv/bin/python -m pytest      # 131 tests
cd frontend && npm test && npm run typecheck   # 13 tests + tsc
```

Backend tests use an in-memory Mongo mock (`mongomock-motor`). They cover duration math, range clipping, midnight splits, DST changes, overlap detection, the password policy, auth (refresh rotation and reuse detection, CSRF, deactivation), and RBAC. Every `/api/admin/*` route is checked to return 403 for a volunteer and 401 when signed out. A test also confirms that user A gets 404 for user B's sessions.

## How it works

### Security

- Passwords are hashed with Argon2id. The policy requires at least 6 characters (`password_min_length` in `shared/enums.json`), upper and lower case, a number and a symbol, and rejects passwords on the bundled common list (including tricks like `P@ssw0rd123!`). HaveIBeenPwned checks are optional (`HIBP_ENABLED`).
- The access token is a 15-minute JWT. The refresh token lasts 7 days, rotates on every use and is stored server-side as a SHA-256 hash. Reusing an old refresh token revokes all of that user's sessions. Both are `HttpOnly`, `SameSite=Lax` cookies, and `Secure` in production.
- CSRF protection uses a double-submit token (`csrf_token` cookie plus `X-CSRF-Token` header) and an Origin check on every mutating `/api` request.
- Login and registration are rate-limited (slowapi).
- Every admin route depends on `require_admin`, which reads the role from the database rather than from the token. Volunteer queries are always scoped to the signed-in user; anything else returns 404.
- Deactivating a user revokes their refresh tokens, and their next request is rejected.
- The app won't start with `ENVIRONMENT=production` if `JWT_SECRET` is weak, `COOKIE_SECURE=false`, or the in-memory database is configured.

### Time and hours

- Clock-in and clock-out use the server clock. Durations are always computed on the server from stored UTC timestamps (`backend/app/reports/timecalc.py`).
- Times are shown in `APP_TIMEZONE` (default America/New_York). Manual entries are sent as local wall-clock times and converted on the server. Times that don't exist because of a spring-forward DST change are rejected.
- Range totals clip each session to `[start, end)`. Daily totals split sessions at local midnight, so a session from 8:15 PM to 12:45 AM counts as 3h 45m on the first day and 45m on the next.
- Hours are stored in whole seconds. Displays use "h m" (floored to the minute) and decimal hours (rounded half-up to 2 places) everywhere.
- Volunteer totals include an in-progress session up to now. Admin reports exclude active sessions from totals unless the **Active** status filter is selected.

### Flags and review

| Flag | When |
|---|---|
| `missing_clock_out` | A session is still open after `MISSING_CLOCK_OUT_HOURS` (default 12). A background sweep runs every 10 minutes and before review queries. |
| `long_session` | Longer than `LONG_SESSION_HOURS` (default 16). Sessions over `MAX_SESSION_HOURS` (24) are rejected. |
| `overlap` | Overlaps another of the volunteer's sessions. Saving returns 409 until the volunteer confirms, and confirmed overlaps are flagged. |
| `manual_entry` | Added or edited by a volunteer. |

A reason is required when a volunteer edits a completed session, and for every admin correction. Each change writes an `audit_logs` record with the before and after values, the reason, the actor and a timestamp.

## Forgotten passwords

Volunteers reset their own password with a **security question**. No admin is involved.

- At registration everyone picks a question from a fixed list (`security_questions` in `shared/enums.json`) and types an answer. Accounts created before this feature see a "Set up your security question" prompt after signing in. Anyone can change theirs later from **Change security question** on the dashboard (or the admin account menu); this asks for their current password.
- **Sign in → Forgot password?**: enter your username, answer your question, and choose a new password.
- Answers match ignoring capitals, spaces and punctuation, and are stored as Argon2 hashes, like passwords. Unknown usernames, and accounts without a question, still get a believable question, so the page can't be used to discover accounts. After `RECOVERY_FAILURES_PER_USER` (5) wrong answers, recovery for that username pauses for `RECOVERY_FAILURE_WINDOW_MINUTES` (15). A reset signs the volunteer out on every device and is recorded in the audit log.
- **Fallback:** if someone forgets their answer or username too, an organizer can find them by name under **Volunteers**, open their profile and tap **Issue reset code** (single use, expires in 30 minutes). The volunteer enters it under **I already have a code**. Organizers can't issue a code for their own account.

## Capacity and resilience

- **Sign-in bursts:** 500 simultaneous logins from one IP all succeed. This was load-tested against Atlas and is covered by `tests/test_resilience.py`. Per-IP limits are sized for a whole event sharing one Wi-Fi address. Password guessing is blocked per account instead: 10 failures per username+IP, or 50 per username, within 15 minutes.
- **Password hashing:** Argon2 runs in worker threads, at most `HASH_CONCURRENCY` at a time per process (about 64 MiB each). A burst of sign-ins can't block other requests or exhaust memory.
- **Failures:** if the database is unreachable, requests get a 503 "try again" (`MONGO_TIMEOUT_MS`), and startup keeps retrying instead of crashing. Unexpected errors return a JSON 500 with a `request_id` that matches the server log. In the browser, an error boundary shows a reload screen instead of a blank page.
- **Health checks:** `GET /api/health` (process up) and `GET /api/health/ready` (database reachable; Docker uses this one).
- **Scaling:** run more worker processes with `WEB_CONCURRENCY` (Docker defaults to 4). Rate-limit counters are kept per process unless `RATE_LIMIT_STORAGE_URI` points at Redis. Lockout counts are always shared, because they're stored in MongoDB.
- **Atlas free tier (M0):** capped at about 100 database operations per second. A sign-in uses 4, so 500 sign-ins take about 25 seconds there. All of them still succeed. A paid tier (M10 or higher) removes the cap.
- **Behind a proxy:** run uvicorn with `--proxy-headers --forwarded-allow-ips <proxy IP>` so limits apply per visitor. The Docker image and the Vite dev proxy already do this.

## Configuration

All settings are environment variables. `.env.example` documents each one. The most important are `MONGO_URL`, `JWT_SECRET`, `COOKIE_SECURE`, `CORS_ORIGINS`, `APP_TIMEZONE` and `WEEK_START`.

## API

FastAPI serves interactive docs at `/docs` on the backend (http://localhost:8000/docs in development). Errors share one shape:

```json
{ "error": { "code": "SESSION_ALREADY_ACTIVE", "message": "…", "fields": { "clock_out": "…" } } }
```

## Open questions for the product owner

- The original spec was cut off at "Provide pagination,". Sorting, export and summary behaviour follow the defaults in `docs/SPEC.md` §7.
- Edits by volunteers go to the review queue (flag `manual_entry`), so they show as "Flagged" until an admin reviews them.
- The admin report's "All" status lists active sessions but leaves them out of the hour totals.
