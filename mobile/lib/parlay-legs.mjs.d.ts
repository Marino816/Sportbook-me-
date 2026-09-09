export function legIdentity(eventId: unknown, market: unknown, selection: unknown): string;
export function hasDuplicateLeg(legs: any[], eventId: unknown, market: unknown, selection: unknown): boolean;
export function hasConflictingLeg(legs: any[], eventId: unknown, market: unknown, selection: unknown): boolean;
export function uniqueValidLegs<T>(legs: T[]): T[];
