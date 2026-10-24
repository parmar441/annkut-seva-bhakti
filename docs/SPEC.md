# Annkut Seva Bhakti: product specification

## 1. Overview

A complete, production-ready web application to manage volunteers, track their seva (volunteer service) hours and generate administrative reports. It must be fully functional, with a working frontend, backend, database, authentication, authorization and reporting. Do not build a static or mock-only UI.

**Stack:** React + TypeScript · Python FastAPI · MongoDB · JWT auth with secure password hashing · responsive, mobile-friendly UI · RESTful APIs with validation, error handling and documentation.

## 2. Roles and permissions

There are two roles: `admin` and `user` (General User). Role-based access control is enforced on the backend.

**Admin can:**

- View all registered users.
- View, search and filter seva records.
- Generate reports by date range, Mandal Name and Mandal Type.
- View an individual volunteer's seva history.
- View daily, weekly, monthly and custom-range totals.
- View total seva hours by volunteer, by Mandal and by Mandal Type.
- Export filtered reports to CSV and Excel (.xlsx).
- Identify missing clock-out entries and overlapping seva sessions.
- Activate or deactivate user accounts.
- Correct seva records. Each correction writes an audit log entry with the original value, updated value, timestamp and admin.
- View dashboard statistics: total volunteers, total sessions, total seva hours and active volunteers.

Admin accounts are created only through a protected setup process or administrative provisioning. Users can never register themselves as Admin.

## 3. Registration and login

### Registration fields (all required)

Full Name · Username · Password · Confirm Password · Mandal Name (dropdown) · Mandal Type (dropdown)

**Mandal Name values (exact):** Edison, Jersey City, Clifton, Parsippany, Passaic, Pennsylvania

**Mandal Type values (exact):** Kishori, Yuvti, Sahid, Sahradayi

Define these once, as shared enums, and use them everywhere: backend, frontend, filters and exports.

### Validation (frontend and backend)

- All required fields must be filled in.
- Usernames must be unique. Treat them as case-insensitive: store a normalized lowercase copy with a unique index.
- Password and Confirm Password must match.
- Passwords need at least 12 characters, with uppercase and lowercase letters, a number and a special character.
- Reject commonly compromised passwords, using a bundled common-password list (and optionally the HIBP k-anonymity API).
- Never store plaintext passwords. Hash them with Argon2id.
- Show clear, friendly validation messages per field. See the Register screen.

After registering, the user can log in with their username and password.

### Session security

- Secure login and logout, with private pages and APIs protected.
- Short-lived access token (about 15 minutes) and a rotating refresh token (about 7 days), both in `Secure`, `HttpOnly`, `SameSite=Lax` (or Strict) cookies. Store refresh tokens hashed server-side so they can be revoked. Protect cookie-authenticated mutating requests against CSRF (double-submit token or SameSite plus Origin checks).
- Rate-limit the login and registration endpoints (e.g. `slowapi`).
- Users who are deactivated cannot log in or refresh their tokens.
- Users cannot reach admin functionality by modifying requests or URLs. Every admin route depends on `require_admin`.

## 4. General User dashboard

- A welcome message with the volunteer's name, and their Mandal Name and Mandal Type.
- Today's seva hours, this month's total and the lifetime total.
- A one-tap Start Seva / End Seva control showing the live elapsed time while a session is active.
- Recent seva sessions.
- A date-range selector for reviewing historical hours.
- It must be easy to use on a phone.

## 5. Seva time tracking

### Clock in

- Record a server-side timestamp (UTC).
- Create a session linked to the user, with a **snapshot** of the user's Mandal Name and Mandal Type at that moment.
- Reject the request if the user already has an open session. Return 409 and also enforce this with a partial unique index on `{user_id, status: "active"}`.
- Return the start time and status.

### Clock out

- Record a server-side timestamp. Match it to the user's active session.
- Compute the duration from the timestamps. Reject the request if there is no active session, or if the duration would be zero or negative.
- Mark the session `completed`.

### Timezone

Store all timestamps in UTC. Display them in the configured timezone, which defaults to America/New_York (`APP_TIMEZONE`). Use `zoneinfo` on the backend for day and week boundaries, including DST changes.

### Manual entry and editing (General User)

- Users can add a past session, or correct their own session's start and end date and time.
- A reason is required when editing a completed session.
- Reject invalid ranges: end must be after start, no future end times, and a configurable maximum length (e.g. 16 hours) or else the session is flagged.
- Prevent unintended overlaps with the user's other sessions. Either reject with a clear message, or allow it with an explicit confirmation, in which case the session is flagged `overlap`.
- Flag unusual or incomplete records for admin review: missing clock-out older than N hours, very long sessions, overlaps, and manual entries.
- Every change writes an audit record.
- Sessions that cross midnight are split across calendar dates in daily reports.

### History table

Columns: Date · Clock-in Date/Time · Clock-out Date/Time · Total Duration · Session Status · Actions (View, Edit). It can be filtered by date range and opens a session detail view. On a phone, show it as stacked cards (see `design/History.dc.html`) and as a real table on wider screens.

Users can never view or modify another volunteer's records. Return 404 for sessions they don't own.

## 6. Hours calculation

