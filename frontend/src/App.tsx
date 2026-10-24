import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useMeta } from './api/hooks';
import { AdminShell, SubpageShell, VolunteerShell } from './components/Shells';
import { Spinner } from './components/ui';
import { setTimezone } from './lib/format';
import { GuestOnly, RequireAdmin, RequireAuth } from './routes/guards';
import SignIn from './features/auth/SignIn';
import Register from './features/auth/Register';
import Dashboard from './features/dashboard/Dashboard';
import History from './features/history/History';
import SessionDetail from './features/history/SessionDetail';
import EditSession from './features/history/EditSession';
import Overview from './features/admin/Overview';
import Reports from './features/admin/Reports';
import Review from './features/admin/Review';
import Volunteers from './features/admin/Volunteers';
import VolunteerDetail from './features/admin/VolunteerDetail';

/** Times render in the server-configured timezone, so wait for it before rendering anything. */
function MetaGate({ children }: { children: ReactNode }) {
  const meta = useMeta();
  if (meta.isPending) return <Spinner />;
  if (meta.data) setTimezone(meta.data.timezone);
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <a href="#main" className="sr-only">
        Skip to content
      </a>
      <MetaGate>
        <Routes>
          <Route path="/login" element={<GuestOnly><SignIn /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />

          <Route element={<RequireAuth><VolunteerShell /></RequireAuth>}>
            <Route index element={<Dashboard />} />
          </Route>
          <Route element={<RequireAuth><VolunteerShell wide /></RequireAuth>}>
            <Route path="/history" element={<History />} />
          </Route>
          <Route element={<RequireAuth><SubpageShell /></RequireAuth>}>
            <Route path="/history/new" element={<EditSession />} />
            <Route path="/history/:id" element={<SessionDetail />} />
            <Route path="/history/:id/edit" element={<EditSession />} />
          </Route>

          <Route path="/admin" element={<RequireAdmin><AdminShell /></RequireAdmin>}>
            <Route index element={<Overview />} />
            <Route path="reports" element={<Reports />} />
            <Route path="review" element={<Review />} />
            <Route path="volunteers" element={<Volunteers />} />
            <Route path="volunteers/:id" element={<VolunteerDetail />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </MetaGate>
    </BrowserRouter>
  );
}
