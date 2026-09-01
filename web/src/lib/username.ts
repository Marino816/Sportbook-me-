export const USERNAME_RULES = "3–24 characters: letters, numbers, underscore, or period. No spaces.";
const USERNAME_RE = /^[a-z0-9._]{3,24}$/;

export function normalizeUsername(raw: string): string {
  return (raw || "").trim().toLowerCase();
}

export function usernameFormatOk(raw: string): boolean {
  const value = normalizeUsername(raw);
  return USERNAME_RE.test(value) && /[a-z0-9]/.test(value);
}

/** Navbar label: authenticated username, else email if username is absent. */
export function navAccountLabel(user: {
  username?: string | null;
  email?: string | null;
} | null | undefined): string {
  const username = (user?.username || "").trim();
  if (username) return username;
  return (user?.email || "").trim();
}
