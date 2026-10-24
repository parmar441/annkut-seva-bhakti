import type { ReactNode } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { BarChart3, Clock, Filter, Flag, Home, LogOut, Users } from 'lucide-react';
import { useLogout } from '../api/hooks';
import { useToast } from './Toast';
import { Logo } from './ui';

const ICON = { size: 24, strokeWidth: 1.9, 'aria-hidden': true } as const;

function navClass() {
  return 'nav-item';
}

function SignOutButton({ className = 'nav-item' }: { className?: string }) {
  const logout = useLogout();
  const navigate = useNavigate();
  const toast = useToast();
  return (
    <button
      type="button"
      className={className}
      disabled={logout.isPending}
      onClick={() =>
        logout.mutate(undefined, {
          onSettled: () => {
            toast('Signed out');
            navigate('/login', { replace: true });
          },
        })
      }
    >
      <LogOut {...ICON} />
      Sign out
    </button>
  );
}

/** Volunteer app: centered phone-width column with the bottom nav. */
export function VolunteerShell({ wide }: { wide?: boolean }) {
  return (
    <div className={`app-column${wide ? ' wide' : ''}`}>
      <main id="main" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Outlet />
      </main>
      <nav aria-label="Main" className="bottom-nav">
        <NavLink to="/" end className={navClass}>
          <Home {...ICON} />
          Home
        </NavLink>
        <NavLink to="/history" className={navClass}>
          <Clock {...ICON} />
          History
        </NavLink>
        <SignOutButton />
      </nav>
    </div>
  );
}

/** Full-screen volunteer sub-pages (detail, edit) with their own back button and no bottom nav. */
export function SubpageShell() {
  return (
    <div className="app-column">
      <main id="main" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Outlet />
      </main>
    </div>
  );
}

const ADMIN_LINKS = [
  { to: '/admin', label: 'Overview', icon: BarChart3, end: true },
  { to: '/admin/reports', label: 'Reports', icon: Filter },
  { to: '/admin/review', label: 'Review', icon: Flag },
  { to: '/admin/volunteers', label: 'Volunteers', icon: Users },
];

/** Admin console: bottom nav on phones, sidebar from 768px. */
export function AdminShell() {
  return (
    <div className="admin-layout">
      <nav aria-label="Admin" className="side-nav">
        <div className="brand-row">
          <Logo size={36} />
          Annkut Seva Bhakti
        </div>
        {ADMIN_LINKS.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={navClass}>
            <Icon {...ICON} />
            {label}
          </NavLink>
        ))}
        <div className="spacer" />
        <NavLink to="/" end className={navClass}>
          <Home {...ICON} />
          My seva
        </NavLink>
        <SignOutButton />
      </nav>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <main id="main" className="admin-main">
          <Outlet />
        </main>
        <nav aria-label="Admin" className="bottom-nav">
          {ADMIN_LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={navClass}>
              <Icon {...ICON} />
              {label}
            </NavLink>
          ))}
        </nav>
      </div>
    </div>
  );
}

export function AdminHeader({ title, aside }: { title: string; aside?: ReactNode }) {
  return (
    <header className="page-header" style={{ alignItems: 'flex-end' }}>
      <div className="stack-sm">
        <span className="admin-badge">ADMIN</span>
        <h1 className="page-title">{title}</h1>
      </div>
      {aside}
    </header>
  );
}
