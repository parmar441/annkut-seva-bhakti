import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { previewAdmin, useAuditLog, useCorrectSession, useMarkReviewed, useReviewQueue } from '../../api/hooks';
import { ApiError, errorMessage } from '../../api/client';
import type { AdminSession, Session, SessionFlag } from '../../api/types';
import { AdminHeader } from '../../components/Shells';
import { TextArea, TextField } from '../../components/Field';
import { Button, EmptyState, ErrorState, Pagination, Segmented, Skeleton, type Option } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { auditSubject, describeActor, describeChange, userReason } from '../../lib/audit';
import { formatCalendarDate, formatTime, localParts, toLocalInput, todayLocal } from '../../lib/format';
import { usePreview } from '../../lib/usePreview';
import { OverlapAlert } from '../history/EditSession';

const TAB_LABEL: Record<SessionFlag, string> = {
  missing_clock_out: 'Missing clock-out',
  overlap: 'Overlaps',
  long_session: 'Long sessions',
  manual_entry: 'Manual entries',
};
const TABS = Object.keys(TAB_LABEL) as SessionFlag[];

function hoursOpen(s: Session): number {
  return Math.floor((s.elapsed_seconds ?? 0) / 3600);
}

function issueText(s: AdminSession, tab: SessionFlag): string {
  if (tab === 'missing_clock_out') {
    if (s.clock_out) return `Clocked out late: ${formatTime(s.clock_in)} – ${formatTime(s.clock_out)}`;
    return hoursOpen(s) >= 24 ? `Open for ${hoursOpen(s)} hours` : `Clocked in ${formatTime(s.clock_in)}, no clock-out`;
  }
  if (tab === 'overlap') {
    const other = s.overlaps?.[0];
    const mine = `${formatTime(s.clock_in)}–${formatTime(s.clock_out)}`;
    return other ? `${mine} overlaps ${formatTime(other.clock_in)}–${other.clock_out ? formatTime(other.clock_out) : 'now'}` : `${mine} overlaps another session`;
  }
  if (tab === 'long_session') return `${formatTime(s.clock_in)} – ${formatTime(s.clock_out)} · ${s.duration?.hm ?? 'still open'}`;
  return `${s.source === 'manual' ? 'Added' : 'Edited'} by volunteer · ${formatTime(s.clock_in)} – ${formatTime(s.clock_out)}`;
}

function CorrectionPanel({ item, onDone }: { item: AdminSession; onDone: () => void }) {
  const toast = useToast();
  const correct = useCorrectSession();
  const markReviewed = useMarkReviewed();
  const start = localParts(item.clock_in);
  const end = item.clock_out ? localParts(item.clock_out) : { date: start.date, time: '' };
  const [inDate, setInDate] = useState(start.date);
  const [inTime, setInTime] = useState(start.time);
  const [outDate, setOutDate] = useState(end.date);
  const [outTime, setOutTime] = useState(end.time);
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState<string>();
  const [confirm, setConfirm] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => headingRef.current?.focus(), [item.id]);

  const clockIn = inDate && inTime ? toLocalInput(inDate, inTime) : null;
  const clockOut = outDate && outTime ? toLocalInput(outDate, outTime) : null;
  const fetcher = useMemo(() => (body: { clock_in: string; clock_out?: string }) => previewAdmin(item.id, body), [item.id]);
  const preview = usePreview(fetcher, clockIn, clockOut);
  const overlaps = preview.data?.overlaps ?? [];
  useEffect(() => setConfirm(false), [clockIn, clockOut]);

  const errs = { ...preview.data?.errors, ...fieldErrors };
  const save = () => {
    setFieldErrors({});
    if (!reason.trim()) return setReasonError('A reason is required. It is saved to the audit log.');
    setReasonError(undefined);
    if (!clockIn) return setFieldErrors({ clock_in: 'Choose the clock-in date and time.' });
    correct.mutate(
      { id: item.id, clock_in: clockIn, clock_out: clockOut ?? undefined, reason: reason.trim(), confirm_overlap: confirm },
      {
        onSuccess: (s) => {
          toast(`Correction saved · ${s.duration?.long ?? 'still open'}`);
          onDone();
        },
        onError: (e) => {
          if (e instanceof ApiError && Object.keys(e.fields).length) setFieldErrors(e.fields);
          else toast(errorMessage(e), 'error');
        },
      },
    );
  };
  const review = () =>
    markReviewed.mutate(
      { id: item.id, reason: reason.trim() || undefined },
      {
        onSuccess: () => {
          toast('Marked as reviewed');
          onDone();
        },
        onError: (e) => toast(errorMessage(e), 'error'),
      },
    );

  return (
    <section aria-labelledby="correct-heading" className="card pad-lg stack panel-raised" style={{ gap: 14 }}>
      <div className="stack-sm" style={{ gap: 2 }}>
        <h2 id="correct-heading" ref={headingRef} tabIndex={-1} className="section-title">
          Correct: {item.volunteer?.full_name}
        </h2>
        <p className="muted" style={{ fontSize: 12 }}>
          {item.mandal_name} · {item.mandal_type} · {formatCalendarDate(item.local_date)}
          {item.volunteer && (
            <>
              {' · '}
              <Link to={`/admin/volunteers/${item.volunteer.id}`}>History</Link>
            </>
          )}
        </p>
      </div>
      <div className="grid-2">
        <div className="compare">
          <p className="k">ORIGINAL</p>
          <p className="v">
            {formatTime(item.clock_in)} – {item.clock_out ? formatTime(item.clock_out) : '—'}
          </p>
          <p className="s">{item.duration ? item.duration.long : 'No clock-out'}</p>
        </div>
        <div className="compare updated" aria-live="polite">
          <p className="k">UPDATED</p>
          <p className="v">
            {clockIn ? formatTimeFromLocal(inTime) : '—'} – {clockOut ? formatTimeFromLocal(outTime) : '—'}
          </p>
          <p className="s">{preview.loading ? 'Calculating…' : (preview.data?.duration?.long ?? '—')}</p>
        </div>
      </div>
      <div className="grid-2">
        <TextField small label="Clock-in date" type="date" max={todayLocal()} value={inDate} onChange={(e) => setInDate(e.target.value)} />
        <TextField small label="Clock-in time" type="time" value={inTime} onChange={(e) => setInTime(e.target.value)} error={errs.clock_in} />
        <TextField small label="Clock-out date" type="date" max={todayLocal()} value={outDate} onChange={(e) => setOutDate(e.target.value)} />
        <TextField small label="Clock-out time" type="time" value={outTime} onChange={(e) => setOutTime(e.target.value)} error={errs.clock_out} />
      </div>
      {preview.data?.warnings.map((w) => (
        <p key={w} className="alert" role="status">
          {w}
        </p>
      ))}
      <OverlapAlert overlaps={overlaps} confirmed={confirm} onConfirm={setConfirm} />
      <TextArea
        small
        label="Reason (saved to audit log)"
        required
        rows={2}
        placeholder="e.g. Confirmed with Mandal coordinator"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        error={reasonError ?? errs.reason}
      />
      <Button size="md" block loading={correct.isPending} disabled={overlaps.length > 0 && !confirm} onClick={save}>
        {correct.isPending ? 'Saving…' : 'Save correction'}
      </Button>
      <Button variant="secondary" size="md" block loading={markReviewed.isPending} onClick={review}>
        Mark reviewed without changes
      </Button>
    </section>
  );
}

