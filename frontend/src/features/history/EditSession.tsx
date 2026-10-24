import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { AlertTriangle, ChevronLeft } from 'lucide-react';
import { previewMine, useMe, useMySession, useMySessionAudit, useSaveSession } from '../../api/hooks';
import { ApiError, errorMessage } from '../../api/client';
import type { AuditEntry, Session } from '../../api/types';
import { TextArea, TextField } from '../../components/Field';
import { Button, ErrorState, Spinner } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { formatCalendarDate, formatDateTime, formatTime, localParts, toLocalInput, todayLocal } from '../../lib/format';
import { usePreview } from '../../lib/usePreview';
import { ChangeHistory } from './ChangeHistory';

interface Values {
  start_date: string;
  start_time: string;
  end_date: string;
  end_time: string;
  reason: string;
}

const STATUS_TEXT = { active: 'Active', completed: 'Completed', flagged: 'Flagged' } as const;

export function OverlapAlert({ overlaps, onConfirm, confirmed }: { overlaps: Session[]; onConfirm?: (v: boolean) => void; confirmed?: boolean }) {
  if (!overlaps.length) return null;
  const list = overlaps
    .map((o) => `${formatCalendarDate(o.local_date, false)}, ${formatTime(o.clock_in)} – ${o.clock_out ? formatTime(o.clock_out) : 'now'}`)
    .join('; ');
  return (
    <div className="stack" style={{ gap: 4 }}>
      <div role="alert" className="alert">
        <AlertTriangle size={20} strokeWidth={2} aria-hidden="true" />
        <p>
          <strong>Overlaps another session.</strong> {list} overlaps these times. Adjust the times, or this change will be flagged for admin review.
        </p>
      </div>
      {onConfirm && (
        <label className="check-row">
          <input type="checkbox" checked={!!confirmed} onChange={(e) => onConfirm(e.target.checked)} />
          Save anyway and flag it for admin review
        </label>
      )}
    </div>
  );
}

function initialValues(s: Session | undefined): Values {
  if (!s) return { start_date: todayLocal(), start_time: '', end_date: todayLocal(), end_time: '', reason: '' };
  const a = localParts(s.clock_in);
  const b = s.clock_out ? localParts(s.clock_out) : { date: a.date, time: '' };
  return { start_date: a.date, start_time: a.time, end_date: b.date, end_time: b.time, reason: '' };
}

export default function EditSession() {
  const { id } = useParams();
  const isNew = !id;
  const session = useMySession(id);
  const audit = useMySessionAudit(id);
  if (!isNew && session.isPending) return <Spinner />;
  if (!isNew && session.isError) {
    return (
      <div className="page">
        <ErrorState message={errorMessage(session.error)} />
        <Link to="/history">Back to history</Link>
      </div>
    );
  }
  return <EditForm key={id ?? 'new'} session={session.data} auditEntries={audit.data} auditLoading={audit.isPending && !isNew} />;
}

