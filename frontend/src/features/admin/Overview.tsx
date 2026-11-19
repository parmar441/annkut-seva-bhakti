import { Link } from 'react-router-dom';
import { ChevronRight, Flag } from 'lucide-react';
import { useState } from 'react';
import { useAdminStats, useTopVolunteers } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { AdminHeader } from '../../components/Shells';
import { ChipGroup, ErrorState, HoursBar, Skeleton, StatCard, type Option } from '../../components/ui';
import { TopCountPicker, TopVolunteerList, readChoice, saveChoice } from '../../components/TopVolunteers';
import { MANDAL_TYPES } from '../../lib/enums';
import { formatDay, formatNumber } from '../../lib/format';
import { SecurityQuestionPrompt } from '../../components/Shells';

export default function Overview() {
  const stats = useAdminStats();
  const s = stats.data;
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
            <StatCard large label="Completed sessions" value={formatNumber(s!.completed_sessions)} sub="Clocked in and out" />
            <StatCard large label="Total seva hours" value={s!.total_hours.decimal_text} sub={s!.total_hours.hm} />
            <StatCard large label="Hours today" value={s!.hours_today.decimal_text} sub={`${s!.volunteers_today} volunteer${s!.volunteers_today === 1 ? '' : 's'}`} />
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
            <section aria-label="Hours by Mandal" className="card pad-lg stack">
              <h2 className="section-title sm">Hours by Mandal</h2>
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

            <section aria-label="Hours by Mandal type" className="card pad-lg stack">
              <h2 className="section-title sm">Hours by Mandal Type</h2>
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

          <TopVolunteersCard />
        </>
      )}
    </div>
  );
}

const TOP_COUNTS = ['3', '5', '10'] as const;
type TopCount = (typeof TOP_COUNTS)[number];
// 'all' = one list per type; 'overall' = one ranking across every type.
const TYPE_OPTIONS: Option<string>[] = [
  { id: 'all', label: 'By type' },
  { id: 'overall', label: 'All categories' },
  ...MANDAL_TYPES.map((t) => ({ id: t, label: t })),
];

function TopVolunteersCard() {
  const [count, setCount] = useState<TopCount>(() => readChoice('overview.topCount', TOP_COUNTS, '3'));
  const [type, setType] = useState<string>(() => readChoice('overview.topType', TYPE_OPTIONS.map((o) => o.id), 'all'));
  const overall = type === 'overall';
  const top = useTopVolunteers({
    limit: Number(count),
    overall: overall || undefined,
    mandal_type: type === 'all' || overall ? undefined : type,
  });
  const reportLink = `/admin/reports${type === 'all' || overall ? '' : `?mandal_type=${encodeURIComponent(type)}`}`;

  return (
    <section aria-label="Top volunteers" className="card pad-lg stack">
      <div className="section-head">
        <h2 className="section-title sm">Top volunteers</h2>
        <Link to={reportLink} className="link-sm">
          Full ranking
        </Link>
      </div>
      <div className="top-controls">
        <TopCountPicker
          label="How many volunteers to show"
          options={TOP_COUNTS}
          value={count}
          onChange={(v) => {
            setCount(v);
            saveChoice('overview.topCount', v);
          }}
        />
        <div className="chips-scroll">
          <ChipGroup
            label="Mandal type"
            options={TYPE_OPTIONS}
            value={type}
            onChange={(v) => {
              setType(v);
              saveChoice('overview.topType', v);
            }}
          />
        </div>
      </div>
      {top.isPending ? (
        <Skeleton count={3} height={44} />
      ) : top.isError ? (
        <ErrorState message={errorMessage(top.error)} onRetry={() => top.refetch()} />
      ) : (
        <div className={`top-types${type === 'all' ? '' : ' single'}`} aria-busy={top.isFetching || undefined}>
          {top.data.items.map((t) => (
            <div key={t.name} className="top-type">
              <h3>
                {t.name}
                <span className="type-total tabular">{t.decimal_text}</span>
              </h3>
              {t.volunteers.length ? (
                <TopVolunteerList
                  label={`Top volunteers, ${t.name}`}
                  items={t.volunteers.map((v) => ({
                    id: v.id,
                    name: v.full_name,
                    hours: v.decimal_text,
                    sessions: v.sessions,
                    detail: overall ? (v.mandal_type ?? undefined) : undefined,
                  }))}
                />
              ) : (
                <p className="note">No seva hours yet.</p>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
