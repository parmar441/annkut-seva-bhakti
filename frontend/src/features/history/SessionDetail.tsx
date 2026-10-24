import { Link, useParams } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { useMe, useMySession, useMySessionAudit } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import type { Session } from '../../api/types';
import { sessionNote } from '../../components/SessionCard';
import { ErrorState, Spinner, StatusPill } from '../../components/ui';
import { formatCalendarDate, formatDateTime } from '../../lib/format';
import { ChangeHistory } from './ChangeHistory';

const FLAG_TEXT: Record<string, string> = {
  missing_clock_out: 'Missing clock-out',
  overlap: 'Overlaps another session',
  long_session: 'Unusually long',
  manual_entry: 'Added or edited by hand',
};

export function SessionFacts({ session: s }: { session: Session }) {
  return (
    <dl className="card dl" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 14 }}>
      <div>
        <dt>Clock in</dt>
        <dd>{formatDateTime(s.clock_in)}</dd>
      </div>
      <div>
        <dt>Clock out</dt>
        <dd>{s.clock_out ? formatDateTime(s.clock_out) : s.status === 'active' ? 'In progress' : '—'}</dd>
      </div>
      <div>
        <dt>Duration</dt>
        <dd>{s.duration ? s.duration.long : '—'}</dd>
      </div>
      <div>
        <dt>Decimal hours</dt>
        <dd>{s.duration ? s.duration.decimal_text : '—'}</dd>
      </div>
      <div>
        <dt>Mandal</dt>
        <dd>
          {s.mandal_name} · {s.mandal_type}
        </dd>
      </div>
      <div>
        <dt>Recorded by</dt>
        <dd>{s.source === 'clock' ? 'Clock in / out' : 'Manual entry'}</dd>
      </div>
      {s.flags.length > 0 && (
        <div style={{ gridColumn: '1 / -1' }}>
          <dt>Flags</dt>
          <dd>
            {s.flags.map((f) => FLAG_TEXT[f]).join(' · ')}
            {s.needs_review ? ' (awaiting review)' : ' (reviewed)'}
          </dd>
        </div>
      )}
    </dl>
  );
}

export default function SessionDetail() {
  const { id } = useParams();
  const session = useMySession(id);
  const audit = useMySessionAudit(id);
  const me = useMe();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <header className="subpage-header">
        <Link to="/history" className="icon-btn" aria-label="Back to history">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <div>
          <h1>Session details</h1>
          {session.data && <p>{formatCalendarDate(session.data.local_date)}</p>}
        </div>
        <div className="spacer" />
        {session.data && <StatusPill status={session.data.display_status} />}
      </header>
      <div className="page" style={{ paddingTop: 8 }}>
        {session.isPending ? (
          <Spinner />
        ) : session.isError ? (
          <ErrorState message={errorMessage(session.error)} />
        ) : (
          <>
            <SessionFacts session={session.data} />
            {sessionNote(session.data) && <p className="note">{sessionNote(session.data)}</p>}
            <ChangeHistory entries={audit.data} meId={me.data?.id} loading={audit.isPending} />
            <Link to={`/history/${session.data.id}/edit`} className="btn btn-primary btn-block">
              {session.data.status === 'active' ? 'Add clock-out' : 'Edit session'}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
