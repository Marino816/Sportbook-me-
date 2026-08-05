const API_PATH = "/api";

/**
 * Normalize a public API URL to always include the /api base path.
 *
 * Input -> Output:
 *   https://example.com          -> https://example.com/api
 *   https://example.com/         -> https://example.com/api
 *   https://example.com/api      -> https://example.com/api
 *   https://example.com/api/     -> https://example.com/api
 *   http://localhost:8000        -> http://localhost:8000/api
 *   undefined                    -> http://localhost:8000/api
 */
function getApiBaseUrl(configuredUrl: string | undefined): string {
  const baseUrl = (configuredUrl || "http://localhost:8000/api").replace(/\/+$/, "");
  return baseUrl.endsWith(API_PATH) ? baseUrl : `${baseUrl}${API_PATH}`;
}

export { getApiBaseUrl };