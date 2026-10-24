import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  AdminSession,
  AdminStats,
  AdminUser,
  AdminUserDetail,
  AuditEntry,
  GroupTotals,
  Meta,
  MeSummary,
  MeTotals,
  Page,
  PasswordReset,
  Preview,
  ReportResponse,
  ReviewResponse,
  Session,
  SessionList,
  User,
} from './types';

type Params = Record<string, string | number | boolean | null | undefined>;

export const keys = {
  me: ['me'] as const,
  meta: ['meta'] as const,
  summary: ['me', 'summary'] as const,
  sessions: (p: Params) => ['me', 'sessions', p] as const,
  session: (id: string) => ['me', 'session', id] as const,
  audit: (id: string) => ['me', 'session', id, 'audit'] as const,
  totals: (p: Params) => ['me', 'totals', p] as const,
  admin: ['admin'] as const,
};

// ---------- auth ----------

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api<{ user: User }>('/api/auth/me').then((r) => r.user),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function useMeta() {
  return useQuery({
    queryKey: keys.meta,
    queryFn: () => api<Meta>('/api/meta/enums'),
    staleTime: Infinity,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { username: string; password: string }) =>
      api<{ user: User }>('/api/auth/login', { method: 'POST', body }),
    onSuccess: (r) => {
      qc.clear();
      qc.setQueryData(keys.me, r.user);
    },
  });
}

export interface RegisterBody {
  full_name: string;
  username: string;
  password: string;
  confirm_password: string;
  mandal_name: string;
  mandal_type: string;
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: RegisterBody) => api<{ user: User }>('/api/auth/register', { method: 'POST', body }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>('/api/auth/logout', { method: 'POST' }),
    onSettled: () => {
      qc.clear();
      qc.setQueryData(keys.me, null);
    },
  });
}

// ---------- volunteer ----------

export function useSummary() {
  return useQuery({
    queryKey: keys.summary,
    queryFn: () => api<MeSummary>('/api/me/summary'),
    refetchInterval: 60_000,
  });
}

export function useMySessions(params: Params) {
  return useQuery({
    queryKey: keys.sessions(params),
    queryFn: () => api<SessionList>('/api/me/sessions', { params }),
    placeholderData: keepPreviousData,
  });
}

export function useMySession(id: string | undefined) {
  return useQuery({
    queryKey: keys.session(id ?? ''),
    queryFn: () => api<{ session: Session }>(`/api/me/sessions/${id}`).then((r) => r.session),
    enabled: !!id,
  });
}

export function useMySessionAudit(id: string | undefined) {
  return useQuery({
    queryKey: keys.audit(id ?? ''),
    queryFn: () => api<{ items: AuditEntry[] }>(`/api/me/sessions/${id}/audit`).then((r) => r.items),
    enabled: !!id,
  });
}

export function useMyTotals(params: Params, enabled = true) {
  return useQuery({
    queryKey: keys.totals(params),
    queryFn: () => api<MeTotals>('/api/me/totals', { params }),
    enabled,
    placeholderData: keepPreviousData,
  });
}

function useInvalidateMine() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ['me'], predicate: (q) => q.queryKey.length > 1 });
}

export function useClockIn() {
  const invalidate = useInvalidateMine();
  return useMutation({
    mutationFn: () => api<{ session: Session }>('/api/me/sessions/clock-in', { method: 'POST' }).then((r) => r.session),
    onSettled: invalidate,
  });
}

export function useClockOut() {
  const invalidate = useInvalidateMine();
  return useMutation({
    mutationFn: () => api<{ session: Session }>('/api/me/sessions/clock-out', { method: 'POST' }).then((r) => r.session),
    onSettled: invalidate,
  });
}

export interface TimesBody {
  clock_in?: string;
  clock_out?: string;
  reason?: string;
  confirm_overlap?: boolean;
}

export function useSaveSession(id?: string) {
  const invalidate = useInvalidateMine();
  return useMutation({
    mutationFn: (body: TimesBody) =>
      (id
        ? api<{ session: Session }>(`/api/me/sessions/${id}`, { method: 'PATCH', body })
        : api<{ session: Session }>('/api/me/sessions', { method: 'POST', body })
      ).then((r) => r.session),
    onSuccess: invalidate,
  });
}

