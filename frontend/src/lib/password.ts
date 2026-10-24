// Mirrors backend/app/auth/passwords.py. The server re-checks everything.
import commonList from '@shared/common_passwords.txt?raw';

const COMMON = new Set(
  commonList
    .split('\n')
    .map((l) => l.trim().toLowerCase())
    .filter((l) => l && !l.startsWith('#')),
);

const LEET: Record<string, string> = { '@': 'a', '4': 'a', '0': 'o', '1': 'i', '!': 'i', '3': 'e', $: 's', '5': 's', '7': 't' };
const leet = (s: string) => s.replace(/[@40135!$7]/g, (c) => LEET[c] ?? c);
const core = (s: string) => s.toLowerCase().replace(/^[^a-z]+|[^a-z]+$/g, '');

export function isCommonPassword(pw: string): boolean {
  const lower = pw.toLowerCase();
  return [lower, core(pw), leet(lower), leet(core(pw)), core(leet(lower))].some((c) => c && COMMON.has(c));
}

export interface PasswordCheck {
  id: string;
  label: string;
  ok: boolean;
}

export function passwordChecks(pw: string): PasswordCheck[] {
  return [
    { id: 'length', label: '12 or more characters', ok: pw.length >= 12 },
    { id: 'case', label: 'Uppercase and lowercase letters', ok: /[a-z]/.test(pw) && /[A-Z]/.test(pw) },
    { id: 'number', label: 'At least one number', ok: /\d/.test(pw) },
    { id: 'special', label: 'At least one special character (!@#$…)', ok: /[^A-Za-z0-9]/.test(pw) },
    { id: 'common', label: 'Not a commonly used password', ok: pw.length > 0 && !isCommonPassword(pw) },
  ];
}
