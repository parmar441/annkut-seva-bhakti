import type { AuditEntry } from '../api/types';
import { formatCalendarDate, formatDateTime, formatTime, localParts } from './format';

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null;
}

function timeChange(label: string, before: string | null, after: string | null): string | null {
  if (before === after) return null;
  const sameDay = before && after && localParts(before).date === localParts(after).date;
  const fmt = (v: string | null) => (v ? (sameDay ? formatTime(v) : formatDateTime(v)) : '—');
  if (!before) return `${label} set to ${fmt(after)}`;
  return `${label} ${fmt(before)} → ${fmt(after)}`;
}

/** One-line summary of what changed, e.g. "Clock-out 9:15 PM → 9:45 PM". */
export function describeChange(e: AuditEntry): string {
  const b = e.before ?? {};
  const a = e.after ?? {};
  if (e.entity === 'user') {
    if (e.action === 'activate') return 'Account activated';
    if (e.action === 'deactivate') return 'Account deactivated';
    if (e.action === 'create') return 'Account created';
    if (e.action === 'reset_issued') return 'Password reset code issued';
    if (e.action === 'password_reset') return 'Password changed with reset code';
    return 'Account updated';
  }
  if (e.action === 'create') {
    return e.reason === 'Clock in' ? 'Session created by clock-in' : `Session added manually (${formatTime(str(a.clock_in))} – ${formatTime(str(a.clock_out))})`;
  }
  if (e.action === 'review') return 'Marked as reviewed';
  if (e.reason === 'Clock out' && e.action === 'update') return `Clocked out at ${formatTime(str(a.clock_out))}`;
  const parts = [timeChange('Clock-in', str(b.clock_in), str(a.clock_in)), timeChange('Clock-out', str(b.clock_out), str(a.clock_out))].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'Session updated';
}

export function describeActor(e: AuditEntry, meId?: string): string {
  const server = e.reason === 'Clock in' || e.reason === 'Clock out';
  if (server) return `Server time · ${formatDateTime(e.created_at)}`;
  const who = e.actor_id && e.actor_id === meId ? 'By you' : e.actor_role === 'admin' ? `Admin: ${e.actor_username}` : e.actor_username ? `By ${e.actor_username}` : 'System';
  return `${who} · ${formatDateTime(e.created_at)}`;
}

export function auditSubject(e: AuditEntry): string {
  const name = e.owner_name ?? 'Volunteer';
  if (e.entity === 'user') return name;
  const when = str(e.after?.clock_in) ?? str(e.before?.clock_in);
  return when ? `${name} · ${formatCalendarDate(localParts(when).date, false)} session` : name;
}

/** Reason shown in quotes, hidden for system-generated reasons. */
export function userReason(e: AuditEntry): string | null {
  if (!e.reason || ['Clock in', 'Clock out', 'Manual entry', 'Marked reviewed', 'Self-registration', 'Password reset code issued', 'Password reset with organizer code'].includes(e.reason)) return null;
  return e.reason;
}
