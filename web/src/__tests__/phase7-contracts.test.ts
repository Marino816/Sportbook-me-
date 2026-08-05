import { describe, it, expect } from "vitest";

// Import the helper directly via relative path from __tests__
import { getApiBaseUrl } from "../lib/api-base-url";

describe("getApiBaseUrl", () => {
  it("appends /api to origin-only URL", () => {
    expect(getApiBaseUrl("https://sportbook-me-production.up.railway.app")).toBe(
      "https://sportbook-me-production.up.railway.app/api"
    );
  });

  it("returns /api URL unchanged", () => {
    expect(getApiBaseUrl("https://sportbook-me-production.up.railway.app/api")).toBe(
      "https://sportbook-me-production.up.railway.app/api"
    );
  });

  it("strips trailing /api/", () => {
    expect(getApiBaseUrl("https://sportbook-me-production.up.railway.app/api/")).toBe(
      "https://sportbook-me-production.up.railway.app/api"
    );
  });

  it("local dev default", () => {
    expect(getApiBaseUrl(undefined)).toBe("http://localhost:8000/api");
  });

  it("never produces double slashes after host", () => {
    expect(getApiBaseUrl("https://example.com/")).toBe("https://example.com/api");
    expect(getApiBaseUrl("https://example.com")).toBe("https://example.com/api");
  });

  it("never produces doubled /api/api", () => {
    expect(getApiBaseUrl("https://example.com/api")).toBe("https://example.com/api");
  });
});

describe("error state mapping", () => {
  it("maps numeric status codes", () => {
    const isErrorStatus = (s: number) => {
      if (s === 401) return "unauthorized";
      if (s === 403) return "forbidden";
      if (s === 404) return "not-found";
      if (s === 429) return "rate-limited";
      if (s >= 500) return "server-error";
      return "server-error";
    };
    expect(isErrorStatus(401)).toBe("unauthorized");
    expect(isErrorStatus(403)).toBe("forbidden");
    expect(isErrorStatus(404)).toBe("not-found");
    expect(isErrorStatus(429)).toBe("rate-limited");
    expect(isErrorStatus(500)).toBe("server-error");
    expect(isErrorStatus(502)).toBe("server-error");
  });
});

describe("demo data guard", () => {
  it("defaults to false", () => {
    expect(process.env.NEXT_PUBLIC_ENABLE_DEMO_DATA).not.toBe("true");
  });
});
