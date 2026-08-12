const API_PATH = "/api";
const PRODUCTION_API_URL = "https://sportbook-me-production.up.railway.app";

/**
 * Resolve the API base URL.
 *
 * Priority:
 *   1. NEXT_PUBLIC_API_URL environment variable (Vercel prod / developer override)
 *   2. Production Railway backend (https://sportbook-me-production.up.railway.app)
 *
 * Never falls back to localhost in production builds.
 */
export function getApiBaseUrl(configuredUrl: string | undefined): string {
  const baseUrl = (configuredUrl || PRODUCTION_API_URL).replace(/\/+$/, "");
  return baseUrl.endsWith(API_PATH) ? baseUrl : `${baseUrl}${API_PATH}`;
}

/**
 * Resolve the API base URL (CommonJS export for shared configs).
 */
export function resolveApiUrl(): string {
  const configured = typeof process !== "undefined"
    ? process.env.NEXT_PUBLIC_API_URL
    : undefined;
  return getApiBaseUrl(configured);
}