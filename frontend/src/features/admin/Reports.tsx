import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowDown, ArrowUp, Download } from 'lucide-react';
import { useAdminReport, useAdminTotals } from '../../api/hooks';
import { downloadFile, errorMessage } from '../../api/client';
import { useToast } from '../../components/Toast';
import type { AdminSession } from '../../api/types';
import { AdminHeader } from '../../components/Shells';
import { SelectField, TextField } from '../../components/Field';
import { ChipGroup, EmptyState, ErrorState, Pagination, Segmented, Skeleton, StatusPill, type Option } from '../../components/ui';
import { MANDAL_NAMES, MANDAL_TYPES } from '../../lib/enums';
import { formatCalendarDate, formatTimeCompact, formatTime } from '../../lib/format';

type Preset = 'today' | 'week' | 'month' | 'date' | 'custom';
const PRESETS: Option<Preset>[] = [
  { id: 'today', label: 'Today' },
  { id: 'week', label: 'This week' },
  { id: 'month', label: 'This month' },
  { id: 'date', label: 'Specific date' },
  { id: 'custom', label: 'Custom' },
];
type Status = 'all' | 'active' | 'completed' | 'flagged';
const STATUSES: Option<Status>[] = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active' },
  { id: 'completed', label: 'Done' },
  { id: 'flagged', label: 'Flagged' },
];
const SORTS = [
  { id: 'date', label: 'Seva date' },
  { id: 'name', label: 'Volunteer name' },
  { id: 'username', label: 'Username' },
  { id: 'mandal_name', label: 'Mandal name' },
  { id: 'mandal_type', label: 'Mandal type' },
  { id: 'duration', label: 'Duration' },
  { id: 'status', label: 'Status' },
] as const;

function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function ReportCard({ r }: { r: AdminSession }) {
  return (
    <article className="card session-card">
      <div className="head">
        <div className="stack-sm" style={{ gap: 2, minWidth: 0 }}>
          <h2>{r.volunteer?.full_name ?? 'Unknown volunteer'}</h2>
          <p className="muted" style={{ fontSize: 12 }}>
            @{r.volunteer?.username} · {r.mandal_name} · {r.mandal_type}
          </p>
        </div>
        <StatusPill status={r.display_status} />
      </div>
      <dl className="dl four">
        <div>
          <dt>Date</dt>
          <dd>{formatCalendarDate(r.local_date, false)}</dd>
        </div>
        <div>
          <dt>In</dt>
          <dd>{formatTimeCompact(r.clock_in)}</dd>
        </div>
        <div>
          <dt>Out</dt>
          <dd>{formatTimeCompact(r.clock_out)}</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>{r.duration?.hm ?? '—'}</dd>
        </div>
      </dl>
    </article>
  );
}

