import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { useAdminUser, useAdminUserSessions, useMe, useSetUserStatus } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { durationText, sessionNote } from '../../components/SessionCard';
import { DurationStat, EmptyState, ErrorState, Pagination, Skeleton, StatCard, StatusPill, Switch } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { TextField } from '../../components/Field';
import { formatCalendarDate, formatDateTime, formatTime, initials } from '../../lib/format';

export default function VolunteerDetail() {
  const { id } = useParams();
  const me = useMe();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const detail = useAdminUser(id);
  const sessions = useAdminUserSessions(id, { page, from, to });
  const setStatus = useSetUserStatus();

  if (detail.isPending) return <div className="page"><Skeleton count={3} /></div>;
  if (detail.isError)
    return (
      <div className="page">
        <ErrorState message={errorMessage(detail.error)} />
        <Link to="/admin/volunteers">Back to volunteers</Link>
      </div>
    );
  const { user, lifetime, this_month, active_session, needs_review } = detail.data;

  return (
    <div className="page tight">
      <header className="row" style={{ gap: 8 }}>
        <Link to="/admin/volunteers" className="icon-btn" aria-label="Back to volunteers">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <span className="admin-badge">ADMIN</span>
      </header>
      <section className="card stack" aria-label="Profile">
        <div className="row" style={{ gap: 12 }}>
          <div className="avatar lg" aria-hidden="true">
            {initials(user.full_name)}
          </div>
          <div className="stack-sm" style={{ flex: 1, gap: 2, minWidth: 0 }}>
            <h1 className="page-title" style={{ fontSize: 20 }}>
              {user.full_name}
            </h1>
            <p className="muted" style={{ fontSize: 13 }}>
              @{user.username} · {user.mandal_name} · {user.mandal_type}
              {user.role === 'admin' ? ' · Admin' : ''}
            </p>
          </div>
          <Switch
            checked={user.is_active}
            label={`${user.is_active ? 'Deactivate' : 'Activate'} ${user.full_name}`}
            disabled={setStatus.isPending || user.id === me.data?.id}
            onChange={(next) =>
              setStatus.mutate({ id: user.id, is_active: next }, { onSuccess: () => toast(next ? 'Account activated' : 'Account deactivated'), onError: (e) => toast(errorMessage(e), 'error') })
            }
          />
        </div>
        <p className="muted" style={{ fontSize: 12 }}>
          {user.is_active ? 'Active account' : 'Deactivated'} · Joined {formatDateTime(user.created_at)} · Last sign-in {formatDateTime(user.last_login_at)}
        </p>
      </section>
      <section aria-label="Totals" className="grid-3">
        <DurationStat label="Lifetime" duration={lifetime.duration} />
        <DurationStat label="This month" duration={this_month.duration} />
        <StatCard label="Needs review" value={needs_review} sub={active_session ? 'On seva now' : `${lifetime.sessions} sessions`} />
      </section>

      <section aria-label="Seva history" className="stack" style={{ gap: 10 }}>
        <h2 className="section-title">Seva history</h2>
        <div className="grid-2">
          <TextField small label="From" type="date" value={from} onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }} />
          <TextField small label="To" type="date" value={to} onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }} />
        </div>
        {sessions.isPending ? (
          <Skeleton count={3} />
        ) : sessions.isError ? (
          <ErrorState message={errorMessage(sessions.error)} />
        ) : sessions.data.items.length === 0 ? (
          <EmptyState>No seva sessions in this range.</EmptyState>
        ) : (
          <>
            <div className="list">
              {sessions.data.items.map((s) => (
                <div key={s.id} className="list-row" style={{ alignItems: 'flex-start' }}>
                  <div className="main">
                    <p className="title">{formatCalendarDate(s.local_date)}</p>
                    <p className="meta">
                      {formatTime(s.clock_in)} – {formatTime(s.clock_out)} · {durationText(s, s.elapsed_seconds)}
                    </p>
                    {sessionNote(s) && <p className="meta">{sessionNote(s)}</p>}
                  </div>
                  <StatusPill status={s.display_status} />
                </div>
              ))}
            </div>
            <Pagination page={sessions.data.page} pages={sessions.data.pages} total={sessions.data.total} pageSize={sessions.data.page_size} onPage={setPage} />
          </>
        )}
        <Link to={`/admin/reports?q=${encodeURIComponent(user.username)}&preset=custom`} className="btn btn-secondary btn-sm">
          Open in reports
        </Link>
      </section>
    </div>
  );
}
