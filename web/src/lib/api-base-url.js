const API_PATH = "/api";
const PRODUCTION_API_URL = "https://sportbook-me-production.up.railway.app";

/**
 * Resolve the API base URL.
 *
 * Priority:
 *   1. NEXT_PUBLIC_API_URL environment variable
 *   2. Production Railway backend
 */
function getApiBaseUrl(configuredUrl) {
  const baseUrl = (configuredUrl || PRODUCTION_API_URL).replace(/\/+$/, "");
  return baseUrl.endsWith(API_PATH) ? baseUrl : `${baseUrl}${API_PATH}`;
}

module.exports = { getApiBaseUrl };