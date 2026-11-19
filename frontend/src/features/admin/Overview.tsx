import { Link } from 'react-router-dom';
import { ChevronRight, Flag } from 'lucide-react';
import { useAdminStats } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { AdminHeader } from '../../components/Shells';
import { ErrorState, HoursBar, Skeleton, StatCard } from '../../components/ui';
import { formatDay, formatNumber, monthName } from '../../lib/format';
import { SecurityQuestionPrompt } from '../../components/Shells';

export default function Overview() {
  const stats = useAdminStats();
  const s = stats.data;
  const month = s?.month.from ? monthName(s.month.from) : 'This month';
  const maxMandal = Math.max(1, ...(s?.by_mandal.map((m) => m.seconds) ?? [1]));
  const maxType = Math.max(1, ...(s?.by_type.map((t) => t.seconds) ?? [1]));
  const totalMandal = s?.by_mandal.reduce((n, m) => n + m.seconds, 0) ?? 0;
  const totalType = s?.by_type.reduce((n, t) => n + t.seconds, 0) ?? 0;
  const review = s?.needs_review;
  const reviewParts = review
    ? [
        review.by_flag.missing_clock_out && `${review.by_flag.missing_clock_out} missing clock-out${review.by_flag.missing_clock_out === 1 ? '' : 's'}`,
        review.by_flag.overlap && `${review.by_flag.overlap} overlap${review.by_flag.overlap === 1 ? '' : 's'}`,
        review.by_flag.long_session && `${review.by_flag.long_session} long`,
        review.by_flag.manual_entry && `${review.by_flag.manual_entry} manual`,
      ].filter(Boolean)
    : [];

  return (
    <div className="page">
      <AdminHeader title="Overview" aside={<p className="muted" style={{ fontSize: 13 }}>{formatDay(new Date().toISOString())}</p>} />

      <SecurityQuestionPrompt />

      {stats.isPending ? (
        <Skeleton count={3} height={90} />
      ) : stats.isError ? (
        <ErrorState message={errorMessage(stats.error)} onRetry={() => stats.refetch()} />
      ) : (
        <>
          <section aria-label="Summary" className="grid-2 cards-desktop-grid">
            <StatCard large label="Registered volunteers" value={formatNumber(s!.total_volunteers)} sub={`${formatNumber(s!.active_accounts)} active accounts`} />
            <StatCard large label="Completed sessions" value={formatNumber(s!.completed_sessions)} sub="All time" />
            <StatCard large label="Total seva hours" value={s!.total_hours.decimal_text} sub={`${s!.total_hours.hm} · all time`} />
            <StatCard large label="Hours today" value={s!.hours_today.decimal_text} sub={`${s!.volunteers_today} volunteer${s!.volunteers_today === 1 ? '' : 's'}`} />
            <StatCard large label="Hours this month" value={s!.hours_this_month.decimal_text} sub={month} />
            <StatCard large label="On seva now" value={formatNumber(s!.on_seva_now)} sub="Active sessions" />
          </section>

          {review && review.total > 0 ? (
            <Link to="/admin/review" className="banner">
              <Flag size={22} strokeWidth={2} aria-hidden="true" />
              <span className="main">
                <strong style={{ fontSize: 15 }}>
                  {review.total} session{review.total === 1 ? '' : 's'} need{review.total === 1 ? 's' : ''} review
                </strong>
                <span style={{ fontSize: 12 }}>{reviewParts.join(' · ')}</span>
              </span>
              <ChevronRight size={20} strokeWidth={2} aria-hidden="true" />
            </Link>
          ) : (
            <p className="note">No sessions need review right now.</p>
          )}

          <div className="split-desktop stack" style={{ gap: 18 }}>
            <section aria-label={`Hours by Mandal, ${month}`} className="card pad-lg stack">
              <h2 className="section-title sm">Hours by Mandal · {month}</h2>
              {/* The server ranks categories by hours, most first. */}
              {s!.by_mandal.map((m, i) => (
                <HoursBar
                  key={m.name}
                  rank={i + 1}
                  name={m.name}
                  value={m.decimal_text}
                  fraction={m.seconds / maxMandal}
                  share={totalMandal ? m.seconds / totalMandal : 0}
                />
              ))}
            </section>

            <section aria-label={`Hours by Mandal type, ${month}`} className="card pad-lg stack">
              <h2 className="section-title sm">Hours by Mandal Type · {month}</h2>
              {s!.by_type.map((t, i) => (
                <HoursBar
                  key={t.name}
                  rank={i + 1}
                  name={t.name}
                  value={t.decimal_text}
                  fraction={t.seconds / maxType}
                  share={totalType ? t.seconds / totalType : 0}
                />
              ))}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
