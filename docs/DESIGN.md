# Annkut Seva Bhakti: design handoff

Mobile-first. The mockups are drawn at 390 px wide (phone). On tablet and desktop, center the content in a column up to about 480 px wide for the volunteer app. The admin console can widen to a sidebar plus content layout, with the report as a real table at 768 px and above.

## Tokens (`frontend/src/styles/tokens.css`)

```css
:root {
  --font: 'Plus Jakarta Sans', system-ui, sans-serif;   /* Google Fonts 400/500/600/700/800 */

  --bg: #F6F4EF;          /* page background */
  --surface: #FFFFFF;     /* cards, inputs, nav */
  --surface-muted: #F0ECE5; /* segmented controls, dividers, bar tracks */
  --ink: #1C1917;         /* primary text, dark cards, selected chips */
  --muted: #57534E;       /* secondary text (passes 4.5:1 on white and bg) */
  --placeholder: #78716C;
  --border: #E7E2DA;      /* card borders */
  --border-input: #D6D0C6;

  --accent: #B4410F;      /* saffron: primary buttons, active nav, links */
  --accent-hover: #8A300A;
  --accent-soft: #FCEBDD; /* highlight panels, avatars */

  --success: #166534;  --success-bg: #DCFCE7;   /* Completed */
  --info: #1E40AF;     --info-bg: #DBEAFE;      /* Active */
  --warning: #92400E;  --warning-bg: #FEF3C7;   /* Flagged, review */
  --danger: #B91C1C;   --danger-bg: #FEE2E2;    /* errors */

  --radius-sm: 12px;  --radius-md: 14px;  --radius-lg: 16px;  --radius-xl: 22px;  --radius-pill: 999px;
  --space-page-x: 20px;  /* 24px on auth screens */
}
```

**Type scale:** page title 24/800 (letter-spacing -0.02em) · section title 15–17/800 · body 14–16 · label 12–14/600 · micro label 11/600 uppercase · timer 44/800 tabular-nums.

**Sizes:** inputs 44–52 px tall · primary buttons 54 px · nav items at least 44 px · status pill 12/700 with 4×10 padding.

**Icons:** inline 24 px stroke icons, 1.9 stroke width (home, clock, logout, bar-chart, filter, flag, users, download, eye, alert). Lucide icons are a close match: `Home`, `Clock`, `LogOut`, `BarChart3`, `Filter`, `Flag`, `Users`, `Download`, `Eye`, `AlertTriangle`. No emoji.

## Shared components

- `Button`: primary (accent fill), secondary (white with border), inverse (white on dark card). Uses real `<button>`, or a router `<Link>` for navigation.
- `TextField`, `SelectField`, `DateField`, `TimeField`, `TextArea`: visible label above the field, error state with a red border, an icon and a message (`aria-invalid` and `aria-describedby`).
- `PasswordStrength`: 4-segment bar plus a checklist (12+ characters, upper and lower case, number, special character, not a common password).
- `StatusPill`: Active (info), Completed (success), Flagged (warning).
- `StatCard`: label, big value, sub-line (e.g. "24h 30m" and "24.5 h").
- `ChipGroup`: date presets, single select, `aria-pressed`.
- `Segmented`: status filter and review tabs.
- `SessionCard`: date, status, a 3-column grid (In / Out / Duration), an optional note, and View and Edit actions.
- `BottomNav`: volunteer (Home, History, Sign out) and admin (Overview, Reports, Review, Volunteers).
- `Switch`: `role="switch"` `aria-checked`, green when on and grey when off.
- `HoursBar`: horizontal bar for hours by Mandal.

## Screens (`design/` files)

| File | Screen | Key content |
|---|---|---|
| `Main.dc.html` | Sign in | Lamp-style logo, username, password with show toggle, Sign in, Create volunteer account, "Admin accounts are set up by organizers only." |
| `Register.dc.html` | Create account | Full name, username, Mandal name and type side by side, password with strength checklist, confirm with mismatch error, Create account |
| `Dashboard.dc.html` | Volunteer home | Name with Mandal and type chips. Dark seva card toggles between **Not on seva** (Start Seva · Clock in) and **On seva now** (live timer, start time, End Seva · Clock out). Today / Month / Lifetime stat cards, date-range lookup, recent sessions |
| `History.dc.html` | Seva history | Preset chips, From/To dates, range total panel (accent-soft), session cards, crosses-midnight note, missing clock-out flag with an "Add clock-out" action |
| `EditSession.dc.html` | Edit / add session | Clock-in and clock-out date and time fieldsets, server-calculated new duration, overlap warning (`role="alert"`), required reason, change-history timeline, Cancel / Save |
| `AdminOverview.dc.html` | Admin overview | 6 stat cards, "N sessions need review" banner, hours by Mandal bars, hours by Mandal Type grid |
| `AdminReports.dc.html` | Reports | Filter panel (presets, dates, Mandal, type, search, status segmented control), dark totals card with CSV and Excel export, result cards with all report columns, pagination |
| `AdminReview.dc.html` | Review & corrections | Tabs for missing clock-out and overlaps, flagged list with Correct buttons, correction panel (original vs updated, new time, reason, Save), recent audit log |
| `AdminUsers.dc.html` | Volunteers | Search, Mandal and type filters, volunteer cards with an activate/deactivate switch, lifetime hours, View history |

Sample names, times and the bracketed admin figures in the mockups are placeholders. Replace them with live API data.

## Behaviour notes

- The seva card timer ticks every second on the client from the server's `clock_in`. The value shown is cosmetic; the server's number is the one that counts.
- Start and End require one tap with no confirmation dialog. Show a brief toast ("Seva started at 9:12 AM"). Disable the button while the request is in flight to prevent double taps.
- Every editing screen shows the duration returned by the server (preview endpoint or on save), never a client-trusted value.
- Empty states: "No seva sessions yet. Tap Start Seva to begin."
