import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useMe } from '../api/hooks';
import { Spinner } from '../components/ui';

/** UI guard only; the backend enforces auth and roles on every endpoint. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return <Spinner label="Checking your session" />;
  if (!me.data) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <Spinner />;
  if (!me.data) return <Navigate to="/login" replace />;
  if (me.data.role !== 'admin') return <Navigate to="/" replace />;
  return <>{children}</>;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return <Spinner />;
  if (me.data) return <Navigate to={me.data.role === 'admin' ? '/admin' : '/'} replace />;
  return <>{children}</>;
}