function EditForm({ session, auditEntries, auditLoading }: { session?: Session; auditEntries?: AuditEntry[]; auditLoading: boolean }) {
  const isNew = !session;
  const isActive = session?.status === 'active';
  const reasonRequired = session?.status === 'completed';
  const navigate = useNavigate();
  const location = useLocation();
  // Return to wherever the user came from (the dashboard's "Add hours manually" or History).
  const back = (location.state as { from?: string } | null)?.from ?? '/history';
  const toast = useToast();
  const me = useMe();
  const save = useSaveSession(session?.id);
  const [confirmOverlap, setConfirmOverlap] = useState(false);
  const [serverOverlaps, setServerOverlaps] = useState<Session[]>([]);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<Values>({ defaultValues: initialValues(session) });
  const v = watch();
  const clockIn = v.start_date && v.start_time ? toLocalInput(v.start_date, v.start_time) : null;
  const clockOut = v.end_date && v.end_time ? toLocalInput(v.end_date, v.end_time) : null;

  const fetcher = useMemo(() => (body: { clock_in: string; clock_out?: string }) => previewMine({ ...body, session_id: session?.id }), [session?.id]);
  const preview = usePreview(fetcher, clockIn, clockOut);
  const overlaps = preview.data?.overlaps ?? serverOverlaps;

  useEffect(() => setConfirmOverlap(false), [clockIn, clockOut]);

  const onSubmit = handleSubmit((values) => {
    let ok = !(overlaps.length && !confirmOverlap);
    const fail = (field: keyof Values, message: string) => {
      ok = false;
      setError(field, { message });
    };
    const needsEnd = !isActive || !!values.end_time;
    if (!values.start_date) fail('start_date', 'Choose a date.');
    if (!values.start_time) fail('start_time', 'Choose a time.');
    if (needsEnd && !values.end_date) fail('end_date', 'Choose a date.');
    if (needsEnd && !values.end_time) fail('end_time', 'Choose a clock-out time.');
    if (reasonRequired && !values.reason.trim()) fail('reason', 'Please give a reason for this change.');
    if (!ok) return;

    save.mutate(
      {
        clock_in: toLocalInput(values.start_date, values.start_time),
        clock_out: needsEnd ? toLocalInput(values.end_date, values.end_time) : undefined,
        reason: values.reason.trim() || undefined,
        confirm_overlap: confirmOverlap,
      },
      {
        onSuccess: (s) => {
          toast(isNew ? 'Session added' : `Session saved · ${s.duration?.long ?? 'in progress'}`);
          navigate(back);
        },
        onError: (err) => {
          if (!(err instanceof ApiError)) return;
          if (err.code === 'SESSION_OVERLAP') setServerOverlaps((err.details.overlaps as Session[]) ?? []);
          if (err.fields.clock_in) setError('start_time', { message: err.fields.clock_in });
          if (err.fields.clock_out) setError('end_time', { message: err.fields.clock_out });
          if (err.fields.reason) setError('reason', { message: err.fields.reason });
        },
      },
    );
  });

  const title = isNew ? 'Add session' : isActive ? 'Add clock-out' : 'Edit session';
  const subtitle = session ? `${formatCalendarDate(session.local_date)} · ${STATUS_TEXT[session.display_status]}` : 'Enter seva you have already done';
  const previewErrors = preview.data?.errors ?? {};
  const formError =
    save.error && !(save.error instanceof ApiError && (save.error.code === 'SESSION_OVERLAP' || Object.keys(save.error.fields).length)) ? errorMessage(save.error) : null;

  return (
    <div className="app-subpage" style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <header className="subpage-header">
        <Link to={back} className="icon-btn" aria-label="Back">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
      </header>
      <form className="form compact" style={{ flex: 1, padding: '8px 20px 20px' }} onSubmit={onSubmit} noValidate>
        {formError && (
          <div className="alert danger" role="alert">
            {formError}
          </div>
        )}
        <fieldset className="card">
          <legend>Clock in</legend>
          <div className="grid-2">
            <TextField small label="Date" type="date" max={todayLocal()} error={errors.start_date?.message} {...register('start_date')} />
            <TextField small label="Time" type="time" error={errors.start_time?.message ?? previewErrors.clock_in} {...register('start_time')} />
          </div>
        </fieldset>
        <fieldset className="card">
          <legend>Clock out{isActive ? ' (leave empty to keep the session running)' : ''}</legend>
          <div className="grid-2">
            <TextField small label="Date" type="date" max={todayLocal()} error={errors.end_date?.message} {...register('end_date')} />
            <TextField small label="Time" type="time" error={errors.end_time?.message ?? previewErrors.clock_out} {...register('end_time')} />
          </div>
        </fieldset>

        <div className="card duration-panel" aria-live="polite">
          <div className="stack-sm" style={{ gap: 2 }}>
            <p className="muted" style={{ fontSize: 12, fontWeight: 600 }}>
              New duration (calculated by server)
            </p>
            <p className="big">{preview.loading ? 'Calculating…' : (preview.data?.duration?.long ?? '—')}</p>
            {preview.data && preview.data.day_split.length > 1 && (
              <p className="muted" style={{ fontSize: 12 }}>
                Crosses midnight: {preview.data.day_split.map((d) => `${d.hm} on ${formatCalendarDate(d.date, false)}`).join(', ')}
              </p>
            )}
          </div>
          <p className="muted" style={{ fontSize: 14, fontWeight: 700 }}>
            {preview.data?.duration?.decimal_text ?? ''}
          </p>
        </div>

        {preview.data?.warnings.map((w) => (
          <div key={w} className="alert" role="status">
            <AlertTriangle size={20} strokeWidth={2} aria-hidden="true" />
            <p>{w}</p>
          </div>
        ))}

        <OverlapAlert overlaps={overlaps} confirmed={confirmOverlap} onConfirm={setConfirmOverlap} />

        <TextArea
          label={reasonRequired ? 'Reason for change' : 'Note (optional)'}
          required={reasonRequired}
          rows={3}
          placeholder="e.g. Forgot to clock out after kitchen seva"
          error={errors.reason?.message}
          hint={reasonRequired ? 'Required when editing a completed session. Saved to the audit trail.' : 'Helps organizers when they review manual entries.'}
          {...register('reason')}
        />

        {!isNew && <ChangeHistory entries={auditEntries} meId={me.data?.id} loading={auditLoading} />}

        <div className="spacer" />
        <div className="grid-2">
          <Link to={back} className="btn btn-secondary">
            Cancel
          </Link>
          <Button type="submit" loading={save.isPending} disabled={overlaps.length > 0 && !confirmOverlap}>
            {save.isPending ? 'Saving…' : isNew ? 'Add session' : 'Save changes'}
          </Button>
        </div>
        {session?.updated_at && (
          <p className="muted" style={{ fontSize: 12, textAlign: 'center' }}>
            Last updated {formatDateTime(session.updated_at)}
          </p>
        )}
      </form>
    </div>
  );
}
