import type { MandalName, MandalType } from '../lib/enums';

export type Role = 'user' | 'admin';
export type DisplayStatus = 'active' | 'completed' | 'flagged';
export type SessionFlag = 'missing_clock_out' | 'overlap' | 'long_session' | 'manual_entry';

export interface Duration {
  seconds: number;
  hm: string;
  long: string;
  decimal: number;
  decimal_text: string;
}

export interface User {
  id: string;
  full_name: string;
  username: string;
  mandal_name: MandalName;
  mandal_type: MandalType;
  role: Role;
  is_active: boolean;
  created_at: string | null;
  last_login_at: string | null;
}

export interface DaySplit extends Duration {
  date: string;
}

export interface Session {
  id: string;
  user_id: string;
  mandal_name: MandalName;
  mandal_type: MandalType;
  clock_in: string;
  clock_out: string | null;
  local_date: string;
  status: 'active' | 'completed';
  display_status: DisplayStatus;
  duration: Duration | null;
  flags: SessionFlag[];
  needs_review: boolean;
  overlap_with: string[];
  source: 'clock' | 'manual';
  reviewed_at: string | null;
  crosses_midnight: boolean;
  day_split: DaySplit[];
  elapsed_seconds?: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface VolunteerRef {
  id: string;
  full_name: string;
  username: string;
  mandal_name: MandalName;
  mandal_type: MandalType;
  is_active: boolean;
}

export interface AdminSession extends Session {
  volunteer: VolunteerRef | null;
  overlaps?: Session[];
}

export interface RangeInfo {
  from: string | null;
  to: string | null;
  preset?: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface Totals {
  duration: Duration;
  sessions: number;
}

export interface MeSummary {
  now: string;
  active_session: Session | null;
  totals: {
    today: Totals & RangeInfo;
    week: Totals & RangeInfo;
    month: Totals & RangeInfo;
    lifetime: Totals;
  };
  recent: Session[];
}

export interface SessionList extends Page<Session> {
  range: RangeInfo;
  summary: Totals;
}

export interface MeTotals extends Totals {
  range: RangeInfo;
  group: string;
  buckets: (Duration & { start: string })[];
}

export interface Preview {
  clock_in: string;
  clock_out: string | null;
  duration: Duration | null;
  errors: Record<string, string>;
  warnings: string[];
  overlaps: Session[];
  day_split: DaySplit[];
}

export interface AuditEntry {
  id: string;
  entity: 'seva_session' | 'user';
  entity_id: string;
  action: 'create' | 'update' | 'correct' | 'review' | 'activate' | 'deactivate';
  actor_id: string | null;
  actor_role: string;
  actor_username: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  reason: string | null;
  created_at: string;
  owner_name?: string | null;
  owner_username?: string | null;
}

export interface Meta {
  mandal_names: MandalName[];
  mandal_types: MandalType[];
  timezone: string;
  week_start: 'sunday' | 'monday';
  long_session_hours: number;
  max_session_hours: number;
}

export interface NamedHours extends Duration {
  name: string;
}

export interface AdminStats {
  now: string;
  month: RangeInfo;
  total_volunteers: number;
  active_accounts: number;
  completed_sessions: number;
  total_hours: Duration;
  hours_today: Duration;
  volunteers_today: number;
  hours_this_month: Duration;
  on_seva_now: number;
  needs_review: { total: number; by_flag: Record<SessionFlag, number> };
  by_mandal: NamedHours[];
  by_type: NamedHours[];
}

export interface AdminUser extends User {
  lifetime: Duration;
  on_seva_now: boolean;
}

export interface AdminUserDetail {
  user: User;
  lifetime: Totals;
  this_month: Totals;
  active_session: Session | null;
  needs_review: number;
}

export interface ReportResponse extends Page<AdminSession> {
  range: RangeInfo;
  label: string;
  totals: Totals & { volunteers: number };
  include_active_in_totals: boolean;
}

export interface GroupTotals {
  group_by: string;
  label?: string;
  items: (Duration & { key: string; label: string; sessions?: number; username?: string })[];
}

export interface ReviewResponse extends Page<AdminSession> {
  counts: Record<SessionFlag | 'all', number>;
}
