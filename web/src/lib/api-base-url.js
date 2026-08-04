const API_PATH = "/api";

/**
 * Adds the backend API prefix to an origin-only public API URL.
 * @param {string | undefined} configuredUrl
 * @returns {string}
 */
function getApiBaseUrl(configuredUrl) {
  const baseUrl = (configuredUrl || "http://localhost:8000/api").replace(/\/+$/, "");
  return baseUrl.endsWith(API_PATH) ? baseUrl : `${baseUrl}${API_PATH}`;
}

module.exports = { getApiBaseUrl };
