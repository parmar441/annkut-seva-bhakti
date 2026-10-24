import { Link } from 'react-router-dom';
import type { Session } from '../api/types';
import { formatCalendarDate, formatTime, monDay } from '../lib/format';
import { StatusPill } from './ui';

export function sessionNote(s: Session): string {
  if (s.flags.includes('missing_clock_out') && !s.clock_out) return 'Missing clock-out. Add the end time so these hours count.';
  const notes: string[] = [];
  if (s.crosses_midnight && s.day_split.length > 1) {
    notes.push(
      `Crosses midnight: ${s.day_split.map((d) => `${d.hm} on ${formatCalendarDate(d.date, false)}`).join(', ')}`,
    );
  }
  if (s.flags.includes('overlap')) notes.push('Overlaps another session. Waiting for admin review.');
  if (s.flags.includes('long_session')) notes.push('Unusually long session. Waiting for admin review.');
  if (s.flags.includes('missing_clock_out')) notes.push('Clock-out was added late. Waiting for admin review.');
  if (s.flags.includes('manual_entry') && s.needs_review && notes.length === 0) notes.push('Added or edited by hand. Waiting for admin review.');
  return notes.join(' · ');
}

export function durationText(s: Session, liveSeconds?: number): string {
  if (s.duration) return s.duration.hm;
  if (s.status === 'active' && liveSeconds !== undefined) {
    const mins = Math.floor(liveSeconds / 60);
    return `${Math.floor(mins / 60)}h ${mins % 60}m`;
  }
  return '—';
}

/** History card: date, status, In / Out / Duration grid, note, View and Edit. */
export function SessionCard({ session: s }: { session: Session }) {
  const note = sessionNote(s);
  const missing = !s.clock_out && s.flags.includes('missing_clock_out');
  return (
    <article className="card session-card">
      <div className="head">
        <h2>{formatCalendarDate(s.local_date)}</h2>
        <StatusPill status={s.display_status} />
      </div>
      <dl className="dl">
        <div>
          <dt>Clock in</dt>
          <dd>{formatTime(s.clock_in)}</dd>
        </div>
        <div>
          <dt>Clock out</dt>
          <dd>{formatTime(s.clock_out)}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>{durationText(s, s.elapsed_seconds)}</dd>
        </div>
      </dl>
      {note && <p className="note">{note}</p>}
      <div className="card-actions">
        <Link className="btn" to={`/history/${s.id}`}>
          View details
        </Link>
        <Link className="btn" to={`/history/${s.id}/edit`}>
          {missing ? 'Add clock-out' : 'Edit'}
        </Link>
      </div>
    </article>
  );
}

/** Compact row used on the dashboard's "Recent sessions" list. */
export function RecentRow({ session: s }: { session: Session }) {
  const { mon, day } = monDay(s.local_date);
  let sub = s.duration?.long ?? (s.status === 'active' ? 'In progress' : '—');
  if (!s.clock_out && s.flags.includes('missing_clock_out')) sub = 'Missing clock-out';
  else if (s.crosses_midnight) sub += ' · crosses midnight';
  return (
    <Link to={`/history/${s.id}`} className="list-row">
      <div className="date-badge" aria-hidden="true">
        <span className="mon">{mon}</span>
        <span className="day">{day}</span>
      </div>
      <div className="main">
        <p className="title">
          <span className="sr-only">{formatCalendarDate(s.local_date)}, </span>
          {formatTime(s.clock_in)} – {s.clock_out ? formatTime(s.clock_out) : '—'}
        </p>
        <p className="meta">{sub}</p>
      </div>
      <StatusPill status={s.display_status} />
    </Link>
  );
}
