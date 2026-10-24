// Single source of truth shared with the backend (shared/enums.json).
import enums from '@shared/enums.json';

export const MANDAL_NAMES = enums.mandal_names as readonly string[];
export const MANDAL_TYPES = enums.mandal_types as readonly string[];
export const PASSWORD_MIN_LENGTH: number = enums.password_min_length;

export type MandalName = (typeof enums.mandal_names)[number];
export type MandalType = (typeof enums.mandal_types)[number];
