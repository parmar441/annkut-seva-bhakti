import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAdminUsers, useMe, useSetUserStatus } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import type { AdminUser } from '../../api/types';
import { AdminHeader } from '../../components/Shells';
import { SelectField, TextField } from '../../components/Field';
import { EmptyState, ErrorState, Pagination, Skeleton, Switch } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { MANDAL_NAMES, MANDAL_TYPES } from '../../lib/enums';
import { initials } from '../../lib/format';

function VolunteerCard({ p, isSelf }: { p: AdminUser; isSelf: boolean }) {
  const setStatus = useSetUserStatus();
  const toast = useToast();
  const toggle = (next: boolean) =>
    setStatus.mutate(
      { id: p.id, is_active: next },
      {
        onSuccess: () => toast(next ? `${p.full_name} can sign in again` : `${p.full_name} has been deactivated and signed out`),
        onError: (e) => toast(errorMessage(e), 'error'),
      },
    );
  return (
    <article className="card stack" style={{ opacity: p.is_active ? 1 : 0.7 }}>
      <div className="row" style={{ gap: 12 }}>
        <div className="avatar" aria-hidden="true">
          {initials(p.full_name)}
        </div>
        <div className="stack-sm" style={{ flex: 1, gap: 2, minWidth: 0 }}>
          <h2 style={{ fontSize: 15, fontWeight: 800 }}>{p.full_name}</h2>
          <p className="muted" style={{ fontSize: 12, overflowWrap: 'anywhere' }}>
            @{p.username} · {p.mandal_name} · {p.mandal_type}
            {p.on_seva_now && ' · on seva now'}
          </p>
        </div>
        <Switch
          checked={p.is_active}
          label={`${p.is_active ? 'Deactivate' : 'Activate'} ${p.full_name}`}
          onChange={toggle}
          disabled={setStatus.isPending || isSelf}
        />
      </div>
      <div className="row" style={{ justifyContent: 'space-between', borderTop: '1px solid var(--surface-muted)', paddingTop: 10 }}>
        <p className="muted" style={{ fontSize: 13 }}>
          <strong style={{ color: 'var(--ink)' }}>{p.lifetime.hm}</strong> lifetime · {p.is_active ? 'Active account' : 'Deactivated'}
        </p>
        <Link to={`/admin/volunteers/${p.id}`} style={{ fontSize: 13, fontWeight: 700, padding: '10px 0' }}>
          View history
        </Link>
      </div>
    </article>
  );
}

export default function Volunteers() {
  const me = useMe();
  const [search, setSearch] = useState('');
  const [q, setQ] = useState('');
  const [mandal, setMandal] = useState('');
  const [type, setType] = useState('');
  const [page, setPage] = useState(1);
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);
  const users = useAdminUsers({ q, mandal_name: mandal, mandal_type: type, page });
  const total = useAdminUsers({});

  return (
    <div className="page tight">
      <AdminHeader title="Volunteers" aside={<p className="muted" style={{ fontSize: 13 }}>{total.data ? `${total.data.total} registered` : ''}</p>} />
      <TextField label="Search by name or username" small type="search" placeholder="Search volunteers" value={search} onChange={(e) => setSearch(e.target.value)} />
      <div className="grid-2">
        <SelectField small label="Mandal" options={MANDAL_NAMES} placeholder="All Mandals" value={mandal} onChange={(e) => {
            setMandal(e.target.value);
            setPage(1);
          }} />
        <SelectField small label="Type" options={MANDAL_TYPES} placeholder="All Types" value={type} onChange={(e) => {
            setType(e.target.value);
            setPage(1);
          }} />
      </div>
      <section aria-label="Volunteer list" className="stack cards-desktop-grid" style={{ gap: 10 }}>
        {users.isPending ? (
          <Skeleton count={4} height={110} />
        ) : users.isError ? (
          <ErrorState message={errorMessage(users.error)} onRetry={() => users.refetch()} />
        ) : users.data.items.length === 0 ? (
          <EmptyState>No volunteers match these filters.</EmptyState>
        ) : (
          users.data.items.map((p) => <VolunteerCard key={p.id} p={p} isSelf={p.id === me.data?.id} />)
        )}
      </section>
      {users.data && <Pagination page={users.data.page} pages={users.data.pages} total={users.data.total} pageSize={users.data.page_size} onPage={setPage} />}
    </div>
  );
}
