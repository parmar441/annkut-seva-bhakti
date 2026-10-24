/** Fetch wrapper: cookies, CSRF double-submit, one silent refresh on 401, and a typed error. */

export interface ApiErrorBody {
  code: string;
  message: string;
  fields?: Record<string, string>;
  details?: Record<string, unknown>;
}

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string>;
  details: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.status = status;
    this.code = body.code;
    this.fields = body.fields ?? {};
    this.details = body.details ?? {};
  }
}

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '';

function readCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfPromise: Promise<string> | null = null;

async function csrfToken(): Promise<string> {
  const existing = readCookie('csrf_token');
  if (existing) return existing;
  csrfPromise ??= fetch(`${BASE}/api/auth/csrf`, { credentials: 'include' })
    .then((r) => r.json())
    .then((b: { csrf_token: string }) => b.csrf_token)
    .finally(() => {
      csrfPromise = null;
    });
  return csrfPromise;
}

let refreshPromise: Promise<boolean> | null = null;

/** Rotate the refresh token once, shared by concurrent callers. */
function refreshSession(): Promise<boolean> {
  refreshPromise ??= (async () => {
    try {
      const r = await fetch(`${BASE}/api/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': await csrfToken() },
      });
      return r.ok;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshPromise = null), 0);
    }
  })();
  return refreshPromise;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(params?: Query): string {
  if (!params) return '';
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

export function apiUrl(path: string, params?: Query): string {
  return `${BASE}${path}${buildQuery(params)}`;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  params?: Query;
  /** Internal: prevents refresh loops. */
  retried?: boolean;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (method !== 'GET') headers['X-CSRF-Token'] = await csrfToken();

  let res: Response;
  try {
    res = await fetch(apiUrl(path, opts.params), {
      method,
      headers,
      credentials: 'include',
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new ApiError(0, { code: 'NETWORK', message: "Can't reach the server. Check your connection and try again." });
  }

  const isAuthRoute = path.startsWith('/api/auth/login') || path.startsWith('/api/auth/refresh');
  if (res.status === 401 && !opts.retried && !isAuthRoute) {
    if (await refreshSession()) return api<T>(path, { ...opts, retried: true });
  }
  if (res.status === 403 && !opts.retried) {
    const body = await res.clone().json().catch(() => null);
    if (body?.error?.code === 'CSRF_FAILED') {
      document.cookie = 'csrf_token=; Max-Age=0; path=/';
      return api<T>(path, { ...opts, retried: true });
    }
  }

  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err: ApiErrorBody = data?.error ?? { code: 'ERROR', message: 'Something went wrong. Please try again.' };
    throw new ApiError(res.status, err);
  }
  return data as T;
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return 'Something went wrong. Please try again.';
}

/** Download a file from an authenticated GET endpoint (refreshing the session if needed). */
export async function downloadFile(path: string, params: Query | undefined, fallbackName: string): Promise<void> {
  const get = () => fetch(apiUrl(path, params), { credentials: 'include' });
  let res = await get();
  if (res.status === 401 && (await refreshSession())) res = await get();
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, data?.error ?? { code: 'ERROR', message: 'Export failed. Please try again.' });
  }
  const disposition = res.headers.get('Content-Disposition') ?? '';
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
