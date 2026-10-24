import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, Copy, KeyRound } from 'lucide-react';
import { useCancelReset, useIssueResetCode, useResetRequests, useUserReset } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import type { User } from '../../api/types';
import { Button } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { formatDateTime, formatTime } from '../../lib/format';

/** Volunteer detail: issue a one-time reset code after checking the person in front of you. */
export function PasswordResetCard({ user, isSelf }: { user: User; isSelf: boolean }) {
  const reset = useUserReset(user.id);
  const issue = useIssueResetCode();
  const cancel = useCancelReset();
  const toast = useToast();
  const [shown, setShown] = useState<{ code: string; expires: string | null } | null>(null);

  const doIssue = () =>
    issue.mutate(user.id, {
      onSuccess: (r) => {
        setShown({ code: r.code, expires: r.reset.expires_at });
        reset.refetch();
      },
      onError: (e) => toast(errorMessage(e), 'error'),
    });
  const doCancel = () =>
    cancel.mutate(user.id, {
      onSuccess: () => {
        setShown(null);
        reset.refetch();
        toast('Reset cancelled');
      },
      onError: (e) => toast(errorMessage(e), 'error'),
    });
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shown!.code);
      toast('Code copied');
    } catch {
      toast('Copy failed. Read the code out instead.', 'error');
    }
  };

  const r = reset.data;
  return (
    <section aria-label="Password reset" className="card stack">
      <div className="row" style={{ gap: 8 }}>
        <KeyRound size={18} strokeWidth={2} aria-hidden="true" />
        <h2 className="section-title sm">Password reset</h2>
      </div>

      {shown ? (
        <div className="stack" style={{ gap: 10 }}>
          <div className="range-total" role="status" aria-live="polite">
            <div className="stack-sm" style={{ gap: 2 }}>
              <p className="kicker">One-time code for @{user.username}</p>
              <p className="big tabular" style={{ letterSpacing: '0.12em' }}>
                {shown.code}
              </p>
            </div>
            <button type="button" className="icon-btn" aria-label="Copy code" onClick={copy}>
              <Copy size={20} aria-hidden="true" />
            </button>
          </div>
          <p className="muted" style={{ fontSize: 13 }}>
            Give this code to {user.full_name} in person or by a call you trust. It works once and expires at{' '}
            <strong>{formatTime(shown.expires)}</strong>. It won't be shown again; issue a new one if it's lost. They enter it at{' '}
            <strong>Sign in → Forgot password → I have a code</strong>.
          </p>
        </div>
      ) : r ? (
        <p className="note" style={{ fontSize: 13 }}>
          {r.status === 'requested'
            ? `${user.full_name} asked for a reset ${formatDateTime(r.requested_at)}. Check it's really them, then issue a code.`
            : `A code was issued ${formatDateTime(r.issued_at)}${r.issued_by ? ` by ${r.issued_by}` : ''} and expires ${formatTime(r.expires_at)}.`}
        </p>
      ) : (
        <p className="muted" style={{ fontSize: 13 }}>
          If {user.full_name} forgot their password, check it's them and issue a one-time code.
        </p>
      )}

      {!user.is_active ? (
        <p className="muted" style={{ fontSize: 13 }}>Activate the account before resetting its password.</p>
      ) : isSelf ? (
        <p className="muted" style={{ fontSize: 13 }}>Ask another organizer to reset your own password.</p>
      ) : (
        <div className="grid-2">
          <Button size="sm" loading={issue.isPending} onClick={doIssue}>
            {r?.status === 'issued' || shown ? 'Issue new code' : 'Issue reset code'}
          </Button>
          <Button size="sm" variant="secondary" disabled={!r && !shown} loading={cancel.isPending} onClick={doCancel}>
            Cancel reset
          </Button>
        </div>
      )}
    </section>
  );
}

/** Volunteers page / overview: who is waiting for a reset code. */
export function ResetRequestsBanner() {
  const requests = useResetRequests();
  const items = requests.data?.items ?? [];
  if (!items.length) return null;
  return (
    <section aria-label="Password reset requests" className="banner" style={{ flexDirection: 'column', alignItems: 'stretch', gap: 8 }}>
      <div className="row" style={{ gap: 10 }}>
        <KeyRound size={20} strokeWidth={2} aria-hidden="true" />
        <strong style={{ fontSize: 15 }}>
          {items.length} password reset request{items.length === 1 ? '' : 's'}
        </strong>
      </div>
      {items.map((r) => (
        <Link
          key={r.id}
          to={`/admin/volunteers/${r.user_id}`}
          className="row"
          style={{ justifyContent: 'space-between', color: 'inherit', textDecoration: 'none', minHeight: 44, borderTop: '1px solid rgba(120,53,15,0.15)' }}
        >
          <span style={{ fontSize: 13 }}>
            <strong>{r.volunteer?.full_name}</strong> @{r.volunteer?.username} · {formatDateTime(r.requested_at)}
          </span>
          <ChevronRight size={18} aria-hidden="true" />
        </Link>
      ))}
    </section>
  );
}
