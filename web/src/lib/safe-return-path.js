const FALLBACK_RETURN_PATH = "/dashboard";
const APPLICATION_ORIGIN = "https://sportbook-me.invalid";

/**
 * Returns a same-origin application path or the dashboard fallback.
 * @param {string | null | undefined} value
 * @returns {string}
 */
function getSafeReturnPath(value) {
  if (typeof value !== "string") return FALLBACK_RETURN_PATH;

  let candidate = value;
  for (let index = 0; index < 3; index += 1) {
    if (
      !candidate.startsWith("/") ||
      candidate.startsWith("//") ||
      candidate.includes("\\") ||
      /[\u0000-\u001F]/.test(candidate)
    ) {
      return FALLBACK_RETURN_PATH;
    }

    try {
      const decoded = decodeURIComponent(candidate);
      if (decoded === candidate) break;
      candidate = decoded;
    } catch {
      return FALLBACK_RETURN_PATH;
    }
  }

  if (
    !candidate.startsWith("/") ||
    candidate.startsWith("//") ||
    candidate.includes("\\") ||
    /[\u0000-\u001F]/.test(candidate)
  ) {
    return FALLBACK_RETURN_PATH;
  }

  const target = new URL(candidate, APPLICATION_ORIGIN);
  if (target.origin !== APPLICATION_ORIGIN) return FALLBACK_RETURN_PATH;

  return `${target.pathname}${target.search}${target.hash}`;
}

module.exports = { getSafeReturnPath };