export function previewMine(body: { clock_in: string; clock_out?: string; session_id?: string }) {
  return api<Preview>('/api/me/sessions/preview', { method: 'POST', body });
}

// ---------- admin ----------

export function useAdminStats() {
  return useQuery({ queryKey: ['admin', 'stats'], queryFn: () => api<AdminStats>('/api/admin/stats'), refetchInterval: 60_000 });
}

export function useAdminReport(params: Params) {
  return useQuery({
    queryKey: ['admin', 'report', params],
    queryFn: () => api<ReportResponse>('/api/admin/sessions', { params }),
    placeholderData: keepPreviousData,
  });
}

export function useAdminTotals(params: Params) {
  return useQuery({
    queryKey: ['admin', 'totals', params],
    queryFn: () => api<GroupTotals>('/api/admin/totals', { params }),
    placeholderData: keepPreviousData,
  });
}

export function useAdminUsers(params: Params) {
  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => api<Page<AdminUser>>('/api/admin/users', { params }),
    placeholderData: keepPreviousData,
  });
}

export function useAdminUser(id: string | undefined) {
  return useQuery({
    queryKey: ['admin', 'user', id],
    queryFn: () => api<AdminUserDetail>(`/api/admin/users/${id}`),
    enabled: !!id,
  });
}

export function useAdminUserSessions(id: string | undefined, params: Params) {
  return useQuery({
    queryKey: ['admin', 'user', id, 'sessions', params],
    queryFn: () => api<Page<Session>>(`/api/admin/users/${id}/sessions`, { params }),
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}

export function useSetUserStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      api<{ user: User }>(`/api/admin/users/${id}/status`, { method: 'PATCH', body: { is_active } }),
    onSettled: () => qc.invalidateQueries({ queryKey: keys.admin }),
  });
}

export function useReviewQueue(params: Params) {
  return useQuery({
    queryKey: ['admin', 'review', params],
    queryFn: () => api<ReviewResponse>('/api/admin/review', { params }),
    placeholderData: keepPreviousData,
  });
}

export function useAuditLog(params: Params) {
  return useQuery({
    queryKey: ['admin', 'audit', params],
    queryFn: () => api<Page<AuditEntry>>('/api/admin/audit', { params }),
  });
}

export function useCorrectSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: TimesBody & { id: string; reason: string }) =>
      api<{ session: AdminSession }>(`/api/admin/sessions/${id}`, { method: 'PATCH', body }).then((r) => r.session),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.admin }),
  });
}

export function useMarkReviewed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      api<{ session: AdminSession }>(`/api/admin/sessions/${id}/mark-reviewed`, { method: 'POST', body: { reason } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.admin }),
  });
}

export function previewAdmin(id: string, body: { clock_in: string; clock_out?: string }) {
  return api<Preview>(`/api/admin/sessions/${id}/preview`, { method: 'POST', body });
}

// ---------- forgotten passwords ----------

export function useRequestReset() {
  return useMutation({
    mutationFn: (username: string) => api<{ message: string }>('/api/auth/password-reset/request', { method: 'POST', body: { username } }),
  });
}

export interface ResetConfirmBody {
  username: string;
  code: string;
  password: string;
  confirm_password: string;
}

export function useConfirmReset() {
  return useMutation({
    mutationFn: (body: ResetConfirmBody) => api<{ message: string }>('/api/auth/password-reset/confirm', { method: 'POST', body }),
  });
}

export function useResetRequests() {
  return useQuery({
    queryKey: ['admin', 'password-resets'],
    queryFn: () => api<Page<PasswordReset>>('/api/admin/password-resets', { params: { status: 'requested' } }),
    refetchInterval: 30_000,
  });
}

export function useUserReset(id: string | undefined) {
  return useQuery({
    queryKey: ['admin', 'user', id, 'password-reset'],
    queryFn: () => api<{ reset: PasswordReset | null }>(`/api/admin/users/${id}/password-reset`).then((r) => r.reset),
    enabled: !!id,
  });
}

export function useIssueResetCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<{ code: string; reset: PasswordReset }>(`/api/admin/users/${id}/password-reset`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.admin }),
  });
}

export function useCancelReset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<{ reset: null }>(`/api/admin/users/${id}/password-reset/cancel`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.admin }),
  });
}
