import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Play, Square } from 'lucide-react';
import { useClockIn, useClockOut } from '../../api/hooks';
import { ApiError, errorMessage } from '../../api/client';
import type { Session } from '../../api/types';
import { useToast } from '../../components/Toast';
import { formatCalendarDate, formatElapsed, formatTime, todayLocal } from '../../lib/format';

/** Ticks every second from the server's clock_in. Cosmetic; the server's duration is what counts. */
function useElapsed(clockIn: string | undefined, skewMs: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!clockIn) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [clockIn]);
  if (!clockIn) return 0;
  return Math.max(0, (now + skewMs - Date.parse(clockIn)) / 1000);
}

export function SevaCard({ active, skewMs }: { active: Session | null; skewMs: number }) {
  const clockIn = useClockIn();
  const clockOut = useClockOut();
  const toast = useToast();
  const elapsed = useElapsed(active?.clock_in, skewMs);
  const busy = clockIn.isPending || clockOut.isPending;

  const start = () =>
    clockIn.mutate(undefined, {
      onSuccess: (s) => toast(`Seva started at ${formatTime(s.clock_in)}`),
      onError: (e) => toast(e instanceof ApiError && e.code === 'SESSION_ALREADY_ACTIVE' ? "You're already on seva." : errorMessage(e), 'error'),
    });
  const end = () =>
    clockOut.mutate(undefined, {
      onSuccess: (s) => toast(`Seva ended · ${s.duration?.long ?? ''}`),
      onError: (e) => toast(errorMessage(e), 'error'),
    });

  const startedToday = active && active.local_date === todayLocal();
  const stale = active?.flags.includes('missing_clock_out');

  return (
    <section aria-label="Current seva session" className="seva-card">
      {active ? (
        <>
          <div className="seva-state on">
            <span className="dot" />
            On seva now
          </div>
          <div className="stack-sm">
            <p className="timer" role="timer" aria-live="off" aria-label={`Elapsed ${formatElapsed(elapsed)}`}>
              {formatElapsed(elapsed)}
            </p>
            <p className="sub">
              Started {startedToday ? 'today' : formatCalendarDate(active.local_date)} at {formatTime(active.clock_in)} · {active.mandal_name}
            </p>
          </div>
          {stale && (
            <p className="warn">
              This session has been open a long time. If you forgot to clock out,{' '}
              <Link to={`/history/${active.id}/edit`} style={{ color: '#fff', fontWeight: 700 }}>
                add the end time
              </Link>
              .
            </p>
          )}
          <button type="button" className="seva-btn end" onClick={end} disabled={busy} aria-busy={busy || undefined}>
            <Square size={20} fill="currentColor" aria-hidden="true" />
            {clockOut.isPending ? 'Ending…' : 'End Seva · Clock out'}
          </button>
        </>
      ) : (
        <>
          <div className="seva-state">
            <span className="dot" />
            Not on seva
          </div>
          <div className="stack-sm">
            <p className="headline">Ready to begin seva?</p>
            <p className="sub">Your start time is recorded by the server.</p>
          </div>
          <button type="button" className="seva-btn start" onClick={start} disabled={busy} aria-busy={busy || undefined}>
            <Play size={18} fill="currentColor" aria-hidden="true" />
            {clockIn.isPending ? 'Starting…' : 'Start Seva · Clock in'}
          </button>
        </>
      )}
    </section>
  );
}
