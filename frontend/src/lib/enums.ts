// Single source of truth shared with the backend (shared/enums.json).
import enums from '@shared/enums.json';

export const MANDAL_NAMES = enums.mandal_names as readonly string[];
export const MANDAL_TYPES = enums.mandal_types as readonly string[];
export const PASSWORD_MIN_LENGTH: number = enums.password_min_length;
export const SECURITY_QUESTIONS = enums.security_questions as readonly string[];
export const SECURITY_ANSWER_MIN_LENGTH: number = enums.security_answer_min_length;

/** Same normalisation as the server: case, spacing and punctuation don't matter. */
export function normalizeAnswer(answer: string): string {
  return answer.toLowerCase().replace(/[^\p{L}\p{N}_\s]/gu, ' ').split(/\s+/).filter(Boolean).join(' ');
}

export type MandalName = (typeof enums.mandal_names)[number];
export type MandalType = (typeof enums.mandal_types)[number];
