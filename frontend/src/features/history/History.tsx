import { Link, useSearchParams } from 'react-router-dom';
import { Plus } from 'lucide-react';
import { useMySessions } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { SessionCard, durationText, sessionNote } from '../../components/SessionCard';
import { ChipGroup, EmptyState, ErrorState, Pagination, Skeleton, StatusPill, type Option } from '../../components/ui';
import { TextField } from '../../components/Field';
import { formatCalendarDate, formatRange, formatTime } from '../../lib/format';

type Preset = 'today' | 'week' | 'month' | 'custom';
const PRESETS: Option<Preset>[] = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: 'This week' },
  { id: 'month', label: 'This month' },
  { id: 'custom', label: 'Custom' },
];

export default function History() {
  const [params, setParams] = useSearchParams();
  const from = params.get('from') ?? '';
  const to = params.get('to') ?? '';
  const preset: Preset = (params.get('preset') as Preset) || (from || to ? 'custom' : 'month');
  const page = Number(params.get('page') ?? '1') || 1;
  const invalid = !!from && !!to && from > to;

  const query = useMySessions(
    preset === 'custom' ? { from: invalid ? undefined : from, to: invalid ? undefined : to, page } : { preset, page },
  );
  const data = query.data;

  const update = (next: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (!('page' in next)) p.delete('page');
    setParams(p, { replace: true });
  };

  const shownFrom = preset === 'custom' ? from : (data?.range.from ?? '');
  const shownTo = preset === 'custom' ? to : (data?.range.to ?? '');

  return (
    <div className="page tight">
      <header className="page-header">
        <h1 className="page-title">Seva history</h1>
        <Link to="/history/new" className="btn btn-secondary btn-sm" style={{ border: '1px solid var(--border)' }}>
          <Plus size={18} strokeWidth={2} aria-hidden="true" />
          Add entry
        </Link>
      </header>

      <ChipGroup
        label="Date range"
        options={PRESETS}
        value={preset}
        onChange={(v) => (v === 'custom' ? update({ preset: 'custom', from: shownFrom, to: shownTo }) : update({ preset: v, from: null, to: null }))}
      />

      <div className="grid-2">
        <TextField small label="From" type="date" value={shownFrom} max={shownTo || undefined} onChange={(e) => update({ preset: 'custom', from: e.target.value, to: shownTo })} />
        <TextField
          small
          label="To"
          type="date"
          value={shownTo}
          min={shownFrom || undefined}
          onChange={(e) => update({ preset: 'custom', from: shownFrom, to: e.target.value })}
          error={invalid ? 'End date must be on or after the start date.' : undefined}
        />
      </div>

      <section aria-label="Range total" className="range-total" aria-live="polite">
        <div className="stack-sm" style={{ gap: 2 }}>
          <p className="kicker">
            {formatRange(data?.range.from, data?.range.to)} · {data ? `${data.summary.sessions} session${data.summary.sessions === 1 ? '' : 's'}` : '…'}
          </p>
          <p className="big">{data ? data.summary.duration.long : '—'}</p>
        </div>
        <p className="dec">{data?.summary.duration.decimal_text ?? ''}</p>
      </section>

      <section aria-label="Sessions" className="stack" style={{ gap: 10 }}>
        {query.isPending ? (
          <Skeleton count={3} height={150} />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} onRetry={() => query.refetch()} />
        ) : !data || data.items.length === 0 ? (
          <EmptyState>
            {data && data.range.from ? 'No seva sessions in this date range.' : 'No seva sessions yet. Tap Start Seva to begin.'}
          </EmptyState>
        ) : (
          <>
            <div className="stack only-mobile" style={{ gap: 10 }}>
              {data.items.map((s) => (
                <SessionCard key={s.id} session={s} />
              ))}
            </div>
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Seva sessions</caption>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">Clock-in</th>
                    <th scope="col">Clock-out</th>
                    <th scope="col">Total duration</th>
                    <th scope="col">Status</th>
                    <th scope="col">Note</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((s) => (
                    <tr key={s.id}>
                      <td>{formatCalendarDate(s.local_date)}</td>
                      <td>{formatTime(s.clock_in)}</td>
                      <td>{s.clock_out ? `${s.crosses_midnight ? `${formatCalendarDate(s.day_split.at(-1)!.date, false)}, ` : ''}${formatTime(s.clock_out)}` : '—'}</td>
                      <td className="num">{durationText(s, s.elapsed_seconds)}</td>
                      <td>
                        <StatusPill status={s.display_status} />
                      </td>
                      <td style={{ whiteSpace: 'normal', maxWidth: 260, color: 'var(--muted)', fontSize: 12 }}>{sessionNote(s)}</td>
                      <td>
                        <div className="actions">
                          <Link className="btn btn-ghost btn-sm" to={`/history/${s.id}`}>
                            View
                          </Link>
                          <Link className="btn btn-ghost btn-sm" to={`/history/${s.id}/edit`}>
                            {s.flags.includes('missing_clock_out') && !s.clock_out ? 'Add clock-out' : 'Edit'}
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={(p) => update({ page: String(p) })} />
          </>
        )}
      </section>
    </div>
  );
}
