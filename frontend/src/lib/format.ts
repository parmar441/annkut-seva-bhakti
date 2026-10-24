/** Display helpers. Times show in the app timezone (from /api/meta/enums), not the browser's. */

let TZ = 'America/New_York';

export function setTimezone(tz: string) {
  TZ = tz;
}
export function getTimezone() {
  return TZ;
}

const cache = new Map<string, Intl.DateTimeFormat>();
function fmt(key: string, opts: Intl.DateTimeFormatOptions, tz = TZ) {
  const k = `${tz}|${key}`;
  let f = cache.get(k);
  if (!f) {
    f = new Intl.DateTimeFormat('en-US', { timeZone: tz, ...opts });
    cache.set(k, f);
  }
  return f;
}

/** "9:12 AM" */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return fmt('time', { hour: 'numeric', minute: '2-digit' }).format(new Date(iso));
}

/** "9:12a" (compact, for dense admin cards) */
export function formatTimeCompact(iso: string | null | undefined): string {
  if (!iso) return '—';
  return formatTime(iso).replace(' AM', 'a').replace(' PM', 'p');
}

/** "Thu, Oct 23" for an instant. */
export function formatDay(iso: string): string {
  return fmt('day', { weekday: 'short', month: 'short', day: 'numeric' }).format(new Date(iso));
}

/** "Oct 22, 10:02 PM" */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  return fmt('dt', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(iso));
}

/** Calendar date ("YYYY-MM-DD") formatting, independent of timezone. */
function dateOnly(d: string): Date {
  return new Date(`${d}T12:00:00Z`);
}
export function formatCalendarDate(d: string, withWeekday = true): string {
  return fmt(
    withWeekday ? 'cal-wd' : 'cal',
    withWeekday ? { weekday: 'short', month: 'short', day: 'numeric' } : { month: 'short', day: 'numeric' },
    'UTC',
  ).format(dateOnly(d));
}

/** "Oct 1 – Oct 23" */
export function formatRange(from: string | null | undefined, to: string | null | undefined): string {
  if (from && to) return from === to ? formatCalendarDate(from, false) : `${formatCalendarDate(from, false)} – ${formatCalendarDate(to, false)}`;
  if (from) return `Since ${formatCalendarDate(from, false)}`;
  if (to) return `Until ${formatCalendarDate(to, false)}`;
  return 'All time';
}

export function monDay(d: string): { mon: string; day: string } {
  const date = dateOnly(d);
  return {
    mon: fmt('mon', { month: 'short' }, 'UTC').format(date).toUpperCase(),
    day: fmt('dnum', { day: 'numeric' }, 'UTC').format(date),
  };
}

/** Local {date: "YYYY-MM-DD", time: "HH:mm"} in the app timezone, for date/time inputs. */
export function localParts(iso: string): { date: string; time: string } {
  const parts = fmt('parts', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return { date: `${get('year')}-${get('month')}-${get('day')}`, time: `${get('hour')}:${get('minute')}` };
}

export function todayLocal(now: Date = new Date()): string {
  return localParts(now.toISOString()).date;
}

export function monthStartLocal(now: Date = new Date()): string {
  return `${todayLocal(now).slice(0, 8)}01`;
}

/** Local wall-clock "YYYY-MM-DDTHH:mm" sent to the API, which interprets it in the app timezone. */
export function toLocalInput(date: string, time: string): string {
  return `${date}T${time}`;
}

/** Live timer "2:18:45". */
export function formatElapsed(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

/** Same "h m" rule as the server: floor to minutes. */
export function formatHm(seconds: number): string {
  const mins = Math.floor(Math.max(0, seconds) / 60);
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
}

/** Same decimal rule as the server: half-up to 2 places. */
export function formatDecimalHours(seconds: number): string {
  // Integer math avoids float error: hundredths of an hour, rounded half-up.
  const hundredths = Math.floor((Math.max(0, Math.floor(seconds)) * 100 + 1800) / 3600);
  return `${Number((hundredths / 100).toFixed(2))} h`;
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

export function monthName(d: string): string {
  return fmt('mname', { month: 'long' }, 'UTC').format(dateOnly(d));
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat('en-US').format(n);
}
