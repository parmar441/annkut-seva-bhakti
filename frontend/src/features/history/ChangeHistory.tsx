import type { AuditEntry } from '../../api/types';
import { describeActor, describeChange, userReason } from '../../lib/audit';
import { Skeleton } from '../../components/ui';

export function ChangeHistory({ entries, meId, loading }: { entries: AuditEntry[] | undefined; meId?: string; loading?: boolean }) {
  return (
    <section aria-label="Change history" className="stack" style={{ gap: 10 }}>
      <h2 className="section-title sm">Change history</h2>
      {loading ? (
        <Skeleton height={40} count={2} />
      ) : !entries?.length ? (
        <p className="muted" style={{ fontSize: 13 }}>
          No changes recorded.
        </p>
      ) : (
        <ol className="timeline">
          {entries.map((e) => {
            const reason = userReason(e);
            return (
              <li key={e.id}>
                <span className="bullet" aria-hidden="true" />
                <div className="stack-sm" style={{ gap: 2 }}>
                  <p className="what">{describeChange(e)}</p>
                  <p className="who">
                    {describeActor(e, meId)}
                    {reason ? ` · “${reason}”` : ''}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
