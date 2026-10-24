import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { BarChart3, ChevronRight, CircleUser, Clock, Filter, Flag, Home, LogOut, ShieldCheck, Users } from 'lucide-react';
import { useLogout, useMe } from '../api/hooks';
import { useToast } from './Toast';
import { Logo } from './ui';

const ICON = { size: 24, strokeWidth: 1.9, 'aria-hidden': true } as const;

function navClass() {
  return 'nav-item';
}

function SignOutButton({ className = 'nav-item', role, iconSize = 24 }: { className?: string; role?: string; iconSize?: number }) {
  const logout = useLogout();
  const navigate = useNavigate();
  const toast = useToast();
  return (
    <button
      type="button"
      className={className}
      role={role}
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
      <LogOut {...ICON} size={iconSize} />
      {logout.isPending ? 'Signing out…' : 'Sign out'}
    </button>
  );
}

/** Volunteer app: centered phone-width column with the bottom nav. */
export function VolunteerShell({ wide }: { wide?: boolean }) {
  const me = useMe();
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
        {me.data?.role === 'admin' && (
          <NavLink to="/admin" className={navClass}>
            <BarChart3 {...ICON} />
            Admin
          </NavLink>
        )}
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
        <NavLink to="/account/security-question" className={navClass}>
          <ShieldCheck {...ICON} />
          Security question
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

/** Until it's set, nudge the user to add a security question so they can reset a forgotten password. */
export function SecurityQuestionPrompt() {
  const me = useMe();
  if (!me.data || me.data.has_security_question) return null;
  return (
    <Link to="/account/security-question" className="banner">
      <ShieldCheck size={22} strokeWidth={2} aria-hidden="true" />
      <span className="main">
        <strong style={{ fontSize: 15 }}>Set up your security question</strong>
        <span style={{ fontSize: 12 }}>So you can reset your password yourself if you forget it.</span>
      </span>
      <ChevronRight size={20} strokeWidth={2} aria-hidden="true" />
    </Link>
  );
}

/** Phones only: My seva and Sign out (the sidebar has these from 768px). */
export function AdminAccountMenu() {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const location = useLocation();

  useEffect(() => setOpen(false), [location.pathname]);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    ref.current?.querySelector<HTMLElement>('[role=menuitem]')?.focus();
    return () => {
      document.removeEventListener('pointerdown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="account-menu" ref={ref}>
      <button
        ref={buttonRef}
        type="button"
        className="icon-btn"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <CircleUser size={26} strokeWidth={1.9} aria-hidden="true" />
      </button>
      {open && (
        <div id={menuId} role="menu" aria-label="Account" className="menu-pop">
          {me.data && (
            <p className="menu-who">
              <strong>{me.data.full_name}</strong>
              <span>@{me.data.username}</span>
            </p>
          )}
          <Link to="/" role="menuitem" className="menu-item">
            <Home size={20} strokeWidth={1.9} aria-hidden="true" />
            My seva
          </Link>
          <Link to="/account/security-question" role="menuitem" className="menu-item">
            <ShieldCheck size={20} strokeWidth={1.9} aria-hidden="true" />
            Security question
          </Link>
          <SignOutButton className="menu-item" role="menuitem" iconSize={20} />
        </div>
      )}
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
      <div className="row" style={{ gap: 4, alignItems: 'center' }}>
        {aside}
        <AdminAccountMenu />
      </div>
    </header>
  );
}