- Duration = clock-out − clock-in, computed on the server from stored BSON dates. Never accept a duration from the client.
- Supported totals: day, week, month, custom range, lifetime, by volunteer, by Mandal and by Mandal Type.
- Show both formats: `2 hours 30 minutes` and `2.5 hours`. Store and aggregate in whole seconds. For decimal hours, round to 2 places (half-up) only for display. For "h m" format, floor to minutes. Apply the same rule everywhere.
- No double counting. For a range [A, B), each session contributes `max(0, min(end, B) − max(start, A))`.
- Daily totals split sessions at local midnight in the configured timezone.
- Active sessions count toward "today" and live totals up to now. Exclude them from finalized reports unless the "Active" status filter is selected.
- Week starts on Sunday by default (configurable).

## 7. Admin dashboard and reporting

### Summary cards

Total registered volunteers · Total completed sessions · Total seva hours · Hours today · Hours this month · Volunteers with active sessions · Sessions requiring review.

### Filters (all can be combined)

- **Date:** specific date, start and end date, Today, This week, This month, custom range.
- **Mandal Name:** All Mandals, or one of the six.
- **Mandal Type:** All Types, or one of the four.
- **Volunteer name** (partial, case-insensitive) and **username**.
- **Session status:** Active, Completed, Flagged.

### Report table

Volunteer Name · Username · Mandal Name · Mandal Type · Seva Date · Clock-in Time · Clock-out Time · Session Duration · Session Status. Paginated, with page size options of 20, 50 and 100. The header shows the total hours and session count for the full filtered set, not just the current page.

> **Note:** the original spec was cut off after "Provide pagination,". The rest of this section fills in sensible defaults. Check with the product owner.

- Sortable columns (default: Seva Date descending).
- **CSV and Excel export** of the full filtered result, not just the current page, plus a summary sheet or rows with totals by Mandal and Mandal Type. Stream large exports. For Excel, use `openpyxl` or `xlsxwriter`.
- Summary views: hours by volunteer, by Mandal and by Mandal Type for the selected filters.
- **Review queue:** missing clock-outs, overlaps, long sessions and manual entries. The admin can correct a session (with a required reason) or mark it reviewed.
- **Volunteer detail:** profile, lifetime hours and paginated history.
- **Activate or deactivate** user accounts. Deactivating a user also revokes their refresh tokens.

## 8. Data model (MongoDB)

**users**

```
_id, full_name, username, username_lower (unique), password_hash,
mandal_name (enum), mandal_type (enum), role ("user"|"admin"),
is_active (bool), created_at, updated_at, last_login_at
```

**seva_sessions**

```
_id, user_id (ObjectId, indexed), mandal_name, mandal_type (snapshot at clock-in),
clock_in (date, UTC), clock_out (date|null), duration_seconds (int|null, server-computed),
status ("active"|"completed"), flags: ["missing_clock_out"|"overlap"|"long_session"|"manual_entry"],
needs_review (bool), reviewed_by, reviewed_at, source ("clock"|"manual"),
created_at, updated_at
Indexes: {user_id:1, clock_in:-1}; {clock_in:1}; {mandal_name:1, mandal_type:1, clock_in:1};
partial unique {user_id:1} where status=="active"; {needs_review:1}
```

**audit_logs**

```
_id, entity ("seva_session"|"user"), entity_id, action ("create"|"update"|"correct"|"activate"|"deactivate"),
actor_id, actor_role, before (object), after (object), reason, created_at
```

**refresh_tokens**

```
_id, user_id, token_hash, expires_at (TTL index), revoked_at, created_at, user_agent, ip
```

## 9. API (suggested)

```
POST   /api/auth/register
POST   /api/auth/login
POST   /api/auth/refresh
POST   /api/auth/logout
GET    /api/auth/me
GET    /api/meta/enums                      # mandal names/types

GET    /api/me/summary                      # today, month, lifetime, active session
GET    /api/me/sessions?from&to&status&page
GET    /api/me/sessions/{id}
POST   /api/me/sessions/clock-in
POST   /api/me/sessions/clock-out
POST   /api/me/sessions                     # manual entry
PATCH  /api/me/sessions/{id}                # requires reason when completed
GET    /api/me/sessions/{id}/audit
GET    /api/me/totals?from&to&group=day|week|month

# admin (require_admin)
GET    /api/admin/stats
GET    /api/admin/users?q&mandal_name&mandal_type&is_active&page
GET    /api/admin/users/{id}
PATCH  /api/admin/users/{id}/status         # {is_active}
GET    /api/admin/users/{id}/sessions
GET    /api/admin/sessions?from&to&date&preset&mandal_name&mandal_type&name&username&status&sort&page&page_size
GET    /api/admin/sessions/export?format=csv|xlsx&<same filters>
GET    /api/admin/totals?group_by=volunteer|mandal_name|mandal_type|day&<filters>
GET    /api/admin/review?type=missing_clock_out|overlap|long_session
PATCH  /api/admin/sessions/{id}             # correction, reason required, audit logged
POST   /api/admin/sessions/{id}/mark-reviewed
GET    /api/admin/audit?entity_id&page
```

Errors: `{ "error": { "code": "SESSION_ALREADY_ACTIVE", "message": "...", "fields": {...} } }`, with 400/401/403/404/409/422/429 used appropriately.

## 10. Quality

- Unit tests (pytest) for duration math, midnight split, range clipping, DST transitions, overlap detection and password policy. API tests for RBAC (a user calling an admin route gets 403; user A reading user B's session gets 404).
- Frontend: form validation, loading, empty and error states, and accessible labels. Touch targets at least 44 px.
- `.env.example`, docker-compose, a seed script with sample data, and a README with setup steps.