export default function Reports() {
  const [params, setParams] = useSearchParams();
  const get = (k: string, d = '') => params.get(k) ?? d;
  const preset = get('preset', 'month') as Preset;
  const status = get('status', 'all') as Status;
  const sort = get('sort', 'date');
  const order = get('order', 'desc') as 'asc' | 'desc';
  const page = Number(get('page', '1')) || 1;
  const pageSize = Number(get('page_size', '20')) || 20;
  const [search, setSearch] = useState(get('q'));
  const q = useDebounced(search);

  const set = (next: Record<string, string | null>, resetPage = true) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (resetPage) p.delete('page');
    setParams(p, { replace: true });
  };

  useEffect(() => {
    if (q !== get('q')) set({ q: q || null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const from = get('from');
  const to = get('to');
  const date = get('date');
  const invalidRange = preset === 'custom' && !!from && !!to && from > to;

  const filters = useMemo(() => {
    const f: Record<string, string | undefined> = {
      mandal_name: get('mandal_name') || undefined,
      mandal_type: get('mandal_type') || undefined,
      q: get('q') || undefined,
      status,
    };
    if (preset === 'date') f.date = date || undefined;
    else if (preset === 'custom') {
      if (!invalidRange) {
        f.from = from || undefined;
        f.to = to || undefined;
      }
    } else f.preset = preset;
    return f;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const report = useAdminReport({ ...filters, sort, order, page, page_size: pageSize });
  const byMandal = useAdminTotals({ ...filters, group_by: 'mandal_name' });
  const byType = useAdminTotals({ ...filters, group_by: 'mandal_type' });
  const data = report.data;

  const toast = useToast();
  const [exporting, setExporting] = useState<'csv' | 'xlsx' | null>(null);
  const runExport = async (format: 'csv' | 'xlsx') => {
    setExporting(format);
    try {
      await downloadFile('/api/admin/sessions/export', { ...filters, sort, order, format }, `seva-report.${format}`);
    } catch (e) {
      toast(errorMessage(e), 'error');
    } finally {
      setExporting(null);
    }
  };

  const sortBy = (field: string) => set({ sort: field, order: sort === field && order === 'desc' ? 'asc' : 'desc' });
  const sortIcon = (field: string) => (sort === field ? order === 'asc' ? <ArrowUp size={12} aria-hidden="true" /> : <ArrowDown size={12} aria-hidden="true" /> : null);
  const ariaSort = (field: string) => (sort === field ? (order === 'asc' ? 'ascending' : 'descending') : 'none');

  return (
    <div className="page tight">
      <AdminHeader title="Reports" />

      <section aria-label="Filters" className="card pad-lg stack" style={{ borderRadius: 18, gap: 14 }}>
        <ChipGroup label="Date preset" options={PRESETS} value={preset} onChange={(v) => set({ preset: v })} />
        <div className="grid-2">
          {preset === 'date' ? (
            <TextField small label="Date" type="date" value={date} onChange={(e) => set({ date: e.target.value })} className="span-2" />
          ) : (
            <>
              <TextField
                small
                label="Start date"
                type="date"
                value={preset === 'custom' ? from : (data?.range.from ?? '')}
                onChange={(e) => set({ preset: 'custom', from: e.target.value, to: preset === 'custom' ? to : (data?.range.to ?? '') })}
              />
              <TextField
                small
                label="End date"
                type="date"
                value={preset === 'custom' ? to : (data?.range.to ?? '')}
                error={invalidRange ? 'End date must be on or after the start date.' : undefined}
                onChange={(e) => set({ preset: 'custom', to: e.target.value, from: preset === 'custom' ? from : (data?.range.from ?? '') })}
              />
            </>
          )}
          <SelectField small label="Mandal name" options={MANDAL_NAMES} placeholder="All Mandals" value={get('mandal_name')} onChange={(e) => set({ mandal_name: e.target.value })} />
          <SelectField small label="Mandal type" options={MANDAL_TYPES} placeholder="All Types" value={get('mandal_type')} onChange={(e) => set({ mandal_type: e.target.value })} />
        </div>
        <TextField small label="Volunteer name or username" type="search" placeholder="Search volunteers" value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="field small">
          <span id="status-label" className="label">
            Session status
          </span>
          <Segmented labelledBy="status-label" options={STATUSES} value={status} onChange={(v) => set({ status: v })} />
        </div>
      </section>

      <section aria-label="Report totals" className="dark-card">
        <p className="kicker">{data?.label ?? 'Loading…'}</p>
        <div className="row" style={{ alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <p className="big">{data ? data.totals.duration.hm : '—'}</p>
          <p style={{ fontSize: 14, color: 'var(--on-dark-muted)' }}>
            {data ? `${data.totals.duration.decimal_text} · ${data.totals.sessions.toLocaleString('en-US')} session${data.totals.sessions === 1 ? '' : 's'}` : ''}
          </p>
        </div>
        {data && !data.include_active_in_totals && (
          <p style={{ fontSize: 12, color: 'var(--on-dark-muted)' }}>Hours are clipped to the date range and exclude sessions still in progress.</p>
        )}
        <div className="grid-2">
          {(['csv', 'xlsx'] as const).map((format) => (
            <button
              key={format}
              type="button"
              className="btn btn-inverse btn-sm"
              disabled={exporting !== null}
              aria-busy={exporting === format || undefined}
              onClick={() => runExport(format)}
            >
              <Download size={18} strokeWidth={2} aria-hidden="true" />
              {exporting === format ? 'Preparing…' : format === 'csv' ? 'CSV' : 'Excel'}
            </button>
          ))}
        </div>
      </section>

      <details className="card">
        <summary style={{ fontWeight: 800, fontSize: 15, cursor: 'pointer', minHeight: 32 }}>Totals by Mandal and Mandal Type</summary>
        <div className="split-desktop stack" style={{ marginTop: 12 }}>
          {[byMandal, byType].map((g, i) => (
            <table key={i} className="table" style={{ display: 'table' }}>
              <thead>
                <tr>
                  <th scope="col">{i === 0 ? 'Mandal' : 'Type'}</th>
                  <th scope="col">Sessions</th>
                  <th scope="col">Hours</th>
                </tr>
              </thead>
              <tbody>
                {g.data?.items.map((it) => (
                  <tr key={it.key}>
                    <td>{it.label}</td>
                    <td className="num">{it.sessions ?? 0}</td>
                    <td className="num">
                      {it.hm} ({it.decimal_text})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
        </div>
      </details>

      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <SelectField
          small
          label="Sort by"
          options={SORTS.map((s) => s.label)}
          value={SORTS.find((s) => s.id === sort)?.label}
          onChange={(e) => set({ sort: SORTS.find((s) => s.label === e.target.value)?.id ?? 'date' })}
        />
        <SelectField small label="Per page" options={['20', '50', '100']} value={String(pageSize)} onChange={(e) => set({ page_size: e.target.value })} />
      </div>

      <section aria-label="Results" className="stack" style={{ gap: 10 }}>
        {report.isPending ? (
          <Skeleton count={4} height={110} />
        ) : report.isError ? (
          <ErrorState message={errorMessage(report.error)} onRetry={() => report.refetch()} />
        ) : !data?.items.length ? (
          <EmptyState>No sessions match these filters.</EmptyState>
        ) : (
          <>
            <div className="stack only-mobile" style={{ gap: 10 }}>
              {data.items.map((r) => (
                <ReportCard key={r.id} r={r} />
              ))}
            </div>
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Seva report</caption>
                <thead>
                  <tr>
                    {[
                      ['name', 'Volunteer name'],
                      ['username', 'Username'],
                      ['mandal_name', 'Mandal name'],
                      ['mandal_type', 'Mandal type'],
                      ['date', 'Seva date'],
                    ].map(([f, l]) => (
                      <th key={f} scope="col" aria-sort={ariaSort(f)}>
                        <button type="button" onClick={() => sortBy(f)}>
                          {l}
                          {sortIcon(f)}
                        </button>
                      </th>
                    ))}
                    <th scope="col">Clock-in</th>
                    <th scope="col">Clock-out</th>
                    <th scope="col" aria-sort={ariaSort('duration')}>
                      <button type="button" onClick={() => sortBy('duration')}>
                        Duration{sortIcon('duration')}
                      </button>
                    </th>
                    <th scope="col" aria-sort={ariaSort('status')}>
                      <button type="button" onClick={() => sortBy('status')}>
                        Status{sortIcon('status')}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((r) => (
                    <tr key={r.id}>
                      <td>
                        {r.volunteer ? <Link to={`/admin/volunteers/${r.volunteer.id}`}>{r.volunteer.full_name}</Link> : '—'}
                      </td>
                      <td>@{r.volunteer?.username}</td>
                      <td>{r.mandal_name}</td>
                      <td>{r.mandal_type}</td>
                      <td>{formatCalendarDate(r.local_date)}</td>
                      <td>{formatTime(r.clock_in)}</td>
                      <td>{formatTime(r.clock_out)}</td>
                      <td className="num">{r.duration ? `${r.duration.hm} (${r.duration.decimal_text})` : '—'}</td>
                      <td>
                        <StatusPill status={r.display_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pages={data.pages} total={data.total} pageSize={data.page_size} onPage={(p) => set({ page: String(p) }, false)} />
          </>
        )}
      </section>
    </div>
  );
}
