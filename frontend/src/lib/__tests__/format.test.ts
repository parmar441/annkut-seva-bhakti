import { describe, expect, it } from 'vitest';
import { formatDecimalHours, formatElapsed, formatHm, formatRange, localParts, setTimezone } from '../format';
import { isCommonPassword, passwordChecks } from '../password';

describe('duration formatting matches the server rules', () => {
  it.each([
    [9000, '2h 30m', '2.5 h'],
    [672300, '186h 45m', '186.75 h'],
    [8442, '2h 20m', '2.35 h'], // half-up decimals, floored minutes
    [18, '0m', '0.01 h'],
    [0, '0m', '0 h'],
  ])('%i seconds', (secs, hm, dec) => {
    expect(formatHm(secs)).toBe(hm);
    expect(formatDecimalHours(secs)).toBe(dec);
  });

  it('formats the live timer', () => {
    expect(formatElapsed(2 * 3600 + 18 * 60 + 45)).toBe('2:18:45');
  });
});

describe('timezone-aware parts', () => {
  it('uses the app timezone, not the browser', () => {
    setTimezone('America/New_York');
    // 02:00 UTC on Oct 24 is still Oct 23 in New York
    expect(localParts('2026-10-24T02:00:00Z')).toEqual({ date: '2026-10-23', time: '22:00' });
  });
  it('formats ranges', () => {
    expect(formatRange('2026-10-01', '2026-10-23')).toBe('Oct 1 – Oct 23');
  });
});

describe('password checklist', () => {
  it('passes a strong password', () => {
    expect(passwordChecks('Seva-Kitchen-42!').every((c) => c.ok)).toBe(true);
  });
  it('accepts 6 characters and rejects 5', () => {
    const ok = (pw: string) => passwordChecks(pw).find((c) => c.id === 'length')!.ok;
    expect(ok('Sv7!kq')).toBe(true);
    expect(ok('Sv7!k')).toBe(false);
    expect(passwordChecks('Sv7!kq').every((c) => c.ok)).toBe(true);
  });
  it('flags weak and common passwords', () => {
    const checks = Object.fromEntries(passwordChecks('pass').map((c) => [c.id, c.ok]));
    expect(checks).toMatchObject({ length: false, case: false, number: false, special: false, common: false });
    expect(isCommonPassword('Welcome@2024!!')).toBe(true);
    expect(isCommonPassword('P@ssw0rd12345!')).toBe(true);
  });
});