/** "21:30" → "9:30 PM" without timezone conversion (it's already local wall-clock time). */
function formatTimeFromLocal(hhmm: string): string {
  const [h, m] = hhmm.split(':').map(Number);
  const suffix = h >= 12 ? 'PM' : 'AM';
  return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${suffix}`;
}

export default function Review() {
  const [tab, setTab] = useState<SessionFlag>('missing_clock_out');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const queue = useReviewQueue({ type: tab, page });
  const audit = useAuditLog({ entity: 'seva_session', page_size: 6 });
  const items = queue.data?.items ?? [];
  const current = items.find((i) => i.id === selected) ?? null;

  const tabs: Option<SessionFlag>[] = TABS.map((t) => ({ id: t, label: `${TAB_LABEL[t]}${queue.data ? ` (${queue.data.counts[t] ?? 0})` : ''}` }));

  return (
    <div className="page tight">
      <AdminHeader title="Needs review" />
      <Segmented
        tabs
        wrap
        label="Issue type"
        options={tabs}
        value={tab}
        onChange={(t) => {
          setTab(t);
          setPage(1);
          setSelected(null);
        }}
      />

      <div className="split-desktop stack">
        <section aria-label="Flagged sessions" className="stack" style={{ gap: 10 }} role="tabpanel">
          {queue.isPending ? (
            <Skeleton count={3} height={80} />
          ) : queue.isError ? (
            <ErrorState message={errorMessage(queue.error)} onRetry={() => queue.refetch()} />
          ) : items.length === 0 ? (
            <EmptyState>Nothing to review here.</EmptyState>
          ) : (
            <>
              {items.map((i) => (
                <article key={i.id} className={`card review-item${i.id === selected ? ' selected' : ''}`}>
                  <div className="stack-sm" style={{ flex: 1, gap: 3, minWidth: 0 }}>
                    <h3 style={{ fontSize: 15, fontWeight: 800 }}>{i.volunteer?.full_name}</h3>
                    <p className="muted" style={{ fontSize: 12 }}>
                      {i.mandal_name} · {i.mandal_type} · {formatCalendarDate(i.local_date, false)}
                    </p>
                    <p className="issue">{issueText(i, tab)}</p>
                  </div>
                  <Button variant="secondary" size="sm" aria-pressed={i.id === selected} onClick={() => setSelected(i.id === selected ? null : i.id)}>
                    Correct
                  </Button>
                </article>
              ))}
              {queue.data && <Pagination page={queue.data.page} pages={queue.data.pages} total={queue.data.total} pageSize={queue.data.page_size} onPage={setPage} />}
            </>
          )}
        </section>

        <div className="stack" style={{ gap: 16 }}>
          {current && <CorrectionPanel key={current.id} item={current} onDone={() => setSelected(null)} />}

          <section aria-label="Audit log" className="stack" style={{ gap: 10 }}>
            <h2 className="section-title sm">Recent audit log</h2>
            {audit.isPending ? (
              <Skeleton count={2} height={60} />
            ) : !audit.data?.items.length ? (
              <EmptyState>No changes recorded yet.</EmptyState>
            ) : (
              <div className="list">
                {audit.data.items.map((a) => {
                  const reason = userReason(a);
                  return (
                    <div key={a.id} className="list-row" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 3, padding: '12px 14px' }}>
                      <p style={{ fontSize: 13, fontWeight: 700 }}>{auditSubject(a)}</p>
                      <p className="muted" style={{ fontSize: 12 }}>
                        {describeChange(a)}
                        {reason ? ` · “${reason}”` : ''}
                      </p>
                      <p className="muted" style={{ fontSize: 12 }}>
                        {describeActor(a)}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
