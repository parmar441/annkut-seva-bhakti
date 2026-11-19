import { Link } from 'react-router-dom';
import { Segmented, type Option } from './ui';

export interface RankedVolunteer {
  id: string;
  name: string;
  hours: string;
  sessions?: number;
  /** Extra context shown before the session count, e.g. the volunteer's Mandal Type. */
  detail?: string;
}

/** Numbered list of volunteers, most hours first. Rows are full-width tap targets on phones. */
export function TopVolunteerList({ items, label }: { items: RankedVolunteer[]; label: string }) {
  return (
    <ol className="top-list" aria-label={label}>
      {items.map((v, i) => (
        <li key={v.id}>
          <span className="rank tabular" aria-hidden="true">
            {i + 1}
          </span>
          <span className="who">
            <Link to={`/admin/volunteers/${v.id}`}>{v.name}</Link>
            {(v.detail || v.sessions !== undefined) && (
              <span className="meta">
                {[v.detail, v.sessions !== undefined && `${v.sessions} session${v.sessions === 1 ? '' : 's'}`].filter(Boolean).join(' · ')}
              </span>
            )}
          </span>
          <span className="tabular hours">{v.hours}</span>
        </li>
      ))}
    </ol>
  );
}

/** "Top 3 / 5 / 10" style picker. */
export function TopCountPicker<T extends string>({ options, value, onChange, label }: { options: readonly T[]; value: T; onChange: (v: T) => void; label: string }) {
  const opts: Option<T>[] = options.map((n) => ({ id: n, label: `Top ${n}` }));
  return (
    <div className="top-count">
      <Segmented label={label} options={opts} value={value} onChange={onChange} />
    </div>
  );
}

/** Per-viewer remembered choice; storage can be unavailable, so every access is guarded. */
export function readChoice<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}

export function saveChoice(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore: the choice just won't be remembered */
  }
}
