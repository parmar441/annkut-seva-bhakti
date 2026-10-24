import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMe, useMyTotals, useSummary } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { RecentRow } from '../../components/SessionCard';
import { DurationStat, EmptyState, ErrorState, Skeleton } from '../../components/ui';
import { TextField } from '../../components/Field';
import { formatRange, initials, monthName, monthStartLocal, todayLocal } from '../../lib/format';
import { SevaCard } from './SevaCard';
import { SecurityQuestionPrompt } from '../../components/Shells';

function RangeLookup() {
  const [from, setFrom] = useState(monthStartLocal());
  const [to, setTo] = useState(todayLocal());
  const invalid = !!from && !!to && from > to;
  const totals = useMyTotals({ from, to }, !!from && !!to && !invalid);
  return (
    <section aria-label="Review hours by date" className="card stack">
      <div className="section-head">
        <h2 className="section-title sm" style={{ fontWeight: 700 }}>
          Hours in a date range
        </h2>
        <Link to={`/history?from=${from}&to=${to}`} className="link-sm">
          Details
        </Link>
      </div>
      <div className="grid-2">
        <TextField small label="From" type="date" value={from} max={to || undefined} onChange={(e) => setFrom(e.target.value)} />
        <TextField
          small
          label="To"
          type="date"
          value={to}
          min={from || undefined}
          onChange={(e) => setTo(e.target.value)}
          error={invalid ? 'End date must be after start.' : undefined}
        />
      </div>
      <p className="muted" style={{ fontSize: 14 }} aria-live="polite">
        {invalid || !from || !to ? (
          'Choose a start and end date.'
        ) : totals.data ? (
          <>
            {formatRange(from, to)} · <strong style={{ color: 'var(--ink)' }}>{totals.data.duration.long}</strong> ({totals.data.duration.decimal_text})
          </>
        ) : totals.isError ? (
          errorMessage(totals.error)
        ) : (
          'Calculating…'
        )}
      </p>
    </section>
  );
}

export default function Dashboard() {
  const me = useMe();
  const summary = useSummary();
  const user = me.data!;
  // Offset between server and device clocks so the live timer matches the server.
  const skewMs = useMemo(() => (summary.data ? Date.parse(summary.data.now) - summary.dataUpdatedAt : 0), [summary.data, summary.dataUpdatedAt]);

  return (
    <div className="page">
      <header className="page-header">
        <div className="stack-sm" style={{ gap: 6 }}>
          <p className="muted" style={{ fontSize: 14 }}>
            Welcome back,
          </p>
          <h1 className="page-title">{user.full_name}</h1>
          <div className="row" style={{ gap: 6 }}>
            <span className="tag">{user.mandal_name}</span>
            <span className="tag">{user.mandal_type}</span>
          </div>
        </div>
        <div className="avatar lg" aria-hidden="true">
          {initials(user.full_name)}
        </div>
      </header>

      <SecurityQuestionPrompt />

      {summary.isPending ? (
        <Skeleton height={190} />
      ) : summary.isError ? (
        <ErrorState message={errorMessage(summary.error)} onRetry={() => summary.refetch()} />
      ) : (
        <SevaCard active={summary.data.active_session} skewMs={skewMs} />
      )}

      <section aria-label="Seva totals" className="grid-3">
        <DurationStat label="Today" duration={summary.data?.totals.today.duration} />
        <DurationStat
          label={summary.data?.totals.month.from ? monthName(summary.data.totals.month.from) : 'This month'}
          duration={summary.data?.totals.month.duration}
        />
        <DurationStat label="Lifetime" duration={summary.data?.totals.lifetime.duration} />
      </section>

      <RangeLookup />

      <section aria-label="Recent sessions" className="stack" style={{ gap: 10 }}>
        <div className="section-head">
          <h2 className="section-title">Recent sessions</h2>
          <Link to="/history" className="link-sm">
            See all
          </Link>
        </div>
        {summary.isPending ? (
          <Skeleton count={3} />
        ) : summary.data && summary.data.recent.length ? (
          <div className="list">
            {summary.data.recent.map((s) => (
              <RecentRow key={s.id} session={s} />
            ))}
          </div>
        ) : summary.data ? (
          <EmptyState>No seva sessions yet. Tap Start Seva to begin.</EmptyState>
        ) : null}
      </section>

      {user.has_security_question && (
        <Link to="/account/security-question" className="link-sm" style={{ alignSelf: 'center', minHeight: 44, display: 'inline-flex', alignItems: 'center' }}>
          Change security question
        </Link>
      )}
    </div>
  );
}
