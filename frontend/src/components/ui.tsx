/** Small presentational components from docs/DESIGN.md. */
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Check, Circle } from 'lucide-react';
import type { DisplayStatus, Duration } from '../api/types';
import type { PasswordCheck } from '../lib/password';

export function Logo({ size = 72 }: { size?: number }) {
  const icon = Math.round(size * 0.53);
  return (
    <div className="logo" style={{ width: size, height: size }} aria-hidden="true">
      <svg width={icon} height={icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3.5 13.5c0 3.4 3.8 5.5 8.5 5.5s8.5-2.1 8.5-5.5z" />
        <path d="M12 3.5c1.6 2.1 2.2 3.5 2.2 4.8a2.2 2.2 0 0 1-4.4 0c0-1.3.6-2.7 2.2-4.8z" />
        <path d="M9 21.5h6" />
      </svg>
    </div>
  );
}

type Variant = 'primary' | 'secondary' | 'inverse' | 'ghost' | 'danger' | 'danger-outline';
type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: 'lg' | 'md' | 'sm';
  block?: boolean;
  loading?: boolean;
};

export function Button({ variant = 'primary', size = 'lg', block, loading, className, children, disabled, type = 'button', ...rest }: ButtonProps) {
  const cls = ['btn', `btn-${variant}`, size !== 'lg' && `btn-${size}`, block && 'btn-block', className].filter(Boolean).join(' ');
  return (
    <button type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {children}
    </button>
  );
}

const STATUS_LABEL: Record<DisplayStatus, string> = { active: 'Active', completed: 'Completed', flagged: 'Flagged' };

export function StatusPill({ status }: { status: DisplayStatus }) {
  return <span className={`pill pill-${status}`}>{STATUS_LABEL[status]}</span>;
}

export function StatCard({ label, value, sub, large }: { label: ReactNode; value: ReactNode; sub?: ReactNode; large?: boolean }) {
  return (
    <div className={`stat${large ? ' lg' : ''}`}>
      <p className="label">{label}</p>
      <p className="value">{value}</p>
      {sub !== undefined && <p className="sub">{sub}</p>}
    </div>
  );
}

export function DurationStat({ label, duration }: { label: string; duration: Duration | undefined }) {
  return <StatCard label={label} value={duration?.hm ?? '—'} sub={duration?.decimal_text ?? ''} />;
}

export interface Option<T extends string> {
  id: T;
  label: string;
}

export function ChipGroup<T extends string>({ label, options, value, onChange }: { label: string; options: Option<T>[]; value: T; onChange: (v: T) => void }) {
  return (
    <div role="group" aria-label={label} className="chips">
      {options.map((o) => (
        <button key={o.id} type="button" className="chip" aria-pressed={value === o.id} onClick={() => onChange(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({
  labelledBy,
  label,
  options,
  value,
  onChange,
  tabs,
  wrap,
}: {
  labelledBy?: string;
  label?: string;
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
  tabs?: boolean;
  wrap?: boolean;
}) {
  return (
    <div
      role={tabs ? 'tablist' : 'group'}
      aria-labelledby={labelledBy}
      aria-label={label}
      className={`segmented${wrap ? ' wrap2' : ''}`}
    >
      {options.map((o) =>
        tabs ? (
          <button key={o.id} type="button" role="tab" aria-selected={value === o.id} onClick={() => onChange(o.id)}>
            {o.label}
          </button>
        ) : (
          <button key={o.id} type="button" aria-pressed={value === o.id} onClick={() => onChange(o.id)}>
            {o.label}
          </button>
        ),
      )}
    </div>
  );
}

export function Switch({ checked, onChange, label, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  return (
    <button type="button" role="switch" className="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)}>
      <span className="track">
        <span className="thumb" />
      </span>
    </button>
  );
}

export function HoursBar({ name, value, fraction }: { name: string; value: string; fraction: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(fraction * 100)));
  return (
    <div className="hours-bar">
      <div className="top">
        <span style={{ fontWeight: 600 }}>{name}</span>
        <span className="tabular" style={{ fontWeight: 700 }}>
          {value}
        </span>
      </div>
      <div className="track" role="presentation">
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function PasswordStrength({ checks }: { checks: PasswordCheck[] }) {
  const passed = checks.filter((c) => c.ok).length;
  // Four segments for five rules: the last segment fills only when every rule passes.
  const segments = passed === checks.length ? 4 : Math.min(3, passed);
  return (
    <>
      <div className="strength-bar" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className={i < segments ? 'on' : ''} />
        ))}
      </div>
      <ul className="checklist" aria-label="Password requirements">
        {checks.map((c) => (
          <li key={c.id} className={c.ok ? 'ok' : ''}>
            {c.ok ? <Check size={16} strokeWidth={2.4} aria-hidden="true" /> : <Circle size={16} strokeWidth={2.4} aria-hidden="true" />}
            {c.label}
            <span className="sr-only">{c.ok ? ' (met)' : ' (not met)'}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite">
      <div className="spinner" />
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function Skeleton({ height = 64, count = 1 }: { height?: number; count?: number }) {
  return (
    <div className="stack" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="skeleton" style={{ minHeight: height }} />
      ))}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert danger" role="alert">
      <div className="stack-sm" style={{ flex: 1 }}>
        <span>{message}</span>
        {onRetry && (
          <button type="button" className="btn btn-secondary btn-sm" style={{ alignSelf: 'flex-start' }} onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function Pagination({ page, pages, total, pageSize, onPage }: { page: number; pages: number; total: number; pageSize: number; onPage: (p: number) => void }) {
  if (pages <= 1) return null;
  const first = (page - 1) * pageSize + 1;
  const last = Math.min(total, page * pageSize);
  return (
    <nav aria-label="Pagination" className="pagination">
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </Button>
      <p aria-live="polite">
        {first}–{last} of {total.toLocaleString('en-US')}
      </p>
      <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </Button>
    </nav>
  );
}
