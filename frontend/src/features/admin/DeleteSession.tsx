import { useId, useState } from 'react';
import { Trash2 } from 'lucide-react';
import { useDeleteSession, useRestoreSession } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { TextArea } from '../../components/Field';
import { Button } from '../../components/ui';
import { useToast } from '../../components/Toast';

/**
 * Delete a session the organizer doesn't accept. Asks for a reason (saved to the audit log),
 * then offers Undo in the confirmation toast. Deleted sessions are archived on the server.
 */
export function DeleteSessionControl({
  sessionId,
  summary,
  onDeleted,
  compact,
}: {
  sessionId: string;
  /** e.g. "Meera Shah · Oct 22, 4:00 – 8:30 PM", shown in the confirmation. */
  summary: string;
  onDeleted?: () => void;
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string>();
  const del = useDeleteSession();
  const restore = useRestoreSession();
  const toast = useToast();
  const headingId = useId();

  const confirm = () => {
    if (!reason.trim()) return setError('A reason is required. It is saved to the audit log.');
    setError(undefined);
    del.mutate(
      { id: sessionId, reason: reason.trim() },
      {
        onSuccess: () => {
          setOpen(false);
          setReason('');
          onDeleted?.();
          toast('Session deleted. Its hours no longer count.', 'info', {
            label: 'Undo',
            // mutateAsync (not mutate callbacks): this panel has usually closed by the time Undo is tapped.
            onClick: () =>
              restore
                .mutateAsync(sessionId)
                .then(() => toast('Session restored'))
                .catch((e) => toast(errorMessage(e), 'error')),
          });
        },
        onError: (e) => toast(errorMessage(e), 'error'),
      },
    );
  };

  if (!open) {
    return (
      <Button variant="danger-outline" size="sm" block={!compact} onClick={() => setOpen(true)}>
        <Trash2 size={16} strokeWidth={2} aria-hidden="true" />
        {compact ? 'Delete' : 'Delete session'}
      </Button>
    );
  }

  return (
    <div role="group" aria-labelledby={headingId} className="stack delete-confirm" style={{ gap: 10 }}>
      <p id={headingId} style={{ fontSize: 14, fontWeight: 700, color: 'var(--danger)' }}>
        Delete these hours?
      </p>
      <p className="muted" style={{ fontSize: 13 }}>
        {summary}. They'll be removed from the volunteer's totals and all reports. You can undo right after.
      </p>
      <TextArea
        small
        label="Reason (saved to audit log)"
        required
        rows={2}
        placeholder="e.g. Clock times not confirmed by Mandal coordinator"
        value={reason}
        onChange={(e) => {
          setReason(e.target.value);
          if (error) setError(undefined);
        }}
        error={error}
        autoFocus
      />
      <div className="grid-2">
        <Button variant="secondary" size="sm" onClick={() => setOpen(false)} disabled={del.isPending}>
          Cancel
        </Button>
        <Button variant="danger" size="sm" loading={del.isPending} onClick={confirm}>
          {del.isPending ? 'Deleting…' : 'Delete hours'}
        </Button>
      </div>
    </div>
  );
}
